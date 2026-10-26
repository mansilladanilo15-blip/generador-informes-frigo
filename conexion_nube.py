"""Conexión compartida con Supabase para la aplicación PC y móvil.

Mantiene los nombres de funciones usados por las aplicaciones existentes.
Las operaciones críticas verifican el resultado remoto y propagan errores.
"""

import json
import os
import tempfile
import time

import streamlit as st
from supabase import create_client

# Mantener la configuración actual del proyecto en esta fase.
SUPABASE_URL = "https://ipqcwszkjpswvajtnzhh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlwcWN3c3pranBzd3ZhanRuemhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2NjU4NTIsImV4cCI6MjEwODI0MTg1Mn0.tQvowfgPPisrCaP44FB1_l4zji6VtAdw-d8GtuHL7ow"

INTENTOS_VERIFICACION = 3
ESPERA_VERIFICACION = 0.6
EXTENSIONES_FOTO = (".jpg", ".jpeg", ".png")


def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _nombre_id_igual(a, b):
    return str(a) == str(b)


def _leer_filas_pedidos():
    """Lee filas de la tabla y propaga errores de conexión/consulta."""
    supabase = obtener_cliente()
    respuesta = supabase.table("pedidos").select("*").execute()
    filas = getattr(respuesta, "data", None)
    if filas is None:
        raise RuntimeError("Supabase no devolvió los pedidos en un formato válido.")
    return filas


def obtener_pedidos_nube():
    """Devuelve pedidos decodificados. Los errores de consulta se propagan."""
    pedidos = []
    for fila in _leer_filas_pedidos():
        try:
            datos = json.loads(fila["datos_json"])
            if isinstance(datos, dict):
                pedidos.append(datos)
        except (KeyError, TypeError, ValueError) as exc:
            # No ocultar una fila dañada: la app debe poder mostrar el problema.
            raise RuntimeError(
                f"No se pudo interpretar el pedido con ID '{fila.get('id', '?')}'."
            ) from exc
    return pedidos


def _obtener_pedido_verificado(pedido_id):
    pedidos = obtener_pedidos_nube()
    return next((p for p in pedidos if _nombre_id_igual(p.get("id"), pedido_id)), None)


def subir_pedido_nube(pedido_id, datos):
    """Guarda el pedido y verifica leyendo nuevamente su contenido."""
    if not isinstance(datos, dict):
        raise TypeError("Los datos del pedido deben ser un diccionario.")

    supabase = obtener_cliente()
    payload = {
        "id": pedido_id,
        "datos_json": json.dumps(datos, ensure_ascii=False),
    }
    supabase.table("pedidos").upsert(payload).execute()

    ultimo_error = None
    for intento in range(INTENTOS_VERIFICACION):
        try:
            guardado = _obtener_pedido_verificado(pedido_id)
            if guardado is not None:
                esperado = json.loads(payload["datos_json"])
                if guardado == esperado:
                    return True
                ultimo_error = RuntimeError("El pedido leído no coincide con los datos enviados.")
            else:
                ultimo_error = RuntimeError("El pedido no apareció al verificar el guardado.")
        except Exception as exc:
            ultimo_error = exc
        if intento < INTENTOS_VERIFICACION - 1:
            time.sleep(ESPERA_VERIFICACION)

    raise RuntimeError(f"No se pudo verificar el guardado del pedido '{pedido_id}'. Detalle: {ultimo_error}")


def obtener_fotos_nube_verificado(pedido_id):
    """Lista las fotos; propaga errores para no confundirlos con una carpeta vacía."""
    supabase = obtener_cliente()
    archivos = supabase.storage.from_("fotos").list(str(pedido_id))
    if archivos is None:
        raise RuntimeError("Supabase no devolvió una lista de fotos válida.")
    return [
        archivo["name"]
        for archivo in archivos
        if isinstance(archivo, dict)
        and isinstance(archivo.get("name"), str)
        and archivo["name"].lower().endswith(EXTENSIONES_FOTO)
    ]


def obtener_fotos_nube(pedido_id):
    """Función compatible con galerías antiguas: devuelve [] si hay error.

    Para borrados, subidas y verificaciones críticas se debe usar la función
    obtener_fotos_nube_verificado, que no oculta errores.
    """
    try:
        return obtener_fotos_nube_verificado(pedido_id)
    except Exception:
        return []


