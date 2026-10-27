"""Conexión compartida con Supabase para la aplicación PC y la app móvil.

Las operaciones normales usan la clave anon. El borrado de pedidos completos usa
la service_role únicamente en el servidor, después de comprobar la sesión admin.
Nunca pongas SUPABASE_SERVICE_ROLE_KEY en el código ni en GitHub.
"""

import json
import os
import tempfile
import time
import hmac
from io import BytesIO
from PIL import Image, ImageOps

import streamlit as st
from supabase import create_client

SUPABASE_URL_PREDETERMINADA = "https://ipqcwszkjpswvajtnzhh.supabase.co"
INTENTOS_VERIFICACION = 3
ESPERA_VERIFICACION = 0.6
EXTENSIONES_FOTO = (".jpg", ".jpeg", ".png")


def _secreto(nombre, predeterminado=""):
    try:
        valor = st.secrets.get(nombre, predeterminado)
        return str(valor) if valor is not None else predeterminado
    except Exception:
        return predeterminado


def obtener_cliente():
    """Cliente normal para lectura/escritura de pedidos y fotos de operarios."""
    url = _secreto("SUPABASE_URL", SUPABASE_URL_PREDETERMINADA)
    clave = _secreto("SUPABASE_ANON_KEY")
    if not url or not clave:
        raise RuntimeError("Falta configurar SUPABASE_URL y SUPABASE_ANON_KEY en los Secrets de Streamlit.")
    return create_client(url, clave)


def _obtener_cliente_admin():
    """Cliente privilegiado: solo se usa en la operación administrativa protegida."""
    url = _secreto("SUPABASE_URL", SUPABASE_URL_PREDETERMINADA)
    clave = _secreto("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not clave:
        raise RuntimeError("Falta SUPABASE_SERVICE_ROLE_KEY en los Secrets de la app de PC. No se borró el pedido.")
    return create_client(url, clave)


def _nombre_id_igual(a, b):
    return str(a) == str(b)


def _leer_filas_pedidos(cliente=None):
    cliente = cliente or obtener_cliente()
    respuesta = cliente.table("pedidos").select("*").execute()
    filas = getattr(respuesta, "data", None)
    if filas is None:
        raise RuntimeError("Supabase no devolvió los pedidos en un formato válido.")
    return filas


def obtener_pedidos_nube():
    pedidos = []
    for fila in _leer_filas_pedidos():
        try:
            datos = json.loads(fila["datos_json"])
            if isinstance(datos, dict):
                pedidos.append(datos)
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"No se pudo interpretar el pedido con ID '{fila.get('id', '?')}'.") from exc
    return pedidos


def _obtener_pedido_verificado(pedido_id):
    pedidos = obtener_pedidos_nube()
    return next((p for p in pedidos if _nombre_id_igual(p.get("id"), pedido_id)), None)


def subir_pedido_nube(pedido_id, datos):
    if not isinstance(datos, dict):
        raise TypeError("Los datos del pedido deben ser un diccionario.")
    cliente = obtener_cliente()
    payload = {"id": pedido_id, "datos_json": json.dumps(datos, ensure_ascii=False)}
    cliente.table("pedidos").upsert(payload).execute()
    ultimo_error = None
    for intento in range(INTENTOS_VERIFICACION):
        try:
            guardado = _obtener_pedido_verificado(pedido_id)
            esperado = json.loads(payload["datos_json"])
            if guardado == esperado:
                return True
            ultimo_error = RuntimeError("El pedido leído no coincide con los datos enviados.")
        except Exception as exc:
            ultimo_error = exc
        if intento < INTENTOS_VERIFICACION - 1:
            time.sleep(ESPERA_VERIFICACION)
    raise RuntimeError(f"No se pudo verificar el guardado del pedido '{pedido_id}'. Detalle: {ultimo_error}")


def obtener_fotos_nube_verificado(pedido_id, cliente=None):
    cliente = cliente or obtener_cliente()
    archivos = cliente.storage.from_("fotos").list(str(pedido_id))
    if archivos is None:
        raise RuntimeError("Supabase no devolvió una lista de fotos válida.")
    return [a["name"] for a in archivos if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].lower().endswith(EXTENSIONES_FOTO)]


def obtener_fotos_nube(pedido_id):
    """Lista fotos; los errores de conexión se propagan y no se disfrazan como lista vacía."""
    return obtener_fotos_nube_verificado(pedido_id)


def _preparar_foto(nombre_archivo, contenido_bytes):
    """Normaliza archivos llamados .jpg a JPEG real y define su MIME correcto."""
    datos = bytes(contenido_bytes)
    extension = os.path.splitext(nombre_archivo)[1].lower()
    if extension in (".jpg", ".jpeg"):
        try:
            imagen = Image.open(BytesIO(datos))
            imagen = ImageOps.exif_transpose(imagen)
            if imagen.mode not in ("RGB",):
                imagen = imagen.convert("RGB")
            salida = BytesIO()
            imagen.save(salida, format="JPEG", quality=94, optimize=True)
            datos = salida.getvalue()
        except Exception as exc:
            raise ValueError(f"El archivo '{nombre_archivo}' no es una imagen válida: {exc}") from exc
        mime = "image/jpeg"
    elif extension == ".png":
        try:
            imagen = Image.open(BytesIO(datos))
            imagen.verify()
        except Exception as exc:
            raise ValueError(f"El archivo '{nombre_archivo}' no es un PNG válido: {exc}") from exc
        mime = "image/png"
    else:
        raise ValueError("Formato no admitido. Usa JPG, JPEG o PNG.")
    if not datos:
        raise ValueError("La fotografía está vacía y no se puede subir.")
    return datos, mime


