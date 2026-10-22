import streamlit as st
from supabase import create_client
import json

# 🔥 PON AQUÍ TUS LLAVES DE SUPABASE
SUPABASE_URL = "https://ipqcwszkjpswvajtnzhh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlwcWN3c3pranBzd3ZhanRuemhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2NjU4NTIsImV4cCI6MjEwODI0MTg1Mn0.tQvowfgPPisrCaP44FB1_l4zji6VtAdw-d8GtuHL7ow"

def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funciones para Pedidos (Base de Datos) ---
import requests

def subir_pedido_nube(pedido_id, datos_dict):
    datos_json = json.dumps(datos_dict, ensure_ascii=False)
    
    # Construimos la URL de la API de Supabase
    url = f"{SUPABASE_URL}/rest/v1/pedidos"
    
    # Cabeceras: Autenticación y la clave para que NO devuelva el dato
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal" # 🔥 ESTO ES LO QUE SOLUCIONA EL ERROR
    }
    
    payload = {"id": pedido_id, "datos_json": datos_json}
    
    # Hacemos la petición POST directamente
    respuesta = requests.post(url, headers=headers, json=payload)
    
    # Si el pedido ya existe, hacemos un PATCH (actualizar)
    if respuesta.status_code == 409: # 409 es el código de "conflicto/duplicado"
        url_update = f"{url}?id=eq.{pedido_id}"
        requests.patch(url_update, headers=headers, json=payload)
    elif respuesta.status_code >= 400:
        # Si hay otro error, lo mostramos
        raise Exception(f"Error de Supabase: {respuesta.text}")

def obtener_pedidos_nube():
    supabase = obtener_cliente()
    respuesta = supabase.table("pedidos").select("*").execute()
    pedidos = []
    if respuesta.data:
        for fila in respuesta.data:
            try:
                pedidos.append(json.loads(fila["datos_json"]))
            except Exception:
                pass
    return pedidos

def borrar_pedido_nube(pedido_id):
    supabase = obtener_cliente()
    # Borramos las fotos del storage primero
    try:
        fotos = obtener_fotos_nube(pedido_id)
        if fotos:
            rutas = [f"{pedido_id}/{f}" for f in fotos]
            supabase.storage.from_("fotos").remove(rutas)
    except Exception:
        pass
    # Luego borramos el registro de la base de datos
    supabase.table("pedidos").delete().eq("id", pedido_id).execute()

# --- Funciones para Fotos (Storage) ---
def subir_foto_nube(pedido_id, nombre_archivo, contenido_bytes):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    # Subimos al balde "fotos"
    supabase.storage.from_("fotos").upload(ruta_nube, contenido_bytes, {"content-type": "image/jpeg"})
    return supabase.storage.from_("fotos").get_public_url(ruta_nube)

def obtener_fotos_nube(pedido_id):
    supabase = obtener_cliente()
    try:
        archivos = supabase.storage.from_("fotos").list(pedido_id)
        # Filtramos solo imágenes
        return [a['name'] for a in archivos if a['name'].endswith(('.jpg', '.jpeg', '.png'))]
    except Exception:
        return []

def descargar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    return supabase.storage.from_("fotos").download(ruta_nube)

def borrar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    # 🔥 Aquí estaba el error, faltaba cerrar el corchete y el paréntesis
    supabase.storage.from_("fotos").remove([ruta_nube])
