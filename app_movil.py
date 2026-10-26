import streamlit as st
import uuid
import base64
import time
import conexion_nube as nube

st.set_page_config(page_title="App Operarios", page_icon="🚚", layout="centered")

# 🔥 DESACTIVAMOS EL AUTO-REFRESH POR DEFECTO (Causa principal de las recargas)
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "fotos_ocultas_movil" not in st.session_state:
    st.session_state["fotos_ocultas_movil"] = set()
if "procesados" not in st.session_state:
    st.session_state["procesados"] = {}

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
    auto_recarga = st.toggle("Auto-recargar (cada 30s)", value=st.session_state["auto_refresh"])
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

    # 0. DOCUMENTACIÓN
    fotos_doc = nube.obtener_fotos_nube(pedido_id)
    fotos_doc = [f for f in fotos_doc if f.startswith("documentacion_") and f not in st.session_state["fotos_ocultas_movil"]]
    
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
                    
                    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                    with col_b2:
                        if st.button("🗑️", key=f"del_doc_{f}"):
                            nube.borrar_foto_nube(pedido_id, f)
                            st.session_state["fotos_ocultas_movil"].add(f)
                            st.rerun()

    st.divider()

    # 1. ESTIBAS
    fotos_estibas = nube.obtener_fotos_nube(pedido_id)
    fotos_estibas = [f for f in fotos_estibas if f.startswith("estiba_pata_") and f not in st.session_state["fotos_ocultas_movil"]]
    
    pedido_data = next((p for p in nube.obtener_pedidos_nube() if p['id'] == pedido_id), {})
    cajas_nube = pedido_data.get("cajas_estibas", {})
    
    if "expand_estibas" not in st.session_state:
        st.session_state["expand_estibas"] = True

    with st.expander(f"📦 1. Estibas ({len(fotos_estibas)})", expanded=st.session_state["expand_estibas"]):
        if fotos_estibas:
            cols = st.columns(2)
            for idx, f in enumerate(fotos_estibas):
                with cols[idx % 2]:
                    bytes_img = nube.descargar_foto_nube(pedido_id, f)
                    b64 = base64.b64encode(bytes_img).decode("utf-8")
                    
                    pata_asignada = f.split("_")[2].replace(".jpg", "").split("_")[0]
                    cajas = cajas_nube.get(f, 0)
                    
                    st.markdown(f'''
                        <div style="text-align:center; margin-bottom: 5px;">
                            <img src="data:image/jpeg;base64,{b64}" style="width:100%; height:160px; object-fit:cover; border-radius:8px; border: 1px solid #ddd;">
                            <div style="font-size:12px; color:#1a4d8f; font-weight:bold; margin-top:2px;">📦 Pata {pata_asignada} ({cajas} cajas)</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                    with col_b2:
                        if st.button("🗑️", key=f"del_estiba_{f}"):
                            nube.borrar_foto_nube(pedido_id, f)
                            st.session_state["fotos_ocultas_movil"].add(f)
                            st.rerun()
        else:
            st.info("No hay fotos de estibas subidas.")

        tab1, tab2 = st.tabs(["🖼️ Galería", "📷 Cámara"])
        with tab1:
            subida = st.file_uploader("Subir nueva estiba", type=["jpg", "png"], key="gal_estiba")
            if subida:
                nombre = f"estiba_pata_99_REVISAR.jpg"
                nube.subir_foto_nube(pedido_id, nombre, subida.getbuffer())
                st.rerun()
        with tab2:
            cam = st.camera_input("Tomar foto", key="cam_estiba")
            if cam:
                nombre = f"estiba_pata_99_REVISAR.jpg"
                nube.subir_foto_nube(pedido_id, nombre, cam.getbuffer())
                st.rerun()

    st.divider()

    # OTRAS CATEGORÍAS
    st.markdown("### 📸 Otras Categorías")
    def mostrar_categoria(titulo, prefijo):
        fotos = nube.obtener_fotos_nube(pedido_id)
        fotos = [f for f in fotos if f.startswith(prefijo) and f not in st.session_state["fotos_ocultas_movil"]]
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
                        
                        col_b1, col_b2, col_b3 = st.columns([1, 2, 1])
                        with col_b2:
                            if st.button("🗑️", key=f"del_{f}"):
                                nube.borrar_foto_nube(pedido_id, f)
                                st.session_state["fotos_ocultas_movil"].add(f)
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
