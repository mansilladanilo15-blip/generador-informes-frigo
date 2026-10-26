import streamlit as st
import uuid
import base64
import time
import conexion_nube as nube


def eliminar_foto_verificada(pedido_id, nombre_foto, intentos=3):
    """Elimina una foto y confirma el resultado consultando Storage sin ocultar errores."""
    ultimo_error = None

    try:
        nube.borrar_foto_nube(pedido_id, nombre_foto)
    except Exception as exc:
        # El borrado pudo aplicarse aunque la respuesta fallara; se comprueba Storage.
        ultimo_error = exc

    total_intentos = max(1, int(intentos))
    for intento in range(total_intentos):
        try:
            fotos_restantes = nube.obtener_fotos_nube_verificado(pedido_id)
            if nombre_foto not in fotos_restantes:
                return True
            ultimo_error = RuntimeError("La foto todavía aparece en Storage.")
        except Exception as exc:
            ultimo_error = exc

        if intento < total_intentos - 1:
            time.sleep(0.8)

    detalle = f" Detalle: {ultimo_error}" if ultimo_error else ""
    raise RuntimeError(
        f"No se pudo confirmar el borrado de '{nombre_foto}'.{detalle}"
    )


def limpiar_referencias_estiba(pedido_id, nombre_foto):
    """Limpia solo las referencias de la foto en los campos existentes."""
    pedidos = nube.obtener_pedidos_nube() or []
    pedido_data = next(
        (p.copy() for p in pedidos if str(p.get("id")) == str(pedido_id)),
        None
    )
    if pedido_data is None:
        raise RuntimeError("No se encontró el pedido para limpiar los datos de estiba.")

    cajas = pedido_data.get("cajas_estibas", {}) or {}
    patas = pedido_data.get("patas_estibas", {}) or {}
    cajas.pop(nombre_foto, None)
    patas.pop(nombre_foto, None)
    pedido_data["cajas_estibas"] = cajas
    pedido_data["patas_estibas"] = patas
    nube.subir_pedido_nube(pedido_id, pedido_data)



st.set_page_config(page_title="App Operarios", page_icon="🚚", layout="centered")

if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "subida_terminada" not in st.session_state:
    st.session_state["subida_terminada"] = False
if "procesados" not in st.session_state:
    st.session_state["procesados"] = {}
if "confirmar_borrado_movil" not in st.session_state:
    st.session_state["confirmar_borrado_movil"] = False

col_titulo, col_boton = st.columns([4, 1])
with col_titulo:
    st.title("📱 App de Operarios")
with col_boton:
    if st.button("🔄 Sincronizar", width="stretch"):
        st.session_state.clear()
        st.cache_data.clear()
        st.rerun()

todos_los_pedidos = nube.obtener_pedidos_nube()

if not todos_los_pedidos:
    st.warning("⚠️ No hay pedidos creados en la nube.")
    st.stop()

pendientes = [p for p in todos_los_pedidos if p.get("estado") != "Finalizado"]
finalizados = [p for p in todos_los_pedidos if p.get("estado") == "Finalizado"]

st.subheader("🟡 Pedidos Pendientes")

if pendientes:
    opciones_pendientes = {f"{p['nro_pedido']} - {p['cliente']}": p for p in pendientes}
    pedido_seleccionado = st.selectbox("Selecciona un pedido:", list(opciones_pendientes.keys()))
    pedido = opciones_pendientes[pedido_seleccionado]
else:
    st.success("🎉 ¡No hay pedidos pendientes!")
    pedido = None

with st.expander("📂 Historial de Finalizados", expanded=False):
    if finalizados:
        for p in finalizados:
            st.write(f"🔒 {p['nro_pedido']} - {p['cliente']}")
    else:
        st.info("Aún no hay finalizados.")

st.divider()

