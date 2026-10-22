import streamlit as st
import pandas as pd
from datetime import date, datetime
import base64
from io import BytesIO
from PIL import Image, ImageOps
import json
import os
import uuid
import re
import time
import sys
from pathlib import Path

# 🔥 ESTO LE DICE A STREAMLIT CLOUD DÓNDE ESTÁN TUS ARCHIVOS
sys.path.insert(0, str(Path(__file__).parent))

import config
from generador import generar_informe

st.set_page_config(page_title="Generador de Informes", page_icon="📄", layout="wide")

if "reinicio_count" not in st.session_state:
    st.session_state["reinicio_count"] = 0
RC = st.session_state["reinicio_count"]

st.title("📄 Generador de Informes de Pedidos y Traslados")

# ============ FUNCIONES AUXILIARES ============
def convertir_a_base64(bytes_imagen, max_ancho=800):
    try:
        img = Image.open(BytesIO(bytes_imagen))
        img = ImageOps.exif_transpose(img)
        if img.width > max_ancho:
            ratio = max_ancho / img.width
            img = img.resize((max_ancho, int(img.height * ratio)))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None

def cargar_fotos_de_carpeta(pedido_id):
    ruta_fotos = f"temp/pedidos/{pedido_id}/fotos"
    fotos = {"estibas": [], "camion": [], "termografo": [], "sello": [], "thermoking": [], "etiqueta": [], "documentacion": []}
    
    if not os.path.exists(ruta_fotos):
        return fotos
    
    for archivo in os.listdir(ruta_fotos):
        if archivo.endswith((".jpg", ".jpeg", ".png")):
            ruta_completa = os.path.join(ruta_fotos, archivo)
            with open(ruta_completa, "rb") as f:
                bytes_foto = f.read()
            
            nombre_lower = archivo.lower()
            
            if nombre_lower.startswith("documentacion_"):
                fotos["documentacion"].append({"nombre": archivo, "bytes": bytes_foto})
            elif nombre_lower.startswith("estiba_pata_"):
                pata_detectada = None
                match = re.search(r'pata_(\d+)', nombre_lower)
                if match: pata_detectada = int(match.group(1))
                fotos["estibas"].append({"nombre": archivo, "bytes": bytes_foto, "pata_sugerida": pata_detectada})
            elif nombre_lower.startswith("camion_"):
                fotos["camion"].append({"nombre": archivo, "bytes": bytes_foto})
            elif nombre_lower.startswith("termografo_"):
                fotos["termografo"].append({"nombre": archivo, "bytes": bytes_foto})
            elif nombre_lower.startswith("sello_"):
                fotos["sello"].append({"nombre": archivo, "bytes": bytes_foto})
            elif nombre_lower.startswith("thermoking_"):
                fotos["thermoking"].append({"nombre": archivo, "bytes": bytes_foto})
    
    return fotos

@st.dialog("🔍 Vista ampliada", width="large")
def mostrar_zoom(nombre_foto, bytes_foto):
    b64 = convertir_a_base64(bytes_foto, max_ancho=1600)
    if b64:
        st.markdown(f'<div style="text-align:center;"><img src="{b64}" style="max-width:100%; max-height:70vh; border:1px solid #ddd; border-radius:8px;"></div>', unsafe_allow_html=True)
        st.caption(f"📸 {nombre_foto}")
    if st.button("❌ Cerrar", use_container_width=True, key="close_modal"):
        st.rerun()

def renderizar_galeria(key, fotos, pedido_id, cols_num=4, pies_key=None, pie_default_func=None):
    resultado = []
    if not fotos: return resultado
    
    cols = st.columns(cols_num)
    for i, foto in enumerate(fotos):
        with cols[i % cols_num]:
            b64 = convertir_a_base64(foto["bytes"], max_ancho=400)
            if b64:
                st.markdown(f'<img src="{b64}" style="width:100%; border:1px solid #ddd; border-radius:6px; margin-bottom:6px;">', unsafe_allow_html=True)
            
            # --- BOTONES DE ACCIÓN (VER Y BORRAR) ---
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔍 Ver", key=f"{key}_zoom_{i}_{pedido_id}_{RC}", use_container_width=True):
                    mostrar_zoom(foto["nombre"], foto["bytes"])
            with col_btn2:
                if not bloqueado:
                    if st.button("🗑️ Borrar", key=f"{key}_del_{i}_{pedido_id}_{RC}", use_container_width=True):
                        ruta_archivo_real = f"temp/pedidos/{pedido_id}/fotos/{foto['nombre']}"
                        if os.path.exists(ruta_archivo_real):
                            os.remove(ruta_archivo_real)
                        st.session_state[f"fotos_{key}_data_{pedido_id}"].pop(i)
                        st.success("🗑️ Foto eliminada.")
                        st.rerun()

            # --- 🔥 SELECTOR PARA DERIVAR / MOVER FOTO ---
            if not bloqueado:
                opciones_destino = ["Mantener aquí", "Mover a Documentación", "Mover a Camión", "Mover a Termógrafo", "Mover a Sello", "Mover a Thermo-king"]
                # Si la foto ya está en un ítem, no mostramos la opción de moverlo a ese mismo ítem
                opciones_filtradas = [op for op in opciones_destino if op != f"Mover a {key.capitalize()}"]
                
                destino = st.selectbox(
                    "Mover foto a:", 
                    opciones_filtradas, 
                    key=f"derivar_{key}_{i}_{pedido_id}_{RC}", 
                    label_visibility="collapsed"
                )
                
                if destino != "Mantener aquí":
                    if st.button("➡️ Confirmar Mover", key=f"btn_mover_{key}_{i}_{pedido_id}_{RC}", use_container_width=True):
                        import shutil
                        prefijo_nuevo = {
                            "Mover a Documentación": "documentacion_",
                            "Mover a Camión": "camion_",
                            "Mover a Termógrafo": "termografo_",
                            "Mover a Sello": "sello_",
                            "Mover a Thermo-king": "thermoking_"
                        }[destino]
                        
                        nuevo_nombre = f"{prefijo_nuevo}{uuid.uuid4().hex[:6]}.jpg"
                        ruta_vieja = f"temp/pedidos/{pedido_id}/fotos/{foto['nombre']}"
                        ruta_nueva = f"temp/pedidos/{pedido_id}/fotos/{nuevo_nombre}"
                        
                        try:
                            if os.path.exists(ruta_vieja):
                                shutil.move(ruta_vieja, ruta_nueva)
                            
                            st.success(f"Foto movida a {destino}.")
                            # Recargamos todas las fotos para que aparezca en el nuevo ítem
                            fotos_actualizadas = cargar_fotos_de_carpeta(pedido_id)
                            for k, v in fotos_actualizadas.items():
                                st.session_state[f"fotos_{k}_data_{pedido_id}"] = v
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al mover: {e}")

            # --- PIE DE FOTO ---
            pie_calculado = pie_default_func(i) if pie_default_func else f"Foto {i+1}"
            if pies_key:
                if pies_key not in st.session_state: st.session_state[pies_key] = {}
                pie_guardado = st.session_state[pies_key].get(foto["nombre"])
                if pie_guardado is None:
                    st.session_state[pies_key][foto["nombre"]] = pie_calculado
            pie = st.text_input(f"Pie {i+1}", value=st.session_state[pies_key].get(foto["nombre"], pie_calculado) if pies_key else pie_calculado, disabled=bloqueado, key=f"{key}_pie_{i}_{pedido_id}_{RC}", label_visibility="collapsed")
            if pies_key: st.session_state[pies_key][foto["nombre"]] = pie
            resultado.append({"archivo": foto["bytes"], "pie": pie})
    return resultado
