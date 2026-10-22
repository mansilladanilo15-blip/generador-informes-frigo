import streamlit as st
import os
import json
import uuid
import base64
import time

st.set_page_config(page_title="App Operarios", page_icon="🚚", layout="centered")

# 🔥 AUTO-RECARGA CADA 30 SEGUNDOS
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = True

if st.session_state["auto_refresh"]:
    st.markdown(
        """
        <script>
            setTimeout(function(){
                window.location.reload();
            }, 30000); // 30 segundos
        </script>
        """,
        unsafe_allow_html=True
    )

# BARRA SUPERIOR CON BOTÓN DE RECARGA MANUAL
col_titulo, col_boton = st.columns([4, 1])
with col_titulo:
    st.title("📱 App de Operarios")
with col_boton:
    if st.button("🔄 Recargar", use_container_width=True):
        st.rerun()

# CONTROL DE AUTO-RECARGA EN BARRA LATERAL
with st.sidebar:
    st.subheader("⚙️ Opciones")
    auto_recarga = st.toggle("Auto-recargar cada 30 seg", value=st.session_state["auto_refresh"])
    if auto_recarga != st.session_state["auto_refresh"]:
        st.session_state["auto_refresh"] = auto_recarga
        st.rerun()

RUTA_PEDIDOS = "temp/pedidos"

if not os.path.exists(RUTA_PEDIDOS):
    st.warning("⚠️ No hay pedidos creados. Pídele al administrador que cree uno.")
    st.stop()

# 1. CARGAR TODOS LOS PEDIDOS
todos_los_pedidos = []
for carpeta in os.listdir(RUTA_PEDIDOS):
    ruta_json = os.path.join(RUTA_PEDIDOS, carpeta, "datos_pedido.json")
    if os.path.exists(ruta_json):
        with open(ruta_json, "r", encoding="utf-8") as f:
            todos_los_pedidos.append(json.load(f))

if not todos_los_pedidos:
    st.warning("⚠️ No hay pedidos creados.")
    st.stop()

# 2. SEPARAR PENDIENTES Y FINALIZADOS
pendientes = [p for p in todos_los_pedidos if p.get("estado") != "Finalizado"]
finalizados = [p for p in todos_los_pedidos if p.get("estado") == "Finalizado"]

# --- SECCIÓN DE PENDIENTES (PRINCIPAL) ---
st.subheader("🟡 Pedidos Pendientes")

if pendientes:
    opciones_pendientes = {f"{p['nro_pedido']} - {p['cliente']}": p for p in pendientes}
    pedido_seleccionado = st.selectbox("Selecciona un pedido pendiente para trabajar:", list(opciones_pendientes.keys()))
    pedido = opciones_pendientes[pedido_seleccionado]
else:
    st.success("🎉 ¡No hay pedidos pendientes! Todos están finalizados.")
    pedido = None

# --- SECCIÓN DE FINALIZADOS (DESPLEGABLE CON BUSCADOR) ---
with st.expander("📂 Ver Historial de Pedidos Finalizados", expanded=False):
    if finalizados:
        busqueda = st.text_input("🔍 Buscar por N° de Pedido o Cliente:", placeholder="Ej: PV1579...")
        
        if busqueda:
            finalizados_filtrados = [
                p for p in finalizados 
                if busqueda.lower() in p['nro_pedido'].lower() or busqueda.lower() in p['cliente'].lower()
            ]
        else:
            finalizados_filtrados = finalizados
            
        if finalizados_filtrados:
            for p in finalizados_filtrados:
                st.write(f"🔒 {p['nro_pedido']} - {p['cliente']} ({p['tipo']})")
        else:
            st.info("No se encontraron pedidos con ese criterio.")
    else:
        st.info("Aún no hay pedidos finalizados.")

st.divider()

