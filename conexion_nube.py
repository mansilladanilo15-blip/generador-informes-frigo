import streamlit as st
from supabase import create_client
import json
import requests
import tempfile
import os
import time

# 🔥 PON AQUÍ TUS LLAVES DE SUPABASE
SUPABASE_URL = "https://ipqcwszkjpswvajtnzhh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlwcWN3c3pranBzd3ZhanRuemhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2NjU4NTIsImV4cCI6MjEwODI0MTg1Mn0.tQvowfgPPisrCaP44FB1_l4zji6VtAdw-d8GtuHL7ow"

def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# FUNCIONES PARA PEDIDOS (BASE DE DATOS)
# ==========================================
def subir_pedido_nube(pedido_id, datos_dict):
    datos_json = json.dumps(datos_dict, ensure_ascii=False)
    url = f"{SUPABASE_URL}/rest/v1/pedidos"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    payload = {"id": pedido_id, "datos_json": datos_json}
    respuesta = requests.post(url, headers=headers, json=payload)
    
    if respuesta.status_code == 409:
        url_update = f"{url}?id=eq.{pedido_id}"
        requests.patch(url_update, headers=headers, json=payload)
    elif respuesta.status_code >= 400:
        raise Exception(f"Error {respuesta.status_code}: {respuesta.text}")

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
    try:
        fotos = obtener_fotos_nube(pedido_id)
        if fotos:
            rutas = [f"{pedido_id}/{f}" for f in fotos]
            supabase.storage.from_("fotos").remove(rutas)
    except Exception:
        pass
    supabase.table("pedidos").delete().eq("id", pedido_id).execute()

# ==========================================
# FUNCIONES PARA FOTOS (STORAGE)
# ==========================================
def subir_foto_nube(pedido_id, nombre_archivo, contenido_bytes):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    
    # 1. Creamos un archivo temporal real en el servidor
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(bytes(contenido_bytes))
        ruta_temporal = tmp.name
    
    try:
        # 2. Lo subimos usando upsert para sobrescribir si ya existe
        with open(ruta_temporal, "rb") as f:
            supabase.storage.from_("fotos").upload(
                path=ruta_nube,
                file=f,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": "true"  # 🔥 ESTO EVITA EL ERROR 409
                }
            )
    finally:
        # 3. Borramos el archivo temporal
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
        
    return supabase.storage.from_("fotos").get_public_url(ruta_nube)

def obtener_fotos_nube(pedido_id):
    supabase = obtener_cliente()
    try:
        archivos = supabase.storage.from_("fotos").list(pedido_id)
        return [a['name'] for a in archivos if a['name'].endswith(('.jpg', '.jpeg', '.png'))]
    except Exception:
        return []

def descargar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    resultado = supabase.storage.from_("fotos").download(ruta_nube)
    return bytes(resultado)

def borrar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    supabase.storage.from_("fotos").remove([ruta_nube])