def val(key, default=""):
    ultimo_cargado = st.session_state.get("cargar_ultimo", {})
    v = ultimo_cargado.get(key, default)
    return default if v == "-" or v is None else v

# ============ GESTIÓN DE TRANSPORTES ============
RUTA_TRANSPORTES = "temp/transportes.json"
def cargar_transportes():
    if os.path.exists(RUTA_TRANSPORTES):
        with open(RUTA_TRANSPORTES, "r", encoding="utf-8") as f: return json.load(f)
    return []
def guardar_transporte(nombre):
    if not nombre.strip(): return
    transportes = cargar_transportes()
    if nombre not in transportes:
        transportes.append(nombre)
        transportes.sort()
        os.makedirs("temp", exist_ok=True)
        with open(RUTA_TRANSPORTES, "w", encoding="utf-8") as f: json.dump(transportes, f, ensure_ascii=False, indent=2)

# ============ GESTIÓN DE PEDIDOS ============
def mostrar_gestion_pedidos():
    st.subheader("📋 Gestión de Pedidos (Administrador)")
    
    tipo_pedido = st.radio("**Selecciona el tipo de pedido a crear:**", ["Pedido de venta", "Traslado"], horizontal=True)
    st.divider()

    lista_transportes = cargar_transportes()
    if not lista_transportes: lista_transportes = ["No asignado"]
    else: lista_transportes = ["No asignado"] + [t for t in lista_transportes if t != "No asignado"]

    with st.form("crear_pedido_form"):
        st.markdown(f"**Nuevo {tipo_pedido}**")
        col1, col2 = st.columns(2)
        
        if tipo_pedido == "Traslado":
            with col1:
                nuevo_nro = st.text_input("N° de Entrega *", placeholder="Ej: 80545555")
                nuevo_destino = st.text_input("Destino *", placeholder="Ej: Planta Dumestre")
            with col2:
                nuevo_transporte = st.selectbox("Transporte (Opcional)", lista_transportes, index=0)
        else:
            with col1:
                nuevo_nro = st.text_input("N° Pedido de Venta *", placeholder="Ej: PV157904")
                nuevo_cliente = st.text_input("Cliente *", placeholder="Ej: MAR E RIO")
            with col2:
                nuevo_transporte = st.selectbox("Transporte (Opcional)", lista_transportes, index=0)
                nuevo_nro_entrega = st.text_input("N° de Entrega (Opcional)", placeholder="Ej: 80545209")

        transporte_nuevo = st.text_input("¿Falta algún transporte? Escríbelo aquí (opcional)")
        crear = st.form_submit_button("➕ Crear Pedido", type="primary")
        
        if crear:
            if not nuevo_nro:
                st.error("⚠️ El número es obligatorio.")
            else:
                if tipo_pedido == "Traslado" and not nuevo_destino:
                    st.error("⚠️ El Destino es obligatorio para Traslados.")
                elif tipo_pedido == "Pedido de venta" and not nuevo_cliente:
                    st.error("⚠️ El Cliente es obligatorio para Pedidos de Venta.")
                else:
                    if transporte_nuevo.strip():
                        guardar_transporte(transporte_nuevo.strip())
                        nombre_transporte_final = transporte_nuevo.strip()
                    else:
                        nombre_transporte_final = nuevo_transporte

                    os.makedirs("temp/pedidos", exist_ok=True)
                    pedido_id = f"{nuevo_nro}_{uuid.uuid4().hex[:4]}"
                    os.makedirs(f"temp/pedidos/{pedido_id}", exist_ok=True)
                    
                    if tipo_pedido == "Traslado":
                        datos_pedido = {"id": pedido_id, "nro_pedido": nuevo_nro, "nro_entrega": nuevo_nro, "cliente": nuevo_destino, "destino": nuevo_destino, "tipo": tipo_pedido, "transporte": nombre_transporte_final, "estado": "Pendiente de fotos", "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"), "guia_despacho": "-", "chofer": "-", "patente_camion": "-", "patente_rampla": "-", "sello_final": "-", "sellos_provisorios": "-", "nro_termografo": "-"}
                    else:
                        nro_entrega_guardar = nuevo_nro_entrega.strip() if nuevo_nro_entrega.strip() else "-"
                        datos_pedido = {"id": pedido_id, "nro_pedido": nuevo_nro, "nro_entrega": nro_entrega_guardar, "cliente": nuevo_cliente, "destino": nuevo_cliente, "tipo": tipo_pedido, "transporte": nombre_transporte_final, "estado": "Pendiente de fotos", "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"), "guia_despacho": "-", "chofer": "-", "patente_camion": "-", "patente_rampla": "-", "sello_final": "-", "sellos_provisorios": "-", "nro_termografo": "-"}

                    with open(f"temp/pedidos/{pedido_id}/datos_pedido.json", "w", encoding="utf-8") as f:
                        json.dump(datos_pedido, f, ensure_ascii=False, indent=2)
                    
                    st.success(f"✅ {tipo_pedido} creado con éxito.")
                    st.rerun()

    st.divider()
    st.markdown("**Pedidos Existentes**")
    
    if os.path.exists("temp/pedidos"):
        pedidos = []
        for carpeta in os.listdir("temp/pedidos"):
            ruta_json = f"temp/pedidos/{carpeta}/datos_pedido.json"
            if os.path.exists(ruta_json):
                with open(ruta_json, "r", encoding="utf-8") as f:
                    pedidos.append(json.load(f))
        
        if pedidos:
            for p in pedidos:
                ruta_fotos = f"temp/pedidos/{p['id']}/fotos"
                cant_fotos = len(os.listdir(ruta_fotos)) if os.path.exists(ruta_fotos) else 0
                estado_json = p.get("estado", "Pendiente de fotos")
                estado_mostrar = f"🟢 {estado_json} ({cant_fotos} fotos)" if cant_fotos > 0 else "🟡 Sin fotos"
                
                col_a, col_b, col_c, col_d = st.columns([4, 2, 1, 1])
                with col_a: st.write(f"**{p['nro_pedido']}** - {p['cliente']} ({p['tipo']})")
                with col_b: st.write(estado_mostrar)
                
                with col_c:
                    if st.button("👁️", key=f"ver_{p['id']}", help="Ver / Editar Pedido", use_container_width=True):
                        for key in list(st.session_state.keys()):
                            if key.startswith("fotos_") or key.startswith("pies_") or key.startswith("resultados_ocr") or key.startswith("tabla_ocr"):
                                del st.session_state[key]
                        fotos_encontradas = cargar_fotos_de_carpeta(p["id"])
                        for k, v in fotos_encontradas.items():
                            st.session_state[f"fotos_{k}_data_{p['id']}"] = v
                        
                        st.session_state["cargar_ultimo"] = {
                            "empresa": "Australis Mar SA", 
                            "nro_pedido": p.get("nro_pedido", ""),
                            "tipo_informe": p.get("tipo", "Pedido de venta"), 
                            "cliente": p.get("cliente", ""),
                            "transporte": p.get("transporte", ""), 
                            "origen": "Planta Dumestre",
                            "nro_entrega": p.get("nro_entrega", ""),
                            "guia_despacho": p.get("guia_despacho", ""),
                            "chofer": p.get("chofer", ""),
                            "patente_camion": p.get("patente_camion", ""),
                            "patente_rampla": p.get("patente_rampla", ""),
                            "sello_final": p.get("sello_final", ""),
                            "sellos_provisorios": p.get("sellos_provisorios", ""),
                            "nro_termografo": p.get("nro_termografo", "")
                        }
                        
                        # 🔥 CARGAMOS LOS RESULTADOS DEL OCR GUARDADOS
                        if "resultados_ocr" in p:
                            st.session_state[f"resultados_ocr_{p['id']}"] = p["resultados_ocr"]
                        
                        st.session_state["pedido_actual_id"] = p["id"]
                        st.session_state["forzar_modo_informe"] = True
                        st.rerun()
                
                with col_d:
                    if st.button("🗑️", key=f"del_pedido_{p['id']}", help="Eliminar Pedido", use_container_width=True):
                        st.session_state[f"confirmar_borrar_{p['id']}"] = True
                        st.rerun()

                if st.session_state.get(f"confirmar_borrar_{p['id']}", False):
                    with st.container(border=True):
                        st.warning(f"⚠️ ¿Estás seguro que quieres eliminar el pedido **{p['nro_pedido']}**?")
                        col_si, col_no = st.columns(2)
                        with col_si:
                            if st.button("✅ Sí, eliminar", key=f"confirmar_si_{p['id']}", type="primary", use_container_width=True):
                                import shutil, time, stat
                                ruta_pedido_completa = f"temp/pedidos/{p['id']}"
                                if st.session_state.get("pedido_actual_id") == p["id"]:
                                    st.session_state["pedido_actual_id"] = None
                                    st.session_state["cargar_ultimo"] = {}
                                    for key in list(st.session_state.keys()):
                                        if key.startswith("fotos_") or key.startswith("pies_"): del st.session_state[key]
                                
                                def forzar_borrado(func, path, exc_info):
                                    try: os.chmod(path, stat.S_IWRITE); func(path)
                                    except Exception: pass
                                
                                if os.path.exists(ruta_pedido_completa):
                                    for _ in range(5):
                                        try: shutil.rmtree(ruta_pedido_completa, onerror=forzar_borrado); break
                                        except Exception: time.sleep(0.5)
                                
                                if f"confirmar_borrar_{p['id']}" in st.session_state: del st.session_state[f"confirmar_borrar_{p['id']}"]
                                st.success("Pedido eliminado.")
                                st.rerun()
                        with col_no:
                            if st.button("❌ Cancelar", key=f"cancelar_borrar_{p['id']}", use_container_width=True):
                                del st.session_state[f"confirmar_borrar_{p['id']}"]
                                st.rerun()
        else:
            st.info("No hay pedidos creados aún.")

