import streamlit as st
import uuid
import base64
import time
import conexion_nube as nube

st.set_page_config(page_title="App Operarios", page_icon="🚚", layout="centered")

if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = True

if st.session_state["auto_refresh"]:
    st.markdown("""<script>setTimeout(function(){window.location.reload();}, 30000);</script>""", unsafe_allow_html=True)

col_titulo, col_boton = st.columns([4, 1])
with col_titulo:
    st.title("📱 App de Operarios")
with col_boton:
    if st.button("🔄 Recargar", width="stretch"):
        st.rerun()

with st.sidebar:
    st.subheader("⚙️ Opciones")
    auto_recarga = st.toggle("Auto-recargar", value=st.session_state["auto_refresh"])
    if auto_recarga != st.session_state["auto_refresh"]:
        st.session_state["auto_refresh"] = auto_recarga
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

    if "procesados" not in st.session_state:
        st.session_state["procesados"] = {}

    def mostrar_imagen_nube(bytes_img, caption):
        b64 = base64.b64encode(bytes_img).decode("utf-8")
        st.markdown(f'<div style="text-align:center;"><img src="data:image/jpeg;base64,{b64}" style="width:100%; border-radius:6px; margin-bottom:8px;"><div style="font-size:12px; color:#666;">{caption}</div></div>', unsafe_allow_html=True)

    # 0. DOCUMENTACIÓN
    fotos_doc = nube.obtener_fotos_nube(pedido_id)
    fotos_doc = [f for f in fotos_doc if f.startswith("documentacion_")]
    
    with st.expander(f"📄 0. Documentación ({len(fotos_doc)})", expanded=True):
        tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
        with tab1:
            subidas = st.file_uploader("Subir documentación", type=["jpg", "png"], accept_multiple_files=True, key=f"gal_doc_{pedido_id}")
            if subidas:
                for foto in subidas:
                    if f"{pedido_id}_doc_{foto.name}" not in st.session_state["procesados"]:
                        nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                        nube.subir_foto_nube(pedido_id, nombre, foto.getbuffer())
                        st.session_state["procesados"][f"{pedido_id}_doc_{foto.name}"] = True
                st.rerun()
        with tab2:
            cam = st.camera_input("Tomar foto", key=f"cam_doc_{pedido_id}_{uuid.uuid4().hex[:6]}")
            if cam:
                nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                nube.subir_foto_nube(pedido_id, nombre, cam.getbuffer())
                st.rerun()
                
        if fotos_doc:
            cols = st.columns(3)
            for idx, f in enumerate(fotos_doc):
                with cols[idx % 3]:
                    bytes_img = nube.descargar_foto_nube(pedido_id, f)
                    mostrar_imagen_nube(bytes_img, f)
                    if st.button(f"🗑️ Borrar", key=f"del_doc_{f}", width="stretch"):
                        nube.borrar_foto_nube(pedido_id, f)
                        st.rerun()

    st.divider()

    # 1. ESTIBAS
    fotos_estibas = nube.obtener_fotos_nube(pedido_id)
    fotos_estibas = [f for f in fotos_estibas if f.startswith("estiba_pata_")]
    cantidad_patas = len(fotos_estibas) + 1
    
    if "expand_estibas" not in st.session_state:
        st.session_state["expand_estibas"] = True

    with st.expander(f"📦 1. Estibas ({len(fotos_estibas)})", expanded=st.session_state["expand_estibas"]):
        for i in range(1, cantidad_patas + 1):
            nombre_pata = f"estiba_pata_{i}.jpg"
            with st.container(border=True):
                st.markdown(f"#### 📦 Pata {i}")
                
                if nombre_pata not in fotos_estibas:
                    if st.button(f"❌ Eliminar Pata {i}", key=f"del_pata_{i}"):
                        st.rerun()
                if nombre_pata in fotos_estibas:
                    bytes_img = nube.descargar_foto_nube(pedido_id, nombre_pata)
                    st.success("✅ Foto registrada")
                    mostrar_imagen_nube(bytes_img, f"Pata {i}")
                    if st.button(f"🗑️ Borrar Pata {i}", key=f"del_foto_{i}"):
                        nube.borrar_foto_nube(pedido_id, nombre_pata)
                        st.rerun()
                else:
                    tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
                    with tab1:
                        subida = st.file_uploader("Subir", type=["jpg", "png"], key=f"gal_pata_{i}")
                        if subida:
                            nube.subir_foto_nube(pedido_id, nombre_pata, subida.getbuffer())
                            st.session_state["expand_estibas"] = True
                            time.sleep(1)
                            st.rerun()
                    with tab2:
                        cam = st.camera_input("Tomar foto", key=f"cam_pata_{i}_{uuid.uuid4().hex[:6]}")
                        if cam:
                            nube.subir_foto_nube(pedido_id, nombre_pata, cam.getbuffer())
                            st.session_state["expand_estibas"] = True
                            time.sleep(1)
                            st.rerun()

        if st.button("➕ Agregar Pata", type="secondary", width="stretch"):
            st.rerun()

    st.divider()

    # OTRAS CATEGORÍAS
    st.markdown("### 📸 Otras Categorías")
    def mostrar_categoria(titulo, prefijo):
        fotos = nube.obtener_fotos_nube(pedido_id)
        fotos = [f for f in fotos if f.startswith(prefijo)]
        with st.expander(f"{titulo} ({len(fotos)})", expanded=False):
            if fotos:
                cols = st.columns(3)
                for idx, f in enumerate(fotos):
                    with cols[idx % 3]:
                        bytes_img = nube.descargar_foto_nube(pedido_id, f)
                        mostrar_imagen_nube(bytes_img, f)
                        if st.button(f"🗑️ Borrar", key=f"del_{f}", width="stretch"):
                            nube.borrar_foto_nube(pedido_id, f)
                            st.rerun()
            
            tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
            with tab1:
                subidas = st.file_uploader("Subir fotos", type=["jpg", "png"], accept_multiple_files=True, key=f"gal_{prefijo}")
                if subidas:
                    for s in subidas:
                        file_id = f"{pedido_id}_{prefijo}_{s.name}_{s.size}"
                        if file_id not in st.session_state["procesados"]:
                            nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                            nube.subir_foto_nube(pedido_id, nombre, s.getbuffer())
                            st.session_state["procesados"][file_id] = True
                    st.rerun()
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
