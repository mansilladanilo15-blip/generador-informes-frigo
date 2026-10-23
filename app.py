import streamlit as st
import pandas as pd
from datetime import date, datetime
import base64
from io import BytesIO
from PIL import Image, ImageOps
import uuid
import time
import conexion_nube as nube

import config
from generador import generar_informe

st.set_page_config(page_title="Generador de Informes", page_icon="📄", layout="wide")

if "reinicio_count" not in st.session_state:
    st.session_state["reinicio_count"] = 0
if "fotos_ocultas" not in st.session_state:
    st.session_state["fotos_ocultas"] = set()

RC = st.session_state["reinicio_count"]

st.title("📄 Generador de Informes de Pedidos y Traslados")

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
        return f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
    except:
        return None

@st.dialog("🔍 Vista ampliada", width="large")
def mostrar_zoom(nombre_foto, bytes_foto):
    b64 = convertir_a_base64(bytes_foto, max_ancho=1600)
    if b64:
        st.markdown(f'<div style="text-align:center;"><img src="{b64}" style="max-width:100%; max-height:70vh; border:1px solid #ddd; border-radius:8px;"></div>', unsafe_allow_html=True)
        st.caption(f"📸 {nombre_foto}")
    if st.button("❌ Cerrar", width="stretch", key="close_modal"):
        st.rerun()

def renderizar_galeria(key, fotos, pedido_id, cols_num=4):
    fotos = [f for f in fotos if f not in st.session_state["fotos_ocultas"]]
    if not fotos: return
    cols = st.columns(cols_num)
    for i, f in enumerate(fotos):
        with cols[i % cols_num]:
            img_placeholder = st.empty()
            try:
                bytes_img = nube.descargar_foto_nube(pedido_id, f)
                b64 = convertir_a_base64(bytes_img, max_ancho=400)
                if b64:
                    img_placeholder.markdown(f'<img src="{b64}" style="width:100%; border:1px solid #ddd; border-radius:6px; margin-bottom:6px;">', unsafe_allow_html=True)
            except Exception:
                img_placeholder.warning("⚠️ Error al cargar")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Ver", key=f"{key}_zoom_{i}_{RC}_{f}", width="stretch"):
                    mostrar_zoom(f, bytes_img)
            with col2:
                if st.button("🗑️ Borrar", key=f"{key}_del_{i}_{RC}_{f}", width="stretch"):
                    with st.spinner("Borrando..."):
                        nube.borrar_foto_nube(pedido_id, f)
                        st.session_state["fotos_ocultas"].add(f)
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()

            opciones = ["Mantener aquí", "Mover a Documentación", "Mover a Camión", "Mover a Termógrafo", "Mover a Sello", "Mover a Thermo-king"]
            opciones_filtradas = [op for op in opciones if op != f"Mover a {key.capitalize()}"]
            destino = st.selectbox("Mover foto a:", opciones_filtradas, key=f"derivar_{key}_{i}_{RC}_{f}", label_visibility="collapsed")

            if destino != "Mantener aquí":
                if st.button("➡️ Confirmar", key=f"btn_mover_{key}_{i}_{RC}_{f}", width="stretch"):
                    prefijo = {"Mover a Documentación": "documentacion_", "Mover a Camión": "camion_", "Mover a Termógrafo": "termografo_", "Mover a Sello": "sello_", "Mover a Thermo-king": "thermoking_"}[destino]
                    nuevo_nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                    bytes_foto = nube.descargar_foto_nube(pedido_id, f)
                    nube.subir_foto_nube(pedido_id, nuevo_nombre, bytes_foto)
                    nube.borrar_foto_nube(pedido_id, f)
                    st.session_state["fotos_ocultas"].add(f)
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()

def val(key, default=""):
    ultimo_cargado = st.session_state.get("cargar_ultimo", {})
    v = ultimo_cargado.get(key, default)
    return default if v == "-" or v is None else v