if pedido:
    if pedido.get("estado") == "Finalizado":
        st.success("🔒 **ESTE PEDIDO HA SIDO FINALIZADO**")
        st.stop()

    if pedido.get("tipo") == "Traslado":
        titulo_cartel = f"🚚 Traslado: {pedido.get('nro_entrega', pedido['nro_pedido'])}"
        subtitulo_cartel = f"Destino: {pedido['cliente']}"
    else:
        titulo_cartel = f"📦 Pedido: {pedido['nro_pedido']}"
        subtitulo_cartel = f"Entrega: {pedido.get('nro_entrega', '-')} | Cliente: {pedido['cliente']}"

    st.markdown(f"""
        <div style="background-color: #1a4d8f; padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;">
            <h2 style="margin: 0; color: white; font-size: 24px;">{titulo_cartel}</h2>
            <h3 style="margin: 10px 0 0 0; color: #e0e0e0; font-size: 18px;">{subtitulo_cartel}</h3>
        </div>
        """, unsafe_allow_html=True)

    pedido_id = pedido['id']

    if st.session_state.get("confirmar_borrado_movil"):
        st.success("✅ Borrado confirmado en la nube.")
        if st.button("🔄 Actualizar Galería", type="primary", width="stretch"):
            st.session_state["confirmar_borrado_movil"] = False
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()

    with st.expander("🧨 Zona de Peligro (Borrar todas las fotos)"):
        st.warning("Esto eliminará TODAS las fotos de este pedido (en la nube y en la PC).")
        if st.button("🗑️ Borrar TODAS las fotos del pedido", type="primary", width="stretch"):
            try:
                with st.spinner("Eliminando todas las fotos del pedido..."):
                    fotos_actuales = list(nube.obtener_fotos_nube_verificado(pedido_id))
                    errores = []
                    for nombre_foto in fotos_actuales:
                        try:
                            eliminar_foto_verificada(pedido_id, nombre_foto)
                        except Exception as exc:
                            errores.append(f"{nombre_foto}: {exc}")

                    if errores:
                        st.error("No se confirmaron todas las eliminaciones. No se limpiaron los datos de estibas.")
                        for error in errores:
                            st.write(f"• {error}")
                    else:
                        # No limpiar metadatos si queda alguna foto o no se puede verificar Storage.
                        fotos_finales = nube.obtener_fotos_nube_verificado(pedido_id)
                        if fotos_finales:
                            raise RuntimeError(
                                "Quedan fotos en la nube; no se limpiaron los datos de estibas. "
                                + ", ".join(fotos_finales)
                            )

                        pedidos_actualizados = nube.obtener_pedidos_nube() or []
                        pedido_data = next(
                            (p.copy() for p in pedidos_actualizados
                             if str(p.get("id")) == str(pedido_id)),
                            None
                        )
                        if pedido_data is None:
                            raise RuntimeError("No se encontró el pedido para actualizar sus datos.")
                        pedido_data["cajas_estibas"] = {}
                        pedido_data["patas_estibas"] = {}
                        nube.subir_pedido_nube(pedido_id, pedido_data)
                        st.session_state["confirmar_borrado_movil"] = True
                        st.session_state["procesados"] = {}
                        st.session_state["subida_terminada"] = False
                        st.cache_data.clear()
                        st.rerun()
            except Exception as exc:
                st.error(f"❌ Error al borrar las fotos: {exc}")

    pedido_data = next((p for p in nube.obtener_pedidos_nube() if p['id'] == pedido_id), {})
    cajas_nube = pedido_data.get("cajas_estibas", {})
    patas_nube = pedido_data.get("patas_estibas", {})

    # 0. DOCUMENTACIÓN
    fotos_doc = nube.obtener_fotos_nube(pedido_id)
    fotos_doc = [f for f in fotos_doc if f.startswith("documentacion_")]
    
    with st.expander(f"📄 0. Documentación ({len(fotos_doc)})", expanded=True):
        tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
        with tab1:
            subidas = st.file_uploader("Subir documentación", type=["jpg", "png"], accept_multiple_files=True, key=f"gal_doc_{pedido_id}")
            if subidas and not st.session_state["subida_terminada"]:
                progreso = st.progress(0)
                texto_prog = st.empty()
                total = len(subidas)
                
                for idx, foto in enumerate(subidas):
                    if f"{pedido_id}_doc_{foto.name}" not in st.session_state["procesados"]:
                        texto_prog.info(f"⏳ Subiendo {idx + 1} de {total}: {foto.name}")
                        nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                        nube.subir_foto_nube(pedido_id, nombre, foto.getbuffer())
                        st.session_state["procesados"][f"{pedido_id}_doc_{foto.name}"] = True
                    progreso.progress((idx + 1) / total)
                
                st.session_state["subida_terminada"] = True
                progreso.empty()
                texto_prog.empty()
                st.success("✅ Documentación subida correctamente.")
                st.button("👁️ Ver fotos subidas", on_click=lambda: st.session_state.update({"subida_terminada": False}))
                
        with tab2:
            cam = st.camera_input("Tomar foto", key=f"cam_doc_{pedido_id}_{uuid.uuid4().hex[:6]}")
            if cam:
                nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                nube.subir_foto_nube(pedido_id, nombre, cam.getbuffer())
                st.rerun()
                
        if fotos_doc:
            cols = st.columns(2)
            for idx, f in enumerate(fotos_doc):
                with cols[idx % 2]:
                    bytes_img = nube.descargar_foto_nube(pedido_id, f)
                    b64 = base64.b64encode(bytes_img).decode("utf-8")
                    st.markdown(f'''
                        <div style="text-align:center; margin-bottom: 5px;">
                            <img src="data:image/jpeg;base64,{b64}" style="width:100%; height:160px; object-fit:cover; border-radius:8px; border: 1px solid #ddd;">
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    if st.button("🗑️ Borrar", key=f"del_doc_{pedido_id}_{f}", width="stretch"):
                        try:
                            eliminar_foto_verificada(pedido_id, f)
                            st.session_state["confirmar_borrado_movil"] = True
                            st.session_state["procesados"] = {}
                            st.session_state["subida_terminada"] = False
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"❌ No se pudo borrar la foto: {exc}")

    st.divider()

    # 1. ESTIBAS
    fotos_estibas = nube.obtener_fotos_nube(pedido_id)
    fotos_estibas = [f for f in fotos_estibas if f.startswith("estiba_pata_")]
    
    if "expand_estibas" not in st.session_state:
        st.session_state["expand_estibas"] = True

    with st.expander(f"📦 1. Estibas ({len(fotos_estibas)})", expanded=st.session_state["expand_estibas"]):
        
        st.info("Sube todas las fotos de una vez. El administrador en la PC procesará el OCR.")
        tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
        
        with tab1:
            subidas = st.file_uploader("Selecciona varias fotos", type=["jpg", "png"], accept_multiple_files=True, key="gal_estibas_multi")
            if subidas and not st.session_state["subida_terminada"]:
                progreso = st.progress(0)
                texto_prog = st.empty()
                total = len(subidas)
                
                for idx, foto in enumerate(subidas):
                    file_id = f"{pedido_id}_estiba_{foto.name}_{foto.size}"
                    if file_id not in st.session_state["procesados"]:
                        texto_prog.info(f"⏳ Subiendo {idx + 1} de {total}: {foto.name}")
                        nombre = f"estiba_pata_99_REVISAR_{uuid.uuid4().hex[:4]}.jpg"
                        nube.subir_foto_nube(pedido_id, nombre, foto.getbuffer())
                        st.session_state["procesados"][file_id] = True
                    progreso.progress((idx + 1) / total)
                
                st.session_state["subida_terminada"] = True
                progreso.empty()
                texto_prog.empty()
                st.success("✅ Fotos subidas correctamente. Ya puedes ir a la PC a procesarlas.")
                st.button("👁️ Ver fotos subidas", on_click=lambda: st.session_state.update({"subida_terminada": False}))
                
        with tab2:
            cam = st.camera_input("Tomar foto", key="cam_estiba")
            if cam:
                nombre = f"estiba_pata_99_REVISAR_{uuid.uuid4().hex[:4]}.jpg"
                nube.subir_foto_nube(pedido_id, nombre, cam.getbuffer())
                st.rerun()

        st.divider()

        if fotos_estibas:
            cols = st.columns(2)
            for idx, f in enumerate(fotos_estibas):
                with cols[idx % 2]:
                    bytes_img = nube.descargar_foto_nube(pedido_id, f)
                    b64 = base64.b64encode(bytes_img).decode("utf-8")
                    
                    pata_asignada = patas_nube.get(f, f.split("_")[2].replace(".jpg", "").split("_")[0])
                    cajas = cajas_nube.get(f, 0)
                    
                    st.markdown(f'''
                        <div style="text-align:center; margin-bottom: 5px;">
                            <img src="data:image/jpeg;base64,{b64}" style="width:100%; height:160px; object-fit:cover; border-radius:8px; border: 1px solid #ddd;">
                            <div style="font-size:12px; color:#1a4d8f; font-weight:bold; margin-top:2px;">📦 Pata {pata_asignada} ({cajas} cajas)</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    if st.button("🗑️ Borrar", key=f"del_estiba_{pedido_id}_{f}", width="stretch"):
                        try:
                            eliminar_foto_verificada(pedido_id, f)
                            limpiar_referencias_estiba(pedido_id, f)
                            st.session_state["confirmar_borrado_movil"] = True
                            st.session_state["procesados"] = {}
                            st.session_state["subida_terminada"] = False
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"❌ No se pudo borrar la foto de estiba: {exc}")
        else:
            st.info("No hay fotos de estibas subidas.")

    st.divider()

    # OTRAS CATEGORÍAS
    st.markdown("### 📸 Otras Categorías")
    
    def mostrar_categoria(titulo, prefijo):
        fotos_brutas = nube.obtener_fotos_nube(pedido_id)
        fotos = [f for f in fotos_brutas if f.startswith(prefijo)]
        
        with st.expander(f"{titulo} ({len(fotos)})", expanded=False):
            if fotos:
                cols = st.columns(2)
                for idx, f in enumerate(fotos):
                    with cols[idx % 2]:
                        bytes_img = nube.descargar_foto_nube(pedido_id, f)
                        b64 = base64.b64encode(bytes_img).decode("utf-8")
                        
                        st.markdown(f'''
                            <div style="text-align:center; margin-bottom: 5px;">
                                <img src="data:image/jpeg;base64,{b64}" style="width:100%; height:160px; object-fit:cover; border-radius:8px; border: 1px solid #ddd;">
                            </div>
                        ''', unsafe_allow_html=True)
                        
                        if st.button("🗑️ Borrar", key=f"del_{pedido_id}_{f}", width="stretch"):
                            try:
                                eliminar_foto_verificada(pedido_id, f)
                                st.session_state["confirmar_borrado_movil"] = True
                                st.session_state["procesados"] = {}
                                st.session_state["subida_terminada"] = False
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as exc:
                                st.error(f"❌ No se pudo borrar la foto: {exc}")
            
            tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
            with tab1:
                subidas = st.file_uploader("Subir fotos", type=["jpg", "png"], accept_multiple_files=True, key=f"gal_{prefijo}")
                if subidas and not st.session_state["subida_terminada"]:
                    progreso = st.progress(0)
                    texto_prog = st.empty()
                    total = len(subidas)
                    
                    for idx, s in enumerate(subidas):
                        file_id = f"{pedido_id}_{prefijo}_{s.name}_{s.size}"
                        if file_id not in st.session_state["procesados"]:
                            texto_prog.info(f"⏳ Subiendo {idx + 1} de {total}: {s.name}")
                            nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                            nube.subir_foto_nube(pedido_id, nombre, s.getbuffer())
                            st.session_state["procesados"][file_id] = True
                        progreso.progress((idx + 1) / total)
                    
                    st.session_state["subida_terminada"] = True
                    progreso.empty()
                    texto_prog.empty()
                    st.success("✅ Fotos subidas correctamente.")
                    st.button("👁️ Ver fotos subidas", on_click=lambda: st.session_state.update({"subida_terminada": False}))
            with tab2:
                cam = st.camera_input("Tomar foto", key=f"cam_{prefijo}_{uuid.uuid4().hex[:6]}")
                if cam:
                    nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                    nube.subir_foto_nube(pedido_id, nombre, cam.getbuffer())
                    st.rerun()

    mostrar_categoria("2. Fotos Camión", "camion_")
    mostrar_categoria("3. Termógrafo", "termografo_")
    mostrar_categoria("4. Sellos", "sello_")
    mostrar_categoria("5. Thermo-king", "thermoking_")
