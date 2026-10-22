import streamlit as st
from supabase import create_client
import json

# 🔥 PON AQUÍ TUS LLAVES DE SUPABASE
SUPABASE_URL = "https://ipqcwszkjpswvajtnzhh.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlwcWN3c3pranBzd3ZhanRuemhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2NjU4NTIsImV4cCI6MjEwODI0MTg1Mn0.tQvowfgPPisrCaP44FB1_l4zji6VtAdw-d8GtuHL7ow"

def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funciones para Pedidos (Base de Datos) ---
def subir_pedido_nube(pedido_id, datos_dict):
    supabase = obtener_cliente()
    datos_json = json.dumps(datos_dict, ensure_ascii=False)
    
    try:
        # 🔥 Usamos insert en lugar de upsert. Esto evita que Supabase intente devolver el dato.
        # Al no intentar devolverlo, no necesita el permiso de SELECT que está causando el error.
        supabase.table("pedidos").insert({"id": pedido_id, "datos_json": datos_json}).execute()
    except Exception as e:
        # Si el error es porque el pedido ya existe (código 23505), entonces actualizamos.
        if "23505" in str(e) or "duplicate key" in str(e).lower():
            supabase.table("pedidos").update({"datos_json": datos_json}).eq("id", pedido_id).execute()
        else:
            # Si es otro error, lo lanzamos para que lo veas.
            raise e

def obtener_pedidos_nube():
    supabase = obtener_cliente()
    respuesta = supabase.table("pedidos").select("*").execute()
    pedidos = []
    for fila in respuesta.data:
        try:
            pedidos.append(json.loads(fila["datos_json"]))
        except:
            pass
    return pedidos

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
        return [a['name'] for a in archivos if a['name'].endswith(('.jpg', '.jpeg', '.png'))]
    except:
        return []

def descargar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    return supabase.storage.from_("fotos").download(ruta_nube)

def borrar_foto_nube(pedido_id, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{pedido_id}/{nombre_archivo}"
    supabase.storage.from_("fotos").remove([ruta_nube])