def borrar_fotos_seleccionadas(pedido_id, df, seleccion):
    """Borra de la nube las fotos seleccionadas en la tabla y actualiza la sesión."""
    if not seleccion:
        return 0
    nombres_a_borrar = [df.iloc[idx]["Archivo"] for idx in seleccion]
    for f in nombres_a_borrar:
        nube.borrar_foto_nube(pedido_id, f)
        st.session_state["fotos_ocultas"].add(f)
    st.cache_data.clear()
    return len(nombres_a_borrar)

# ============ GESTIÓN DE PEDIDOS ============
def mostrar_gestion_pedidos():
    st.subheader("📋 Gestión de Pedidos")
    tipo_pedido = st.radio("Selecciona el tipo:", ["Pedido de venta", "Traslado"], horizontal=True)
    st.divider()

    with st.form("crear_pedido"):
        col1, col2 = st.columns(2)
        if tipo_pedido == "Traslado":
            with col1:
                nuevo_nro = st.text_input("N° de Entrega *")
                nuevo_destino = st.text_input("Destino *")
            with col2:
                nuevo_transporte = st.text_input("Transporte (Opcional)")
        else:
            with col1:
                nuevo_nro = st.text_input("N° Pedido *")
                nuevo_cliente = st.text_input("Cliente *")
            with col2:
                nuevo_transporte = st.text_input("Transporte (Opcional)")
                nuevo_nro_entrega = st.text_input("N° de Entrega (Opcional)")

        crear = st.form_submit_button("➕ Crear Pedido", type="primary")

        if crear and nuevo_nro:
            pedido_id = str(uuid.uuid4())
            codigo_pedido = f"{nuevo_nro}_{uuid.uuid4().hex[:4]}"

            if tipo_pedido == "Traslado":
                datos = {"id": pedido_id, "codigo_pedido": codigo_pedido, "nro_pedido": nuevo_nro, "nro_entrega": nuevo_nro, "cliente": nuevo_destino, "tipo": tipo_pedido, "transporte": nuevo_transporte or "No asignado", "estado": "Pendiente de fotos", "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"), "guia_despacho": "-", "chofer": "-", "patente_camion": "-", "patente_rampla": "-", "sello_final": "-", "sellos_provisorios": "-", "nro_termografo": "-"}
            else:
                datos = {"id": pedido_id, "codigo_pedido": codigo_pedido, "nro_pedido": nuevo_nro, "nro_entrega": nuevo_nro_entrega or "-", "cliente": nuevo_cliente, "tipo": tipo_pedido, "transporte": nuevo_transporte or "No asignado", "estado": "Pendiente de fotos", "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"), "guia_despacho": "-", "chofer": "-", "patente_camion": "-", "patente_rampla": "-", "sello_final": "-", "sellos_provisorios": "-", "nro_termografo": "-"}

            nube.subir_pedido_nube(pedido_id, datos)
            st.success("✅ Pedido creado.")
            st.rerun()

# ============ ENRUTADOR ============
if st.session_state.get("forzar_modo_informe", False):
    st.session_state["selector_modo"] = "📄 Generar Informe"
    st.session_state["forzar_modo_informe"] = False
    st.session_state["reinicio_count"] += 1
    st.rerun()

modo = st.radio("Modo:", ["📄 Generar Informe", "📋 Gestión de Pedidos"], horizontal=True, key="selector_modo")

if modo == "📋 Gestión de Pedidos":
    mostrar_gestion_pedidos()
    st.stop()

# ============ MODO INFORME ============
pedido_actual = st.session_state.get("pedido_actual_id", "")
bloqueado = False
pedidos_nube = nube.obtener_pedidos_nube()

if pedido_actual:
    for p in pedidos_nube:
        if p['id'] == pedido_actual:
            bloqueado = (p.get('estado') == 'Finalizado')
            st.session_state["cargar_ultimo"] = p

