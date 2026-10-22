import streamlit as st
from supabase import create_client

# 🔥 PON AQUÍ TUS LLAVES DE SUPABASE
SUPABASE_URL = "https://ipqcwszkjpswvajtnzhh.supabase.co/rest/v1/"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlwcWN3c3pranBzd3ZhanRuemhoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2NjU4NTIsImV4cCI6MjEwODI0MTg1Mn0.tQvowfgPPisrCaP44FB1_l4zji6VtAdw-d8GtuHL7ow"

def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funciones para Pedidos (Base de Datos) ---
def subir_pedido_nube(pedido_id, datos_json):
    supabase = obtener_cliente()
    supabase.table("pedidos").upsert({"id": pedido_id, "datos_json": datos_json}).execute()

def obtener_pedidos_nube():
    supabase = obtener_cliente()
    respuesta = supabase.table("pedidos").select("*").execute()
    return respuesta.data

# --- Funciones para Fotos (Storage) ---
def subir_foto_nube(ruta_local, nombre_archivo, contenido_bytes):
    supabase = obtener_cliente()
    ruta_nube = f"{ruta_local}/{nombre_archivo}"
    # Subimos al balde "fotos"
    supabase.storage.from_("fotos").upload(ruta_nube, contenido_bytes, {"content-type": "image/jpeg"})
    return supabase.storage.from_("fotos").get_public_url(ruta_nube)

def obtener_fotos_nube(ruta_local):
    supabase = obtener_cliente()
    archivos = supabase.storage.from_("fotos").list(ruta_local)
    return [a['name'] for a in archivos if a['name'].endswith(('.jpg', '.jpeg', '.png'))]

def descargar_foto_nube(ruta_local, nombre_archivo):
    supabase = obtener_cliente()
    ruta_nube = f"{ruta_local}/{nombre_archivo}"
    return supabase.storage.from_("fotos").download(ruta_nube)