def subir_foto_nube(pedido_id, nombre_archivo, contenido_bytes):
    """Sube una foto y confirma que existe en Storage; los fallos se informan al llamador."""
    if not contenido_bytes:
        raise ValueError("La fotografía está vacía y no se puede subir.")
    nombre_archivo = os.path.basename(str(nombre_archivo))
    if not nombre_archivo or nombre_archivo in (".", ".."):
        raise ValueError("El nombre de archivo no es válido.")
    contenido_preparado, mime = _preparar_foto(nombre_archivo, contenido_bytes)
    cliente = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    ruta_temporal = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(nombre_archivo)[1] or ".jpg") as tmp:
        tmp.write(contenido_preparado)
        ruta_temporal = tmp.name
    try:
        with open(ruta_temporal, "rb") as archivo:
            cliente.storage.from_("fotos").upload(
                path=ruta_nube,
                file=archivo,
                file_options={"content-type": mime, "upsert": "true"}
            )
    finally:
        if ruta_temporal and os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
    ultimo_error = None
    for intento in range(INTENTOS_VERIFICACION):
        try:
            if nombre_archivo in obtener_fotos_nube_verificado(pedido_id):
                return cliente.storage.from_("fotos").get_public_url(ruta_nube)
            ultimo_error = RuntimeError("La foto todavía no aparece en la lista de Storage.")
        except Exception as exc:
            ultimo_error = exc
        if intento < INTENTOS_VERIFICACION - 1:
            time.sleep(ESPERA_VERIFICACION)
    raise RuntimeError(f"No se pudo confirmar la subida de '{nombre_archivo}'. Detalle: {ultimo_error}")


def descargar_foto_nube(pedido_id, nombre_archivo):
    cliente = obtener_cliente()
    ruta_nube = f"{pedido_id}/{os.path.basename(str(nombre_archivo))}"
    resultado = cliente.storage.from_("fotos").download(ruta_nube)
    if resultado is None:
        raise RuntimeError(f"Supabase no devolvió el contenido de '{nombre_archivo}'.")
    return bytes(resultado)


def borrar_foto_nube(pedido_id, nombre_archivo):
    """Borra una foto usando permisos normales y confirma que desapareció."""
    nombre_archivo = os.path.basename(str(nombre_archivo))
    cliente = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    error_operacion = None
    try:
        cliente.storage.from_("fotos").remove([ruta_nube])
    except Exception as exc:
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


def borrar_pedido_nube_admin(pedido_id):
    """Borrado completo: requiere sesión admin y usa service_role solo en servidor."""
    if not st.session_state.get("admin_autenticado", False):
        raise PermissionError("Acceso denegado: inicia sesión como administrador antes de borrar un pedido.")
    if not pedido_id:
        raise ValueError("No se indicó un pedido válido.")

    cliente = _obtener_cliente_admin()
    # Primero se comprueba que el pedido exista. Si falla la lectura, no se borra nada.
    fila = cliente.table("pedidos").select("id").eq("id", pedido_id).execute()
    filas = getattr(fila, "data", None)
    if filas is None or not any(_nombre_id_igual(x.get("id"), pedido_id) for x in filas if isinstance(x, dict)):
        raise RuntimeError("El pedido no existe o no se pudo confirmar su existencia. No se realizó el borrado.")

    fotos = obtener_fotos_nube_verificado(pedido_id, cliente=cliente)
    errores = []
    for nombre in fotos:
        ruta = f"{pedido_id}/{os.path.basename(str(nombre))}"
        try:
            cliente.storage.from_("fotos").remove([ruta])
        except Exception as exc:
            errores.append(f"{nombre}: {exc}")

    fotos_restantes = obtener_fotos_nube_verificado(pedido_id, cliente=cliente)
    if errores or fotos_restantes:
        detalle = "; ".join(errores) if errores else ", ".join(fotos_restantes)
        raise RuntimeError("No se eliminó el registro porque quedan fotos sin borrar o verificar. Detalle: " + detalle)

    cliente.table("pedidos").delete().eq("id", pedido_id).execute()
    verificacion = cliente.table("pedidos").select("id").eq("id", pedido_id).execute()
    filas_finales = getattr(verificacion, "data", None)
    if filas_finales is None:
        raise RuntimeError("Se solicitó el borrado, pero no se pudo verificar el resultado en la tabla.")
    if any(_nombre_id_igual(x.get("id"), pedido_id) for x in filas_finales if isinstance(x, dict)):
        raise RuntimeError("Supabase todavía conserva el pedido. No repitas la operación sin revisar la tabla.")
    return True


def borrar_pedido_nube(pedido_id):
    """Compatibilidad segura: el borrado completo siempre exige autenticación admin."""
    return borrar_pedido_nube_admin(pedido_id)