# ============ BARRA LATERAL ============
with st.sidebar:
    st.markdown("### 🧭 Navegación Rápida")
    if not pedidos_nube:
        st.info("No hay pedidos creados.")
    else:
        pendientes = [p for p in pedidos_nube if p.get('estado') != 'Finalizado']
        finalizados = [p for p in pedidos_nube if p.get('estado') == 'Finalizado']
        
        def boton_pedido(p, icono):
            label = f"{icono} {p['nro_pedido']} - {p['cliente'][:15]}..."
            if p['id'] == pedido_actual:
                st.button(label, key=f"nav_{p['id']}", type="primary", width="stretch", disabled=True)
            else:
                if st.button(label, key=f"nav_{p['id']}", width="stretch"):
                    st.session_state["cargar_ultimo"] = p
                    st.session_state["pedido_actual_id"] = p["id"]
                    st.session_state["reinicio_count"] += 1
                    st.session_state["fotos_ocultas"] = set()
                    st.rerun()

        if pendientes:
            st.markdown("**🟡 Pendientes**")
            for p in pendientes: boton_pedido(p, "📦")
        if finalizados:
            st.divider()
            st.markdown("**🟢 Finalizados**")
            for p in finalizados: boton_pedido(p, "🔒")
                
    st.divider()
    if st.button("🧹 Reiniciar app", width="stretch"):
        st.session_state.clear()
        st.rerun()

st.subheader("📋 Datos generales")
if bloqueado: st.warning("🔒 Pedido FINALIZADO.")

with st.form("datos"):
    c1, c2, c3 = st.columns(3)
    with c1:
        empresa = st.text_input("Empresa", value=val("empresa", "Australis Mar SA"), disabled=bloqueado)
        tipo_informe = st.selectbox("Tipo", ["Pedido de venta", "Traslado"], index=0 if val("tipo_informe", "Pedido de venta") == "Pedido de venta" else 1, disabled=bloqueado)
        nro_pedido = st.text_input("N° Pedido", value=val("nro_pedido", ""), disabled=bloqueado)
    with c2:
        fecha = st.date_input("Fecha", value=date.today(), disabled=bloqueado)
        origen = st.text_input("Origen", value=val("origen", "Planta Dumestre"), disabled=bloqueado)
        cliente = st.text_input("Cliente", value=val("cliente", ""), disabled=bloqueado)
    with c3:
        nro_entrega = st.text_input("N° Entrega", value=val("nro_entrega", ""), disabled=bloqueado)
        guia_despacho = st.text_input("Guía Despacho", value=val("guia_despacho", ""), disabled=bloqueado)

    st.subheader("🚛 Transporte")
    t1, t2 = st.columns(2)
    with t1:
        transporte = st.text_input("Transporte", value=val("transporte", ""), disabled=bloqueado)
        patente_camion = st.text_input("Patente Camión", value=val("patente_camion", ""), disabled=bloqueado)
        sello_final = st.text_input("Sello Final", value=val("sello_final", ""), disabled=bloqueado)
    with t2:
        chofer = st.text_input("Chofer", value=val("chofer", ""), disabled=bloqueado)
        patente_rampla = st.text_input("Patente Rampla", value=val("patente_rampla", ""), disabled=bloqueado)
        sellos_provisorios = st.text_input("Sellos Provisorios", value=val("sellos_provisorios", ""), disabled=bloqueado)
    nro_termografo = st.text_input("N° Termógrafo", value=val("nro_termografo", ""), disabled=bloqueado)

    if not bloqueado:
        if st.form_submit_button("💾 Guardar datos", width="stretch"):
            if pedido_actual:
                pedidos = nube.obtener_pedidos_nube()
                for p in pedidos:
                    if p['id'] == pedido_actual:
                        p.update({"nro_entrega": nro_entrega, "transporte": transporte, "cliente": cliente, "nro_pedido": nro_pedido, "guia_despacho": guia_despacho, "chofer": chofer, "patente_camion": patente_camion, "patente_rampla": patente_rampla, "sello_final": sello_final, "sellos_provisorios": sellos_provisorios, "nro_termografo": nro_termografo})
                        nube.subir_pedido_nube(pedido_actual, p)
                        st.success("Guardado.")
                        st.rerun()