# ============ ENRUTADOR ============
if st.session_state.get("forzar_modo_informe", False):
    st.session_state["selector_modo"] = "📄 Generar Informe (PC)"
    st.session_state["forzar_modo_informe"] = False
    st.session_state["reinicio_count"] += 1 
    st.rerun()

modo = st.radio("Selecciona el modo de trabajo:", ["📄 Generar Informe (PC)", "📋 Gestión de Pedidos"], horizontal=True, key="selector_modo")

if modo == "📋 Gestión de Pedidos":
    mostrar_gestion_pedidos()
    st.stop()

# ============ MODO INFORME ============
pedido_actual = st.session_state.get("pedido_actual_id", "")

estado_pedido_actual = "Pendiente"
if pedido_actual:
    ruta_json_estado = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
    if os.path.exists(ruta_json_estado):
        with open(ruta_json_estado, "r", encoding="utf-8") as f:
            estado_pedido_actual = json.load(f).get("estado", "Pendiente de fotos")

bloqueado = (estado_pedido_actual == "Finalizado")

with st.sidebar:
    st.subheader("⚡ Acciones rápidas")
    if st.button("🔄 Sincronizar fotos nuevas", type="primary", use_container_width=True):
        if pedido_actual:
            fotos_actualizadas = cargar_fotos_de_carpeta(pedido_actual)
            for k, v in fotos_actualizadas.items(): st.session_state[f"fotos_{k}_data_{pedido_actual}"] = v
            st.success("✅ Fotos sincronizadas.")
            st.rerun()
    if st.button("🧹 Reiniciar app", use_container_width=True):
        st.session_state["reinicio_count"] += 1
        for key in list(st.session_state.keys()):
            if key != "reinicio_count": del st.session_state[key]
        st.rerun()

    st.divider()
    st.subheader("📦 Pedidos de Operarios")
    
    if os.path.exists("temp/pedidos"):
        pedidos = []
        for carpeta in os.listdir("temp/pedidos"):
            ruta_json = f"temp/pedidos/{carpeta}/datos_pedido.json"
            if os.path.exists(ruta_json):
                with open(ruta_json, "r", encoding="utf-8") as f:
                    pedidos.append(json.load(f))
        
        pendientes = [p for p in pedidos if p.get("estado") != "Finalizado"]
        completados = [p for p in pedidos if p.get("estado") == "Finalizado"]

        with st.expander(f"🟡 Pendientes ({len(pendientes)})", expanded=True):
            for p in pendientes:
                if st.button(f"📄 {p['nro_pedido']} - {p['cliente']}", key=f"sb_pend_{p['id']}", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key.startswith("fotos_") or key.startswith("pies_") or key.startswith("resultados_ocr") or key.startswith("tabla_ocr"):
                            del st.session_state[key]
                    fotos_encontradas = cargar_fotos_de_carpeta(p["id"])
                    for k, v in fotos_encontradas.items(): 
                        st.session_state[f"fotos_{k}_data_{p['id']}"] = v
                    
                    st.session_state["cargar_ultimo"] = {
                        "empresa": "Australis Mar SA", "nro_pedido": p.get("nro_pedido", ""),
                        "tipo_informe": p.get("tipo", "Pedido de venta"), "cliente": p.get("cliente", ""),
                        "transporte": p.get("transporte", ""), "origen": "Planta Dumestre",
                        "nro_entrega": p.get("nro_entrega", ""), "guia_despacho": p.get("guia_despacho", ""),
                        "chofer": p.get("chofer", ""), "patente_camion": p.get("patente_camion", ""),
                        "patente_rampla": p.get("patente_rampla", ""), "sello_final": p.get("sello_final", ""),
                        "sellos_provisorios": p.get("sellos_provisorios", ""), "nro_termografo": p.get("nro_termografo", "")
                    }
                    # 🔥 CARGAMOS LOS RESULTADOS DEL OCR GUARDADOS
                    if "resultados_ocr" in p:
                        st.session_state[f"resultados_ocr_{p['id']}"] = p["resultados_ocr"]
                    
                    st.session_state["pedido_actual_id"] = p["id"]
                    st.session_state["reinicio_count"] += 1
                    st.rerun()
                
        with st.expander(f"🟢 Finalizados ({len(completados)})", expanded=True):
            for p in completados:
                if st.button(f"📄 {p['nro_pedido']} - {p['cliente']}", key=f"sb_comp_{p['id']}", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key.startswith("fotos_") or key.startswith("pies_") or key.startswith("resultados_ocr") or key.startswith("tabla_ocr"):
                            del st.session_state[key]
                    fotos_encontradas = cargar_fotos_de_carpeta(p["id"])
                    for k, v in fotos_encontradas.items(): st.session_state[f"fotos_{k}_data_{p['id']}"] = v
                    st.session_state["cargar_ultimo"] = {
                        "empresa": "Australis Mar SA", "nro_pedido": p.get("nro_pedido", ""),
                        "tipo_informe": p.get("tipo", "Pedido de venta"), "cliente": p.get("cliente", ""),
                        "transporte": p.get("transporte", ""), "origen": "Planta Dumestre",
                        "nro_entrega": p.get("nro_entrega", ""), "guia_despacho": p.get("guia_despacho", ""),
                        "chofer": p.get("chofer", ""), "patente_camion": p.get("patente_camion", ""),
                        "patente_rampla": p.get("patente_rampla", ""), "sello_final": p.get("sello_final", ""),
                        "sellos_provisorios": p.get("sellos_provisorios", ""), "nro_termografo": p.get("nro_termografo", "")
                    }
                    # 🔥 CARGAMOS LOS RESULTADOS DEL OCR GUARDADOS
                    if "resultados_ocr" in p:
                        st.session_state[f"resultados_ocr_{p['id']}"] = p["resultados_ocr"]
                    
                    st.session_state["pedido_actual_id"] = p["id"]
                    st.session_state["reinicio_count"] += 1
                    st.rerun()

    st.divider()
    st.subheader("📚 Historial de PDFs")
    import historial
    for inf in historial.obtener_todos(limite=5):
        if st.button(f"📄 {inf['nro_pedido']}", key=f"hist_{inf['id']}_{RC}", use_container_width=True):
            datos = historial.obtener_por_id(inf["id"])
            if datos: st.session_state["cargar_ultimo"] = datos; st.rerun()

# --- DATOS GENERALES ---
st.subheader("📋 Datos generales")

if bloqueado:
    st.warning("🔒 Este pedido está FINALIZADO. Los campos están bloqueados. Presiona 'Habilitar Pedido' al final para editar.")

with st.form("form_datos_pedido"):
    col1, col2, col3 = st.columns(3)
    with col1:
        empresa = st.text_input("Nombre de la empresa", value=val("empresa", "Australis Mar SA"), disabled=bloqueado, key=f"empresa_{pedido_actual}_{RC}")
        tipo_informe = st.selectbox("Tipo de informe", ["Pedido de venta", "Traslado"], index=0 if val("tipo_informe", "Pedido de venta") == "Pedido de venta" else 1, disabled=bloqueado, key=f"tipo_{pedido_actual}_{RC}")
        nro_pedido = st.text_input("N° Pedido *", value=val("nro_pedido", ""), disabled=bloqueado, key=f"nro_pedido_{pedido_actual}_{RC}")
    with col2:
        fecha = st.date_input("Fecha", value=date.today(), disabled=bloqueado, key=f"fecha_{pedido_actual}_{RC}")
        origen = st.text_input("Origen", value=val("origen", "Planta Dumestre"), disabled=bloqueado, key=f"origen_{pedido_actual}_{RC}")
        cliente = st.text_input("Cliente / Destino *", value=val("cliente", ""), disabled=bloqueado, key=f"cliente_{pedido_actual}_{RC}")
    with col3:
        nro_entrega = st.text_input("N° de entrega", value=val("nro_entrega", ""), disabled=bloqueado, key=f"nro_entrega_{pedido_actual}_{RC}")
        guia_despacho = st.text_input("Guía de despacho", value=val("guia_despacho", ""), disabled=bloqueado, key=f"guia_{pedido_actual}_{RC}")

    st.subheader("🚛 Datos del transporte")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        transporte = st.text_input("Transporte", value=val("transporte", ""), disabled=bloqueado, key=f"transporte_{pedido_actual}_{RC}")
        patente_camion = st.text_input("Patente Camión", value=val("patente_camion", ""), disabled=bloqueado, key=f"patente_camion_{pedido_actual}_{RC}")
        sello_final = st.text_input("Sello Final", value=val("sello_final", ""), disabled=bloqueado, key=f"sello_final_{pedido_actual}_{RC}")
    with col_t2:
        chofer = st.text_input("Chofer", value=val("chofer", ""), disabled=bloqueado, key=f"chofer_{pedido_actual}_{RC}")
        patente_rampla = st.text_input("Patente Rampla", value=val("patente_rampla", ""), disabled=bloqueado, key=f"patente_rampla_{pedido_actual}_{RC}")
        sellos_provisorios = st.text_input("Sellos Provisorios", value=val("sellos_provisorios", ""), disabled=bloqueado, key=f"sellos_provisorios_{pedido_actual}_{RC}")

    nro_termografo = st.text_input("N° Termógrafo", value=val("nro_termografo", ""), disabled=bloqueado, key=f"nro_termografo_{pedido_actual}_{RC}")

    if not bloqueado:
        guardar = st.form_submit_button("💾 Guardar cambios del pedido", type="primary", use_container_width=True)
        if guardar and pedido_actual:
            ruta_json = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
            if os.path.exists(ruta_json):
                with open(ruta_json, "r", encoding="utf-8") as f:
                    datos_p = json.load(f)
                
                datos_p["nro_entrega"] = nro_entrega.strip() if nro_entrega.strip() else "-"
                datos_p["transporte"] = transporte.strip() if transporte.strip() else "-"
                datos_p["cliente"] = cliente.strip() if cliente.strip() else datos_p.get("cliente", "")
                datos_p["nro_pedido"] = nro_pedido.strip() if nro_pedido.strip() else datos_p.get("nro_pedido", "")
                datos_p["guia_despacho"] = guia_despacho.strip() if guia_despacho.strip() else "-"
                datos_p["chofer"] = chofer.strip() if chofer.strip() else "-"
                datos_p["patente_camion"] = patente_camion.strip() if patente_camion.strip() else "-"
                datos_p["patente_rampla"] = patente_rampla.strip() if patente_rampla.strip() else "-"
                datos_p["sello_final"] = sello_final.strip() if sello_final.strip() else "-"
                datos_p["sellos_provisorios"] = sellos_provisorios.strip() if sellos_provisorios.strip() else "-"
                datos_p["nro_termografo"] = nro_termografo.strip() if nro_termografo.strip() else "-"
                
                with open(ruta_json, "w", encoding="utf-8") as f:
                    json.dump(datos_p, f, ensure_ascii=False, indent=2)
                
                st.success("✅ Datos guardados correctamente.")
                st.rerun()

# --- FOTOS ---
st.subheader("📷 Registro fotográfico")

# 0. DOCUMENTACIÓN (CON SELECTOR PARA DERIVAR)
with st.expander("0. Documentación (Cámara y Rampla) - No sale en PDF", expanded=False):
    ruta_doc = f"temp/pedidos/{pedido_actual}/fotos" if pedido_actual else ""
    fotos_doc = [f for f in os.listdir(ruta_doc) if f.startswith("documentacion_")] if os.path.exists(ruta_doc) else []
    
    if fotos_doc:
        st.success(f"✅ {len(fotos_doc)} fotos de documentación cargadas")
        cols = st.columns(4)
        for idx, f in enumerate(fotos_doc):
            with cols[idx % 4]:
                ruta_img = os.path.join(ruta_doc, f)
                try:
                    with open(ruta_img, "rb") as img_file:
                        bytes_img = img_file.read()
                    b64 = convertir_a_base64(bytes_img, max_ancho=400)
                    if b64:
                        st.markdown(
                            f'<div style="text-align:center;">'
                            f'<img src="{b64}" style="width:100%; border:1px solid #ddd; border-radius:6px; margin-bottom:5px;">'
                            f'<div style="font-size:11px; color:#666;">{f}</div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                except Exception as e:
                    st.error(f"⚠️ No se pudo leer {f}: {e}")
                
                # 🔥 SELECTOR PARA DERIVAR FOTO (SOLO SI NO ESTÁ BLOQUEADO)
                if not bloqueado:
                    opciones_destino = ["Mantener aquí", "Mover a Estibas", "Mover a Camión", "Mover a Termógrafo", "Mover a Sello", "Mover a Thermo-king"]
                    destino = st.selectbox(
                        "Mover a:", 
                        opciones_destino, 
                        key=f"derivar_doc_{f}_{pedido_actual}", 
                        label_visibility="collapsed"
                    )
                    
                    if destino != "Mantener aquí":
                        if st.button("➡️ Confirmar", key=f"btn_mover_doc_{f}_{pedido_actual}", use_container_width=True):
                            import shutil
                            prefijo_nuevo = {
                                "Mover a Estibas": "estiba_pata_99", # 99 es temporal, se puede ajustar en la tabla del OCR
                                "Mover a Camión": "camion_",
                                "Mover a Termógrafo": "termografo_",
                                "Mover a Sello": "sello_",
                                "Mover a Thermo-king": "thermoking_"
                            }[destino]
                            
                            # Generamos el nuevo nombre
                            if destino == "Mover a Estibas":
                                nuevo_nombre = f"estiba_pata_99.jpg" # Temporal
                            else:
                                nuevo_nombre = f"{prefijo_nuevo}{uuid.uuid4().hex[:6]}.jpg"
                            
                            ruta_vieja = os.path.join(ruta_doc, f)
                            ruta_nueva = os.path.join(ruta_doc, nuevo_nombre)
                            
                            try:
                                shutil.move(ruta_vieja, ruta_nueva)
                                st.success(f"✅ Foto movida a {destino}.")
                                # Recargar fotos
                                fotos_actualizadas = cargar_fotos_de_carpeta(pedido_actual)
                                for k, v in fotos_actualizadas.items():
                                    st.session_state[f"fotos_{k}_data_{pedido_actual}"] = v
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al mover: {e}")
    else:
        st.info("No hay fotos de documentación subidas desde la App Móvil.")
# 1. ESTIBAS
with st.expander("1️⃣ Fotos Estibas", expanded=True):
    if st.session_state.get(f"fotos_estibas_data_{pedido_actual}"):
        st.success("✅ Fotos cargadas desde la App Móvil")
        
        df_estibas = pd.DataFrame([{"archivo": f["nombre"], "pata_sugerida": f.get("pata_sugerida")} for f in st.session_state[f"fotos_estibas_data_{pedido_actual}"]])
        
        if st.button("🔍 Analizar con OCR", type="secondary", key=f"btn_ocr_{pedido_actual}_{RC}", disabled=bloqueado):
            with st.spinner("Analizando fotos con OCR... ⏳"):
                try:
                    from ocr_bridge import analizar_fotos
                    fotos_para_ocr = [(f["nombre"], f["bytes"]) for f in st.session_state[f"fotos_estibas_data_{pedido_actual}"]]
                    resultados = analizar_fotos(fotos_para_ocr)
                    
                    for r in resultados:
                        for f in st.session_state[f"fotos_estibas_data_{pedido_actual}"]:
                            if r["archivo"] == f["nombre"]:
                                r["pata_operario"] = f.get("pata_sugerida")
                                if r["pata"] is None:
                                    r["pata"] = f.get("pata_sugerida")
                                break
                                
                    st.session_state[f"resultados_ocr_{pedido_actual}"] = resultados
                    
                    # 🔥 GUARDAMOS LOS RESULTADOS DEL OCR EN EL JSON DEL PEDIDO
                    ruta_json = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
                    if os.path.exists(ruta_json):
                        with open(ruta_json, "r", encoding="utf-8") as f: datos_p = json.load(f)
                        datos_p["resultados_ocr"] = resultados
                        with open(ruta_json, "w", encoding="utf-8") as f: json.dump(datos_p, f, ensure_ascii=False, indent=2)
                    
                    st.rerun()
                except Exception as e: 
                    st.error(f"❌ Error en OCR: {e}")

        if f"resultados_ocr_{pedido_actual}" in st.session_state and st.session_state[f"resultados_ocr_{pedido_actual}"]:
            st.markdown("### 📋 Revisión y Corrección")
            st.info("Compara la 'Pata Operario' con la 'Pata OCR'. Si hay diferencias, corrige la columna final.")
            
            col_tabla, col_preview = st.columns([2, 1])
            
            data_editor = []
            for r in st.session_state[f"resultados_ocr_{pedido_actual}"]:
                data_editor.append({
                    "Borrar": False, # 🔥 NUEVA COLUMNA PARA MARCAR SI SE QUIERE BORRAR
                    "Archivo": r["archivo"],
                    "Pata Operario": r.get("pata_operario"),
                    "Pata OCR": r.get("pata"),
                    "Pata Final (Editable)": r.get("pata"),
                    "Cajas": r.get("total_cajas"),
                    "Confianza": f"{r.get('confianza', 0):.0%}"
                })
            df_final = pd.DataFrame(data_editor)

            with col_tabla:
                df_editado = st.data_editor(
                    df_final,
                    use_container_width=True,
                    column_config={
                        "Borrar": st.column_config.CheckboxColumn("🗑️", help="Marca para eliminar esta foto"),
                        "Pata Final (Editable)": st.column_config.NumberColumn("Pata Final (Editable)", min_value=1),
                        "Cajas": st.column_config.NumberColumn("Cajas", min_value=0),
                    },
                    key=f"editor_ocr_{pedido_actual}_{RC}",
                    disabled=bloqueado
                )
                st.session_state[f"tabla_ocr_editada_{pedido_actual}"] = df_editado
                
                # 🔥 LÓGICA PARA ELIMINAR LAS FOTOS MARCADAS
                if not bloqueado and df_editado["Borrar"].any():
                    if st.button("🗑️ Eliminar fotos seleccionadas", type="primary", use_container_width=True):
                        archivos_a_borrar = df_editado[df_editado["Borrar"] == True]["Archivo"].tolist()
                        
                        for archivo in archivos_a_borrar:
                            # 1. Borrar el archivo físico del disco
                            ruta_archivo = f"temp/pedidos/{pedido_actual}/fotos/{archivo}"
                            if os.path.exists(ruta_archivo):
                                os.remove(ruta_archivo)
                            
                            # 2. Eliminarlo de la lista de resultados del OCR
                            st.session_state[f"resultados_ocr_{pedido_actual}"] = [
                                r for r in st.session_state[f"resultados_ocr_{pedido_actual}"] 
                                if r["archivo"] != archivo
                            ]
                            
                            # 3. Eliminarlo de la lista de fotos cargadas
                            if f"fotos_estibas_data_{pedido_actual}" in st.session_state:
                                st.session_state[f"fotos_estibas_data_{pedido_actual}"] = [
                                    f for f in st.session_state[f"fotos_estibas_data_{pedido_actual}"]
                                    if f["nombre"] != archivo
                                ]
                        
                        # 4. Guardar el JSON actualizado
                        ruta_json = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
                        if os.path.exists(ruta_json):
                            with open(ruta_json, "r", encoding="utf-8") as f: datos_p = json.load(f)
                            datos_p["resultados_ocr"] = st.session_state[f"resultados_ocr_{pedido_actual}"]
                            with open(ruta_json, "w", encoding="utf-8") as f: json.dump(datos_p, f, ensure_ascii=False, indent=2)
                        
                        st.success(f"✅ Se eliminaron {len(archivos_a_borrar)} fotos.")
                        time.sleep(1)
                        st.rerun()
                
                if not df_editado.empty:
                    total_patas = len(df_editado)
                    total_cajas = int(df_editado["Cajas"].fillna(0).sum())
                    st.info(f"📦 **Resumen:** {total_patas} Patas registradas | **Total Cajas:** {total_cajas}")
                
                st.markdown("---")
                st.markdown("**🔍 Selecciona una foto para ver el detalle:**")
                archivos_disponibles = list(df_final["Archivo"].values)
                archivo_seleccionado = st.selectbox(
                    "Selecciona una foto:", 
                    archivos_disponibles, 
                    label_visibility="collapsed",
                    key=f"selector_preview_ocr_{pedido_actual}_{RC}"
                )

            with col_preview:
                st.markdown("#### 🖼️ Vista Previa")
                
                if archivo_seleccionado:
                    foto_encontrada = None
                    for f in st.session_state[f"fotos_estibas_data_{pedido_actual}"]:
                        if f["nombre"] == archivo_seleccionado:
                            foto_encontrada = f
                            break
                    
                    if foto_encontrada:
                        b64 = convertir_a_base64(foto_encontrada["bytes"], max_ancho=800)
                        if b64:
                            st.markdown(
                                f'<div style="text-align:center;">'
                                f'<img src="{b64}" style="width:100%; border:1px solid #ddd; border-radius:6px;">'
                                f'</div>',
                                unsafe_allow_html=True
                            )
                            st.caption(f"📸 {archivo_seleccionado}")
                            
                            if st.button("🔍 Ver a pantalla completa", use_container_width=True, key=f"btn_fullscreen_{pedido_actual}_{RC}"):
                                mostrar_zoom(archivo_seleccionado, foto_encontrada["bytes"])
                            
                            for r in st.session_state[f"resultados_ocr_{pedido_actual}"]:
                                if r["archivo"] == archivo_seleccionado:
                                    with st.expander("🔤 Texto detectado por el OCR"):
                                        st.write(r.get("texto_crudo", "No hay texto."))
                                    break
                        else:
                            st.error("⚠️ No se pudo cargar la imagen.")
            
            st.divider()
            st.checkbox("✅ Cierro registro fotográfico y genero PDF", key=f"ocr_validado_{pedido_actual}_{RC}", disabled=bloqueado)
    else:
        st.info("No hay fotos de estiba cargadas en el pedido todavía.")

    # SUBIDA MANUAL MASIVA
    if not bloqueado:
        st.markdown("---")
        st.markdown("### 📤 Subida Manual de Estibas (El OCR asignará las patas)")
        st.info("Sube todas las fotos aquí. La app leerá el cartel de cada una y las guardará en la pata que corresponda, actualizando la App Móvil.")

        fotos_manuales = st.file_uploader("Selecciona las fotos de estiba", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key=f"up_manual_estiba_{pedido_actual}_{RC}")
        
        if fotos_manuales:
            if st.button("🚀 Procesar con OCR y Guardar en App Móvil", type="primary", use_container_width=True):
                with st.spinner("El OCR está leyendo los carteles y ordenando las fotos... ⏳"):
                    try:
                        from ocr_bridge import analizar_fotos
                        import time
                        
                        fotos_para_ocr = [(f.name, f.getvalue()) for f in fotos_manuales]
                        resultados = analizar_fotos(fotos_para_ocr)
                        
                        mapa_bytes = {f.name: f.getvalue() for f in fotos_manuales}
                        
                        ruta_fotos = f"temp/pedidos/{pedido_actual}/fotos"
                        os.makedirs(ruta_fotos, exist_ok=True)
                        
                        patas_guardadas = 0
                        
                        for r in resultados:
                            nombre_original = r["archivo"]
                            pata_detectada = r.get("pata")
                            
                            if pata_detectada and nombre_original in mapa_bytes:
                                nuevo_nombre = f"estiba_pata_{pata_detectada}.jpg"
                                ruta_guardado = os.path.join(ruta_fotos, nuevo_nombre)
                                
                                with open(ruta_guardado, "wb") as file:
                                    file.write(mapa_bytes[nombre_original])
                                    file.flush()
                                
                                patas_guardadas += 1
                            else:
                                st.warning(f"⚠️ No se pudo detectar la pata para '{nombre_original}'. Se guardará como 'pata_99'.")
                                nuevo_nombre = f"estiba_pata_99.jpg"
                                ruta_guardado = os.path.join(ruta_fotos, nuevo_nombre)
                                with open(ruta_guardado, "wb") as file:
                                    file.write(mapa_bytes[nombre_original])
                        
                        fotos_actualizadas = cargar_fotos_de_carpeta(pedido_actual)
                        for k, v in fotos_actualizadas.items():
                            st.session_state[f"fotos_{k}_data_{pedido_actual}"] = v
                        
                        st.success(f"✅ ¡Listo! Se guardaron {patas_guardadas} fotos y se actualizó la App Móvil.")
                        time.sleep(1.5)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al procesar las fotos: {e}")

# FUNCIÓN PARA OTRAS CATEGORÍAS
def seccion_fotos_extra(nombre_key, titulo, pedido_id):
    with st.expander(titulo, expanded=True):
        if st.session_state.get(f"fotos_{nombre_key}_data_{pedido_id}"):
            st.success("✅ Fotos cargadas")
            renderizar_galeria(nombre_key, st.session_state[f"fotos_{nombre_key}_data_{pedido_id}"], pedido_id, cols_num=4, pies_key=f"pies_{nombre_key}_{pedido_id}")
        
        if not bloqueado:
            st.markdown("**Subir más fotos manualmente:**")
            nuevas_raw = st.file_uploader(f"Subir fotos extra ({nombre_key})", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key=f"up_{nombre_key}_{pedido_id}_{RC}")
            if nuevas_raw:
                for f in nuevas_raw:
                    if f"fotos_{nombre_key}_data_{pedido_id}" not in st.session_state: 
                        st.session_state[f"fotos_{nombre_key}_data_{pedido_id}"] = []
                    st.session_state[f"fotos_{nombre_key}_data_{pedido_id}"].append({"nombre": f.name, "bytes": f.getvalue()})
                st.rerun()
        else:
            st.info("🔒 Las fotos están bloqueadas porque el pedido está finalizado.")

seccion_fotos_extra("camion", "2️⃣ Fotos Camión", pedido_actual)
seccion_fotos_extra("termografo", "3️⃣ Termógrafo", pedido_actual)
seccion_fotos_extra("sello", "4️⃣ Sello/s", pedido_actual)
seccion_fotos_extra("thermoking", "5️⃣ Thermo-king", pedido_actual)

st.divider()

# BOTÓN GENERAR INFORME
col_fin1, col_fin2 = st.columns([1, 1])
with col_fin1:
    if st.button("🚀 Generar informe PDF", type="primary", use_container_width=True, key=f"btn_generar_{pedido_actual}_{RC}"):
        if not nro_pedido.strip() and not nro_entrega.strip():
            st.error("⚠️ Debes ingresar al menos el N° de Pedido o el N° de Entrega.")
        else:
            with st.spinner("Generando PDF... ⏳"):
                try:
                    datos_cabecera = {
                        "pedido_id": pedido_actual,
                        "empresa": empresa.strip(), "nro_pedido": nro_pedido.strip() or "-",
                        "tipo_informe": tipo_informe, "fecha": fecha.strftime("%d/%m/%Y"),
                        "origen": origen.strip(), "cliente": cliente.strip(),
                        "nro_entrega": nro_entrega.strip() or "-", "guia_despacho": guia_despacho.strip() or "-",
                        "transporte": transporte.strip() or "-", "chofer": chofer.strip() or "-",
                        "patente_camion": patente_camion.strip() or "-", "patente_rampla": patente_rampla.strip() or "-",
                        "sello_final": sello_final.strip() or "-", "sellos_provisorios": sellos_provisorios.strip() or "-",
                        "nro_termografo": nro_termografo.strip() or "-",
                    }

                    def preparar_fotos(fotos_data, pies_key):
                        resultado = []
                        for foto in fotos_data:
                            pie = st.session_state.get(pies_key, {}).get(foto["nombre"], "Foto")
                            resultado.append({"archivo": foto["bytes"], "pie": pie})
                        return resultado

                    # Preparar estibas ORDENADAS por pata
                    fotos_estibas_ordenadas = []
                    if f"tabla_ocr_editada_{pedido_actual}" in st.session_state and not st.session_state[f"tabla_ocr_editada_{pedido_actual}"].empty:
                        # 🔥 ORDENAMOS LA TABLA POR LA COLUMNA "Pata Final (Editable)"
                        df_ordenado = st.session_state[f"tabla_ocr_editada_{pedido_actual}"].copy()
                        df_ordenado["Pata Final (Editable)"] = pd.to_numeric(df_ordenado["Pata Final (Editable)"], errors='coerce').fillna(999)
                        df_ordenado = df_ordenado.sort_values(by="Pata Final (Editable)")
                        
                        mapa_bytes = {f["nombre"]: f["bytes"] for f in st.session_state.get(f"fotos_estibas_data_{pedido_actual}", [])}
                        
                        for _, row in df_ordenado.iterrows():
                            nombre_archivo = row["Archivo"]
                            pata_final = row.get("Pata Final (Editable)")
                            cajas = row.get("Cajas")
                            if nombre_archivo in mapa_bytes:
                                pie = f"Pata {int(pata_final)} - {cajas} cajas" if pata_final and cajas else f"Pata {int(pata_final)}"
                                fotos_estibas_ordenadas.append({"archivo": mapa_bytes[nombre_archivo], "pie": pie})
                    else:
                        # Si no hay tabla OCR, ordenamos por el nombre del archivo
                        fotos_sueltas = st.session_state.get(f"fotos_estibas_data_{pedido_actual}", [])
                        fotos_sueltas_ordenadas = sorted(fotos_sueltas, key=lambda x: x.get('pata_sugerida', 999))
                        for f in fotos_sueltas_ordenadas:
                            pie = f"Pata {f.get('pata_sugerida')}" if f.get('pata_sugerida') else "Foto Estiba"
                            fotos_estibas_ordenadas.append({"archivo": f["bytes"], "pie": pie})

                    # Preparar termógrafo con número
                    fotos_termografo_preparadas = []
                    for idx, foto in enumerate(st.session_state.get(f"fotos_termografo_data_{pedido_actual}", [])):
                        if nro_termografo and nro_termografo.strip():
                            pie = nro_termografo.strip() if idx == 0 else f"{nro_termografo.strip()} ({idx + 1})"
                        else:
                            pie = f"Foto {idx + 1}"
                        fotos_termografo_preparadas.append({"archivo": foto["bytes"], "pie": pie})

                    fotos_por_categoria = {
                        "estibas": fotos_estibas_ordenadas,
                        "camion": preparar_fotos(st.session_state.get(f"fotos_camion_data_{pedido_actual}", []), f"pies_camion_{pedido_actual}"),
                        "termografo": fotos_termografo_preparadas,
                        "sello": preparar_fotos(st.session_state.get(f"fotos_sello_data_{pedido_actual}", []), f"pies_sello_{pedido_actual}"),
                        "thermoking": preparar_fotos(st.session_state.get(f"fotos_thermoking_data_{pedido_actual}", []), f"pies_thermoking_{pedido_actual}"),
                        "etiqueta": preparar_fotos(st.session_state.get(f"fotos_etiqueta_data_{pedido_actual}", []), f"pies_etiqueta_{pedido_actual}"),
                    }

                    filas_estibas = []
                    if f"tabla_ocr_editada_{pedido_actual}" in st.session_state and not st.session_state[f"tabla_ocr_editada_{pedido_actual}"].empty:
                        # 🔥 ORDENAMOS LA TABLA POR EL NÚMERO DE PATA ANTES DE ARMAR EL PDF
                        df_para_pdf = st.session_state[f"tabla_ocr_editada_{pedido_actual}"].copy()
                        df_para_pdf["Pata Final (Editable)"] = pd.to_numeric(df_para_pdf["Pata Final (Editable)"], errors='coerce').fillna(999)
                        df_para_pdf["Cajas"] = pd.to_numeric(df_para_pdf["Cajas"], errors='coerce').fillna(0)
                        df_para_pdf = df_para_pdf.sort_values(by="Pata Final (Editable)")
                        
                        for _, row in df_para_pdf.iterrows():
                            pata = row.get("Pata Final (Editable)")
                            cajas = row.get("Cajas")
                            if pata and cajas:
                                filas_estibas.append({"cantidad": str(int(cajas)), "pata": int(pata)})

                    ruta_pdf = generar_informe(datos_cabecera, fotos_por_categoria, filas_estibas)
                    
                    st.success(f"✅ ¡Informe generado con éxito! ({ruta_pdf.name})")
                    with open(ruta_pdf, "rb") as f:
                        st.download_button("⬇️ Descargar PDF", data=f.read(), file_name=ruta_pdf.name, mime="application/pdf", use_container_width=True)
                except Exception as e:
                    st.error(f"❌ Error al generar el PDF: {e}")

with col_fin2:
    if pedido_actual:
        if not bloqueado:
            if st.button("✅ Marcar Pedido como FINALIZADO", type="secondary", use_container_width=True):
                ruta_json = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
                if os.path.exists(ruta_json):
                    with open(ruta_json, "r", encoding="utf-8") as f: datos_p = json.load(f)
                    datos_p["estado"] = "Finalizado"
                    with open(ruta_json, "w", encoding="utf-8") as f: json.dump(datos_p, f, ensure_ascii=False, indent=2)
                    st.success("🎉 Pedido marcado como FINALIZADO.")
                    st.rerun()
        else:
            if st.button("🔓 Habilitar Pedido (Reabrir)", type="primary", use_container_width=True):
                ruta_json = f"temp/pedidos/{pedido_actual}/datos_pedido.json"
                if os.path.exists(ruta_json):
                    with open(ruta_json, "r", encoding="utf-8") as f: datos_p = json.load(f)
                    datos_p["estado"] = "Pendiente de fotos"
                    with open(ruta_json, "w", encoding="utf-8") as f: json.dump(datos_p, f, ensure_ascii=False, indent=2)
                    st.success("🔓 Pedido habilitado nuevamente.")
                    st.rerun()