def subir_foto_nube(pedido_id, nombre_archivo, contenido_bytes):
    """Sube una foto, comprueba que aparezca en Storage y devuelve su URL pública."""
    if not contenido_bytes:
        raise ValueError("La fotografía está vacía y no se puede subir.")
    nombre_archivo = os.path.basename(str(nombre_archivo))
    if not nombre_archivo or nombre_archivo in (".", ".."):
        raise ValueError("El nombre de archivo no es válido.")

    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    ruta_temporal = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(nombre_archivo)[1] or ".jpg") as tmp:
        tmp.write(bytes(contenido_bytes))
        ruta_temporal = tmp.name

    try:
        with open(ruta_temporal, "rb") as archivo:
            supabase.storage.from_("fotos").upload(
                path=ruta_nube,
                file=archivo,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
    finally:
        if ruta_temporal and os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)

    ultimo_error = None
    for intento in range(INTENTOS_VERIFICACION):
        try:
            fotos = obtener_fotos_nube_verificado(pedido_id)
            if nombre_archivo in fotos:
                return supabase.storage.from_("fotos").get_public_url(ruta_nube)
            ultimo_error = RuntimeError("La foto todavía no aparece en la lista de Storage.")
        except Exception as exc:
            ultimo_error = exc
        if intento < INTENTOS_VERIFICACION - 1:
            time.sleep(ESPERA_VERIFICACION)
    raise RuntimeError(f"No se pudo confirmar la subida de '{nombre_archivo}'. Detalle: {ultimo_error}")


def descargar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{os.path.basename(str(nombre_archivo))}"
    resultado = supabase.storage.from_("fotos").download(ruta_nube)
    if resultado is None:
        raise RuntimeError(f"Supabase no devolvió el contenido de '{nombre_archivo}'.")
    return bytes(resultado)


def borrar_foto_nube(pedido_id, nombre_archivo):
    """Solicita el borrado y verifica que la foto ya no esté en Storage."""
    nombre_archivo = os.path.basename(str(nombre_archivo))
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    error_operacion = None
    try:
        supabase.storage.from_("fotos").remove([ruta_nube])
    except Exception as exc:
        # La respuesta puede fallar aunque el borrado sí se haya aplicado;
        # la verificación remota decide el resultado final.
        error_operacion = exc

    ultimo_error = error_operacion
    for intento in range(INTENTOS_VERIFICACION):
        try:
            if nombre_archivo not in obtener_fotos_nube_verificado(pedido_id):
                return True
            ultimo_error = RuntimeError("La foto todavía aparece en Storage.")
        except Exception as exc:
            ultimo_error = exc
        if intento < INTENTOS_VERIFICACION - 1:
            time.sleep(ESPERA_VERIFICACION)
    raise RuntimeError(f"No se pudo confirmar el borrado de '{nombre_archivo}'. Detalle: {ultimo_error}")


def borrar_pedido_nube(pedido_id):
    """Borra primero las fotos, verifica el bucket vacío y recién después el pedido."""
    supabase = obtener_cliente()
    fotos = obtener_fotos_nube_verificado(pedido_id)

    errores = []
    for nombre in fotos:
        try:
            borrar_foto_nube(pedido_id, nombre)
        except Exception as exc:
            errores.append(f"{nombre}: {exc}")

    # No eliminar el registro si alguna foto no pudo borrarse o no pudo verificarse.
    fotos_restantes = obtener_fotos_nube_verificado(pedido_id)
    if errores or fotos_restantes:
        detalle = "; ".join(errores) if errores else ", ".join(fotos_restantes)
        raise RuntimeError(
            "No se eliminó el pedido porque todavía hay fotos sin borrar o verificar. "
            f"Detalle: {detalle}"
        )

    supabase.table("pedidos").delete().eq("id", pedido_id).execute()

    # Confirmar que la fila realmente dejó de existir.
    respuesta = supabase.table("pedidos").select("id").eq("id", pedido_id).execute()
    filas = getattr(respuesta, "data", None)
    if filas is None:
        raise RuntimeError("El pedido fue enviado a borrar, pero no se pudo verificar el resultado.")
    if any(_nombre_id_igual(fila.get("id"), pedido_id) for fila in filas if isinstance(fila, dict)):
        raise RuntimeError(f"Supabase todavía conserva el pedido '{pedido_id}'.")
    return True