st.subheader("📷 Fotos")
if pedido_actual:
    fotos = nube.obtener_fotos_nube(pedido_actual)

    with st.expander("0. Documentación", expanded=False):
        docs = [x for x in fotos if x.startswith("documentacion_")]
        if docs:
            renderizar_galeria("documentacion", docs, pedido_actual, cols_num=4)
        else:
            st.info("No hay documentación.")

        if not bloqueado:
            st.markdown("**Subir fotos manualmente:**")
            nuevas = st.file_uploader("Subir documentación", type=["jpg", "png"], accept_multiple_files=True, key=f"up_doc_{RC}")
            if nuevas:
                for f in nuevas:
                    nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                    nube.subir_foto_nube(pedido_actual, nombre, f.getbuffer())
                st.rerun()

    with st.expander("1. Estibas", expanded=True):
        estibas = [x for x in fotos if x.startswith("estiba_pata_")]
        
        if not bloqueado:
            st.markdown("### 📤 Subir y Procesar Fotos Nuevas")
            st.info("Sube las fotos de WhatsApp. El OCR les asignará el número de Pata y contará las cajas.")
            fotos_manuales = st.file_uploader("Selecciona las fotos", type=["jpg", "png"], accept_multiple_files=True, key=f"up_estiba_{RC}")
            
            if fotos_manuales:
                if st.button("🚀 Analizar y Guardar Fotos", type="primary", width="stretch"):
                    with st.spinner("El OCR está leyendo los carteles... ⏳"):
                        try:
                            from ocr_bridge import analizar_fotos
                            fotos_para_ocr = [(f.name, f.getvalue()) for f in fotos_manuales]
                            resultados = analizar_fotos(fotos_para_ocr)
                            
                            mapa_bytes = {f.name: f.getvalue() for f in fotos_manuales}
                            patas_guardadas = 0
                            errores = []
                            
                            for r in resultados:
                                nombre_original = r["archivo"]
                                pata_detectada = r.get("pata")
                                
                                if pata_detectada and pata_detectada != 99 and nombre_original in mapa_bytes:
                                    nuevo_nombre = f"estiba_pata_{pata_detectada}.jpg"
                                    nube.subir_foto_nube(pedido_actual, nuevo_nombre, mapa_bytes[nombre_original])
                                    patas_guardadas += 1
                                else:
                                    nuevo_nombre = f"estiba_pata_99.jpg"
                                    nube.subir_foto_nube(pedido_actual, nuevo_nombre, mapa_bytes[nombre_original])
                                    errores.append(nombre_original)
                            
                            if errores:
                                st.warning(f"⚠️ Se guardaron {patas_guardadas} fotos. Estas no se pudieron asignar (Pata 99): {', '.join(errores)}")
                            else:
                                st.success(f"✅ Se guardaron {patas_guardadas} fotos correctamente.")
                            
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al procesar: {e}")

        st.divider()

        if estibas:
            st.markdown("### 📋 Resumen de Patas y Cajas")
            
            if f"ocr_result_{pedido_actual}" not in st.session_state:
                df_estibas = pd.DataFrame([{"Pata": f.split("_")[2].replace(".jpg", ""), "Archivo": f, "Cajas": 0} for f in estibas])
                st.session_state[f"ocr_result_{pedido_actual}"] = df_estibas

            df_editado = st.data_editor(
                st.session_state[f"ocr_result_{pedido_actual}"],
                width="stretch",
                disabled=bloqueado,
                hide_index=True,
                num_rows="fixed",
                key=f"editor_estibas_{pedido_actual}",
                column_config={
                    "Archivo": st.column_config.TextColumn("Archivo", disabled=True),
                    "Pata OCR": st.column_config.NumberColumn("Pata OCR", disabled=True),
                    "Pata Final (Editable)": st.column_config.NumberColumn("Pata Final"),
                    "Cajas": st.column_config.NumberColumn("Cajas")
                }
            )
            st.session_state[f"ocr_result_{pedido_actual}"] = df_editado
            
            if not bloqueado:
                filas_seleccionadas = st.multiselect(
                    "Selecciona las fotos que deseas eliminar (puedes elegir varias):",
                    options=range(len(df_editado)),
                    format_func=lambda i: f"Pata {df_editado.iloc[i].get('Pata Final (Editable)', '?')} - {df_editado.iloc[i]['Archivo']}",
                    key=f"sel_borrar_estibas_{pedido_actual}"
                )
                
                if filas_seleccionadas:
                    if st.button("🗑️ Eliminar Fotos Seleccionadas", type="primary", width="stretch"):
                        with st.spinner("Borrando fotos..."):
                            # 🔥 CORRECCIÓN AQUÍ: Se quitó el 4to parámetro que causaba el error
                            cant = borrar_fotos_seleccionadas(pedido_actual, df_editado, filas_seleccionadas)
                            st.success(f"✅ {cant} fotos eliminadas correctamente.")
                            time.sleep(1.5)
                            st.rerun()

            total_patas = len(df_editado)
            try:
                total_cajas = int(pd.to_numeric(df_editado["Cajas"], errors='coerce').fillna(0).sum())
            except:
                total_cajas = 0
            
            col_m1, col_m2 = st.columns(2)
            col_m1.metric(label="📦 Total Patas Detectadas", value=total_patas)
            col_m2.metric(label="🧊 Total Cajas Detectadas", value=total_cajas)
            
            st.divider()
            st.markdown("### ✏️ Revisión Foto por Foto")
            col_tabla, col_preview = st.columns([1.5, 1])
            with col_preview:
                archivo_sel = st.selectbox("Ver foto:", df_editado["Archivo"].tolist(), key=f"sel_ocr_{RC}_{pedido_actual}")
                if archivo_sel:
                    b = nube.descargar_foto_nube(pedido_actual, archivo_sel)
                    b64 = convertir_a_base64(b, 600)
                    st.markdown(f'<img src="{b64}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
            with col_tabla:
                st.info("Edita la Pata y las Cajas en la tabla superior. Para borrar fotos equivocadas, selecciónalas en la lista y presiona 'Eliminar'.")

    def seccion_extra(titulo, prefijo):
        with st.expander(titulo, expanded=False):
            items = [x for x in fotos if x.startswith(prefijo)]
            if items:
                renderizar_galeria(prefijo, items, pedido_actual, cols_num=4)
            else:
                st.info("No hay fotos.")

            if not bloqueado:
                st.markdown("**Subir fotos manualmente:**")
                nuevas = st.file_uploader(f"Subir fotos ({titulo})", type=["jpg", "png"], accept_multiple_files=True, key=f"up_{prefijo}_{RC}")
                if nuevas:
                    for f in nuevas:
                        nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                        nube.subir_foto_nube(pedido_actual, nombre, f.getbuffer())
                    st.rerun()

    seccion_extra("2. Camión", "camion_")
    seccion_extra("3. Termógrafo", "termografo_")
    seccion_extra("4. Sellos", "sello_")
    seccion_extra("5. Thermo-king", "thermoking_")

st.divider()
c1, c2 = st.columns(2)
with c1:
    if st.button("🚀 Generar PDF", type="primary", width="stretch"):
        st.success("Función PDF en construcción para la nube.")
with c2:
    if pedido_actual and not bloqueado:
        if st.button("✅ Finalizar Pedido", width="stretch"):
            pedidos = nube.obtener_pedidos_nube()
            for p in pedidos:
                if p['id'] == pedido_actual:
                    p['estado'] = "Finalizado"
                    nube.subir_pedido_nube(pedido_actual, p)
                    st.rerun()
    elif pedido_actual and bloqueado:
        if st.button("🔓 Reabrir Pedido", type="primary", width="stretch"):
            pedidos = nube.obtener_pedidos_nube()
            for p in pedidos:
                if p['id'] == pedido_actual:
                    p['estado'] = "Pendiente de fotos"
                    nube.subir_pedido_nube(pedido_actual, p)
                    st.rerun()
