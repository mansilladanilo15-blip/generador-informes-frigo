import time
import uuid
import streamlit as st

def renderizar_galeria(key, fotos, pedido_id, cols_num=4):
    # Filtrar fotos ocultas en la sesión actual
    if "fotos_ocultas" not in st.session_state:
        st.session_state["fotos_ocultas"] = set()
        
    fotos_visibles = [f for f in fotos if f not in st.session_state["fotos_ocultas"]]
    if not fotos_visibles:
        st.info("No hay fotos en esta sección o ya fueron procesadas.")
        return

    # Usar un identificador seguro para las keys evitando errores si RC no existe
    rc_suffix = globals().get("RC", "gral")

    cols = st.columns(cols_num)
    for i, f in enumerate(fotos_visibles):
        with cols[i % cols_num]:
            img_placeholder = st.empty()
            bytes_img = None
            try:
                bytes_img = nube.descargar_foto_nube(pedido_id, f)
                b64 = convertir_a_base64(bytes_img, max_ancho=400)
                if b64:
                    img_placeholder.markdown(
                        f'<img src="{b64}" style="width:100%; border:1px solid #ddd; border-radius:6px; margin-bottom:6px;">', 
                        unsafe_allow_html=True
                    )
            except Exception:
                img_placeholder.warning("⚠️ Error al cargar")

            # Botones de Acción (Zoom y Borrar)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Ver", key=f"{key}_zoom_{i}_{rc_suffix}_{f}", use_container_width=True):
                    if bytes_img:
                        mostrar_zoom(f, bytes_img)
                    else:
                        st.error("No se pudo cargar la imagen para ampliar.")
                        
            with col2:
                if st.button("🗑️ Borrar", key=f"{key}_del_{i}_{rc_suffix}_{f}", use_container_width=True):
                    with st.spinner("Borrando foto..."):
                        try:
                            nube.borrar_foto_nube(pedido_id, f)
                            st.session_state["fotos_ocultas"].add(f)
                            st.success("¡Eliminada!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al borrar: {e}")

            # Selector y botón para Mover de categoría
            opciones = [
                "Mantener aquí", 
                "Mover a Documentación", 
                "Mover a Camión", 
                "Mover a Termógrafo", 
                "Mover a Sello", 
                "Mover a Thermo-king"
            ]
            # Evitar que se mueva a su propia categoría actual
            opciones_filtradas = [op for op in opciones if op != f"Mover a {key.capitalize()}"]
            
            destino = st.selectbox(
                "Mover foto a:", 
                opciones_filtradas, 
                key=f"derivar_{key}_{i}_{rc_suffix}_{f}", 
                label_visibility="collapsed"
            )

            if destino != "Mantener aquí":
                if st.button("➡️ Confirmar", key=f"btn_mover_{key}_{i}_{rc_suffix}_{f}", use_container_width=True):
                    with st.spinner("Moviendo archivo..."):
                        try:
                            mapeo_prefijos = {
                                "Mover a Documentación": "documentacion_",
                                "Mover a Camión": "camion_",
                                "Mover a Termógrafo": "termografo_",
                                "Mover a Sello": "sello_",
                                "Mover a Thermo-king": "thermoking_"
                            }
                            prefijo = mapeo_prefijos[destino]
                            nuevo_nombre = f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                            
                            # Si ya descargamos los bytes arriba, los reutilizamos para ahorrar peticiones
                            if not bytes_img:
                                bytes_img = nube.descargar_foto_nube(pedido_id, f)
                                
                            nube.subir_foto_nube(pedido_id, nuevo_nombre, bytes_img)
                            nube.borrar_foto_nube(pedido_id, f)
                            
                            st.session_state["fotos_ocultas"].add(f)
                            st.success("¡Movido con éxito!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al mover: {e}")