# --- RESTO DE LA APP (SOLO SE EJECUTA SI HAY UN PEDIDO PENDIENTE SELECCIONADO) ---
if pedido:
    # BLOQUEO SI EL PEDIDO ESTÁ FINALIZADO
    if pedido.get("estado") == "Finalizado":
        st.success("🔒 **ESTE PEDIDO HA SIDO FINALIZADO POR EL ADMINISTRADOR**")
        st.info("⚠️ No se pueden subir ni modificar fotos. Si necesitas hacer un cambio, comunícate con el administrador.")
        st.stop()

    # CARTEL DESTACADO DINÁMICO
    if pedido.get("tipo") == "Traslado":
        titulo_cartel = f"🚚 Traslado: {pedido.get('nro_entrega', pedido['nro_pedido'])}"
        subtitulo_cartel = f"Destino: {pedido['cliente']}"
    else:
        titulo_cartel = f"📦 Pedido de Venta: {pedido['nro_pedido']}"
        nro_entrega_display = pedido.get('nro_entrega', '-')
        subtitulo_cartel = f"Entrega: {nro_entrega_display} | Cliente: {pedido['cliente']}"

    st.markdown(
        f"""
        <div style="background-color: #1a4d8f; padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;">
            <h2 style="margin: 0; color: white; font-size: 24px;">{titulo_cartel}</h2>
            <h3 style="margin: 10px 0 0 0; color: #e0e0e0; font-size: 18px;">{subtitulo_cartel}</h3>
        </div>
        """,
        unsafe_allow_html=True
    )

    ruta_fotos = os.path.join(RUTA_PEDIDOS, pedido["id"], "fotos")
    os.makedirs(ruta_fotos, exist_ok=True)

    if "procesados" not in st.session_state:
        st.session_state["procesados"] = {}

    def mostrar_imagen_local(ruta_archivo, caption):
        try:
            with open(ruta_archivo, "rb") as f:
                img_bytes = f.read()
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            st.markdown(
                f'<div style="text-align:center;">'
                f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; border-radius:6px; margin-bottom:8px;">'
                f'<div style="font-size:12px; color:#666;">{caption}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"Error al cargar imagen: {e}")

    # 0. DOCUMENTACIÓN
    fotos_doc_count = len([f for f in os.listdir(ruta_fotos) if f.startswith("documentacion_")])
    with st.expander(f"📄 0. Documentación (Camión y Rampla) ({fotos_doc_count})", expanded=True):
        tab1_doc, tab2_doc = st.tabs(["🖼️ Subir de Galería", "📷 Usar Cámara"])
        
        with tab1_doc:
            fotos_doc = st.file_uploader("Subir documentación", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"gal_documentacion_{pedido['id']}")
            if fotos_doc:
                guardado_exitoso = False
                for foto in fotos_doc:
                    file_id = f"{pedido['id']}_documentacion_{foto.name}"
                    if file_id not in st.session_state["procesados"]:
                        nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                        ruta_guardado = os.path.join(ruta_fotos, nombre)
                        
                        with open(ruta_guardado, "wb") as f:
                            f.write(foto.getbuffer())
                            f.flush()
                        
                        if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                            st.session_state["procesados"][file_id] = True
                            guardado_exitoso = True
                
                if guardado_exitoso:
                    st.success("✅ Documentación guardada.")
                    time.sleep(1)
                    st.rerun()
                
        with tab2_doc:
            foto_cam_doc = st.camera_input("Tomar foto de documentación", key=f"cam_documentacion_{pedido['id']}_{uuid.uuid4().hex[:6]}")
            if foto_cam_doc:
                file_id = f"{pedido['id']}_documentacion_cam_{uuid.uuid4().hex[:6]}"
                if file_id not in st.session_state["procesados"]:
                    nombre = f"documentacion_{uuid.uuid4().hex[:6]}.jpg"
                    ruta_guardado = os.path.join(ruta_fotos, nombre)
                    
                    with open(ruta_guardado, "wb") as f:
                        f.write(foto_cam_doc.getbuffer())
                        f.flush()
                    
                    if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                        st.session_state["procesados"][file_id] = True
                        st.success("✅ Foto guardada.")
                        time.sleep(1)
                        st.rerun()

        fotos_doc_existentes = [f for f in os.listdir(ruta_fotos) if f.startswith("documentacion_")]
        if fotos_doc_existentes:
            st.markdown("**Fotos de documentación subidas:**")
            cols = st.columns(3)
            for idx, f in enumerate(fotos_doc_existentes):
                with cols[idx % 3]:
                    ruta_completa_img = os.path.join(ruta_fotos, f)
                    mostrar_imagen_local(ruta_completa_img, f)
                    if st.button(f"🗑️ Borrar", key=f"del_doc_{f}_{pedido['id']}", use_container_width=True):
                        try:
                            os.remove(ruta_completa_img)
                            st.success("✅ Foto eliminada permanentemente.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al borrar: {e}")

    st.divider()

    # 1. ESTIBAS
    clave_cantidad_patas = f"cantidad_patas_{pedido['id']}"

    if clave_cantidad_patas not in st.session_state:
        fotos_patas = [f for f in os.listdir(ruta_fotos) if f.startswith("estiba_pata_")]
        if fotos_patas:
            max_pata = max([int(f.split("_")[2].split(".")[0]) for f in fotos_patas if f.split("_")[2].split(".")[0].isdigit()])
            st.session_state[clave_cantidad_patas] = max_pata + 1
        else:
            st.session_state[clave_cantidad_patas] = 1

    patas_con_foto = len([f for f in os.listdir(ruta_fotos) if f.startswith("estiba_pata_")])

    # 🔥 GUARDAMOS EN MEMORIA SI EL EXPANDER ESTÁ ABIERTO O CERRADO
    if "expand_estibas" not in st.session_state:
        st.session_state["expand_estibas"] = True


        # Mostramos las patas de la última a la primera
    with st.expander(f"📦 1. Registro de Estibas por Pata ({patas_con_foto})", expanded=st.session_state["expand_estibas"]):
        cantidad_patas_actual = st.session_state[clave_cantidad_patas]
        
        # 🔥 VOLVEMOS AL ORDEN NATURAL: DE 1 HASTA LA ÚLTIMA
        for i in range(1, cantidad_patas_actual + 1):
            with st.container(border=True):
                ruta_pata_actual = os.path.join(ruta_fotos, f"estiba_pata_{i}.jpg")
                
                st.markdown(f"#### 📦 Pata {i}")
                
                if not os.path.exists(ruta_pata_actual):
                    if st.button(f"❌ Eliminar Pata {i}", key=f"eliminar_pata_{pedido['id']}_{i}", use_container_width=True):
                        st.session_state[clave_cantidad_patas] -= 1
                        st.rerun()
                
                if os.path.exists(ruta_pata_actual):
                    st.success("✅ Foto registrada")
                    
                    # 🔥 MOSTRAMOS LA VISTA PREVIA DIRECTAMENTE
                    mostrar_imagen_local(ruta_pata_actual, f"Pata {i}")
                    
                    if st.button(f"🗑️ Borrar Foto de Pata {i}", key=f"del_foto_pata_{pedido['id']}_{i}", use_container_width=True):
                        os.remove(ruta_pata_actual)
                        st.success(f"Foto de Pata {i} eliminada.")
                        st.rerun()
                else:
                    tab1, tab2 = st.tabs(["🖼️ Subir de Galería", "📷 Usar Cámara"])
                    
                    with tab1:
                        foto_gal = st.file_uploader(f"Seleccionar de galería", type=["jpg", "jpeg", "png"], key=f"gal_pata_{pedido['id']}_{i}")
                        if foto_gal:
                            file_id = f"{pedido['id']}_estiba_{i}_{foto_gal.name}"
                            if file_id not in st.session_state["procesados"]:
                                nombre = f"estiba_pata_{i}.jpg"
                                ruta_guardado = os.path.join(ruta_fotos, nombre)
                                
                                with open(ruta_guardado, "wb") as f:
                                    f.write(foto_gal.getbuffer())
                                    f.flush()
                                
                                if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                                    st.session_state["procesados"][file_id] = True
                                    st.session_state["expand_estibas"] = True
                                    time.sleep(1)
                                    st.rerun()
                            
                    with tab2:
                        foto_cam = st.camera_input(f"Tomar foto", key=f"cam_pata_{pedido['id']}_{i}_{uuid.uuid4().hex[:6]}")
                        if foto_cam:
                            if not os.path.exists(ruta_pata_actual):
                                ruta_guardado = os.path.join(ruta_fotos, f"estiba_pata_{i}.jpg")
                                with open(ruta_guardado, "wb") as f:
                                    f.write(foto_cam.getbuffer())
                                    f.flush()
                                
                                if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                                    st.session_state["expand_estibas"] = True
                                    time.sleep(1)
                                    st.rerun()

        # 🔥 EL BOTÓN DE AGREGAR PATA VA AL FINAL
        if st.button("➕ Agregar Pata", type="secondary", use_container_width=True):
            st.session_state[clave_cantidad_patas] += 1
            st.rerun()
    st.divider()

    # OTRAS CATEGORÍAS
    st.markdown("### 📸 Otras Categorías")

    def mostrar_otras_categorias(titulo, categoria):
        fotos_existentes = [f for f in os.listdir(ruta_fotos) if f.startswith(f"{categoria}_")]
        cantidad_fotos = len(fotos_existentes)
        
        titulo_con_contador = f"{titulo} ({cantidad_fotos})"
        
        with st.expander(titulo_con_contador, expanded=False):
            if fotos_existentes:
                cols = st.columns(3)
                for idx, f in enumerate(fotos_existentes):
                    with cols[idx % 3]:
                        ruta_imagen = os.path.join(ruta_fotos, f)
                        mostrar_imagen_local(ruta_imagen, f)
                        if st.button(f"🗑️ Borrar", key=f"del_{pedido['id']}_{f}", use_container_width=True):
                            try:
                                os.remove(ruta_imagen)
                                st.success("Foto eliminada.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al borrar: {e}")
            
            tab1, tab2 = st.tabs(["🖼️ Subir de Galería", "📷 Usar Cámara"])
            
            with tab1:
                fotos_gal = st.file_uploader(
                    f"Seleccionar de galería (puedes elegir varias)", 
                    type=["jpg", "jpeg", "png"], 
                    accept_multiple_files=True, 
                    key=f"gal_{pedido['id']}_{categoria}"
                )
                
                if fotos_gal:
                    hubo_nuevas = False
                    for foto in fotos_gal:
                        file_id = f"{pedido['id']}_{categoria}_{foto.name}"
                        if file_id not in st.session_state["procesados"]:
                            nombre = f"{categoria}_{uuid.uuid4().hex[:6]}.jpg"
                            ruta_guardado = os.path.join(ruta_fotos, nombre)
                            
                            with open(ruta_guardado, "wb") as f:
                                f.write(foto.getbuffer())
                                f.flush()
                            
                            if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                                st.session_state["procesados"][file_id] = True
                                hubo_nuevas = True
                    
                    if hubo_nuevas:
                        time.sleep(1)
                        st.rerun()
                    
            with tab2:
                foto_cam = st.camera_input(f"Tomar foto", key=f"cam_{pedido['id']}_{categoria}_{uuid.uuid4().hex[:6]}")
                if foto_cam:
                    file_id = f"{pedido['id']}_{categoria}_{uuid.uuid4().hex[:6]}"
                    if file_id not in st.session_state["procesados"]:
                        nombre = f"{categoria}_{uuid.uuid4().hex[:6]}.jpg"
                        ruta_guardado = os.path.join(ruta_fotos, nombre)
                        
                        with open(ruta_guardado, "wb") as f:
                            f.write(foto_cam.getbuffer())
                            f.flush()
                        
                        if os.path.exists(ruta_guardado) and os.path.getsize(ruta_guardado) > 0:
                            st.session_state["procesados"][file_id] = True
                            time.sleep(1)
                            st.rerun()

    mostrar_otras_categorias("2. Fotos del Camión", "camion")
    mostrar_otras_categorias("3. Fotos del Termógrafo", "termografo")
    mostrar_otras_categorias("4. Fotos de Sellos", "sello")
    mostrar_otras_categorias("5. Fotos del Thermo-king", "thermoking")