import streamlit as st
from supabase import create_client
import json

# 🔥 PON AQUÍ TUS LLAVES DE SUPABASE
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_KEY = "TU-LLAVE-ANON-PUBLIC"

def obtener_cliente():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Funciones para Pedidos (Base de Datos) ---
def subir_pedido_nube(pedido_id, datos_dict):
    supabase = obtener_cliente()
    # Convertimos el diccionario a texto JSON para guardarlo en la columna "datos_json"
    datos_json = json.dumps(datos_dict, ensure_ascii=False)
    supabase.table("pedidos").upsert({"id": pedido_id, "datos_json": datos_json}).execute()

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
