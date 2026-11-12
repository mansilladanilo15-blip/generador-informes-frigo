
import streamlit as st
import base64
import time
import hashlib
from io import BytesIO
from PIL import Image, ImageOps
import conexion_nube as nube


# ==========================================================
# PREPARACIÓN DE IMÁGENES
# ==========================================================

def preparar_jpeg(contenido):
    """Convierte JPG/PNG/cámara a JPEG real."""

    try:
        imagen = Image.open(BytesIO(bytes(contenido)))
        imagen = ImageOps.exif_transpose(imagen)

        if imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        salida = BytesIO()

        imagen.save(
            salida,
            format="JPEG",
            quality=94,
            optimize=True
        )

        resultado = salida.getvalue()

        if not resultado:
            raise ValueError("La imagen quedó vacía al prepararla.")

        return resultado

    except Exception as exc:
        raise ValueError(
            f"No se pudo leer o preparar la imagen: {exc}"
        ) from exc


# ==========================================================
# SUBIDA DE FOTOGRAFÍAS
# ==========================================================

def subir_foto_movil(pedido_id, prefijo, contenido):
    """
    Convierte la imagen a JPEG y la sube a Supabase.
    Utiliza una firma para evitar fotografías duplicadas.
    """

    jpeg = preparar_jpeg(contenido)

    firma = hashlib.sha256(jpeg).hexdigest()[:24]

    nombre = f"{prefijo}{firma}.jpg"

    existentes = nube.obtener_fotos_nube(pedido_id) or []

    if nombre in existentes:
        return nombre, False, firma

    nube.subir_foto_nube(
        pedido_id,
        nombre,
        jpeg
    )

    return nombre, True, firma


# ==========================================================
# ELIMINACIÓN INDIVIDUAL VERIFICADA
# ==========================================================

def eliminar_foto_verificada(pedido_id, nombre_foto, intentos=3):
    """Elimina una fotografía y verifica que desaparezca de Storage."""

    ultimo_error = None

    try:
        nube.borrar_foto_nube(
            pedido_id,
            nombre_foto
        )

    except Exception as exc:
        ultimo_error = exc

    for intento in range(intentos):

        try:

            fotos_restantes = (
                nube.obtener_fotos_nube(pedido_id) or []
            )

            if nombre_foto not in fotos_restantes:
                return True

        except Exception as exc:

            ultimo_error = exc

        if intento < intentos - 1:
            time.sleep(0.8)

    detalle = (
        f" Detalle: {ultimo_error}"
        if ultimo_error
        else ""
    )

    raise RuntimeError(
        f"No se pudo confirmar el borrado de "
        f"'{nombre_foto}'.{detalle}"
    )


# ==========================================================
# CONFIGURACIÓN DE STREAMLIT
# ==========================================================

st.set_page_config(
    page_title="App Operarios",
    page_icon="🚚",
    layout="centered"
)


# ==========================================================
# OCULTAR BARRA SUPERIOR DE STREAMLIT
# ==========================================================

st.markdown("""
    <style>

        header[data-testid="stHeader"] {
            display: none !important;
        }

        [data-testid="stToolbar"] {
            display: none !important;
        }

        [data-testid="stDecoration"] {
            display: none !important;
        }

        #MainMenu {
            visibility: hidden !important;
        }

        footer {
            visibility: hidden !important;
        }

        .stDeployButton,
        [data-testid="stAppDeployButton"],
        [data-testid="stAppDeployButton"] button,
        button[aria-label="Manage app"],
        [title="Manage app"] {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }

    </style>
""", unsafe_allow_html=True)


# ==========================================================
# VARIABLES DE SESIÓN
# ==========================================================

if "procesados" not in st.session_state:
    st.session_state["procesados"] = {}

if "confirmar_borrado_movil" not in st.session_state:
    st.session_state["confirmar_borrado_movil"] = False


# ==========================================================
# ENCABEZADO
# ==========================================================

st.title("📱 FRIGORIFICO DUMESTRE")

st.markdown(
    """
    <p style="
        text-align:center;
        color:#64748b;
        font-size:14px;
        margin-top:-12px;
    ">
        Carga de fotografías de despacho
    </p>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# OBTENER PEDIDOS
# ==========================================================

todos_los_pedidos = nube.obtener_pedidos_nube() or []

if not todos_los_pedidos:

    st.warning("⚠️ No hay pedidos creados en la nube.")
    st.stop()


pendientes = [
    p for p in todos_los_pedidos
    if p.get("estado") != "Finalizado"
]

finalizados = [
    p for p in todos_los_pedidos
    if p.get("estado") == "Finalizado"
]


# ==========================================================
# PEDIDOS PENDIENTES
# ==========================================================

st.subheader("🟡 Pedidos Pendientes")

if pendientes:

    opciones_pendientes = {
        f"{p['nro_pedido']} - {p['cliente']}": p
        for p in pendientes
    }

    pedido_seleccionado = st.selectbox(
        "Selecciona un pedido:",
        list(opciones_pendientes.keys())
    )

    pedido = opciones_pendientes[pedido_seleccionado]

else:

    st.success("🎉 ¡No hay pedidos pendientes!")

    pedido = None


# ==========================================================
# HISTORIAL DE PEDIDOS FINALIZADOS
# ==========================================================

with st.expander(
    "📂 Historial de Finalizados",
    expanded=False
):

    if finalizados:

        for p in finalizados:

            st.write(
                f"🔒 {p['nro_pedido']} - {p['cliente']}"
            )

    else:

        st.info("Aún no hay pedidos finalizados.")


st.divider()


# ==========================================================
# INFORMACIÓN DEL PEDIDO SELECCIONADO
# ==========================================================

if pedido:

    if pedido.get("estado") == "Finalizado":

        st.success(
            "🔒 **ESTE PEDIDO HA SIDO FINALIZADO**"
        )

        st.stop()


    # ------------------------------------------------------
    # TÍTULO DEL PEDIDO
    # ------------------------------------------------------

    if pedido.get("tipo") == "Traslado":

        titulo_cartel = (
            f"🚚 Traslado: "
            f"{pedido.get('nro_entrega', pedido['nro_pedido'])}"
        )

        subtitulo_cartel = (
            f"Destino: {pedido.get('cliente', '-')}"
        )

    else:

        titulo_cartel = (
            f"📦 Pedido: {pedido['nro_pedido']}"
        )

        nro_entrega = pedido.get("nro_entrega")

        if nro_entrega and str(nro_entrega).strip() not in ("", "-"):

            subtitulo_cartel = (
                f"Entrega: {nro_entrega} | "
                f"Cliente: {pedido.get('cliente', '-')}"
            )

        else:

            subtitulo_cartel = (
                f"Cliente: {pedido.get('cliente', '-')}"
            )


    with st.container(border=True):

        st.markdown(
            f"""
            <h2 style="
                text-align:center;
                color:#1a4d8f;
            ">
                {titulo_cartel}
            </h2>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <h4 style="text-align:center;">
                {subtitulo_cartel}
            </h4>
            """,
            unsafe_allow_html=True
        )


    pedido_id = pedido["id"]


    # ======================================================
    # CONFIRMACIÓN DE ELIMINACIÓN
    # ======================================================

    if st.session_state.get("confirmar_borrado_movil"):

        st.success(
            "✅ Borrado confirmado en la nube."
        )

        if st.button(
            "🔄 Actualizar Galería",
            type="primary",
            width="stretch"
        ):

            st.session_state["confirmar_borrado_movil"] = False

            st.cache_data.clear()

            st.rerun()


    # ======================================================
    # ÚNICA SECCIÓN: DOCUMENTACIÓN
    # ======================================================

    st.markdown("### 📸 Documentación")

    st.info(
        "Puedes seleccionar varias fotografías desde tu galería "
        "o tomar fotografías directamente con la cámara. "
        "Todas quedarán guardadas en este pedido para que "
        "el administrador las clasifique desde la aplicación de PC."
    )


    with st.expander(
        "📸 Cargar fotografías",
        expanded=True
    ):

        vista_documentacion = st.radio(
            "Selecciona cómo deseas cargar las fotografías:",
            ["🖼️ Galería", "📷 Cámara"],
            horizontal=True,
            key=f"vista_documentacion_{pedido_id}"
        )




        # ==================================================
        # SUBIR MÚLTIPLES FOTOGRAFÍAS DESDE GALERÍA
        # ==================================================

        if vista_documentacion == "🖼️ Galería":

            subidas = st.file_uploader(
                "Seleccionar fotografías",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"gal_documentacion_{pedido_id}"
            )

            if subidas:

                total = len(subidas)

                peso_total = sum(
                    foto.size for foto in subidas
                )

                st.success(
                    f"📁 Fotografías recibidas: {total}"
                )

                st.info(
                    f"Peso total: {peso_total / (1024 * 1024):.2f} MB"
                )

                with st.expander("Ver archivos seleccionados"):

                    for foto in subidas:
                        st.write(
                            f"📷 {foto.name} — "
                            f"{foto.size / 1024:.1f} KB"
                        )

                st.divider()

                if st.button(
                    "⬆️ SUBIR FOTOGRAFÍAS",
                    type="primary",
                    width="stretch",
                    key=f"btn_subir_{pedido_id}"
                ):

                    barra = st.progress(
                        0,
                        text=f"Preparando carga: 0/{total}"
                    )

                    mensaje = st.empty()

                    nuevas_ok = 0
                    ya_existian = 0
                    fallidas = []

                    # Consultar Storage una sola vez
                    try:

                        existentes = set(
                            nube.obtener_fotos_nube(
                                pedido_id
                            ) or []
                        )

                    except Exception as exc:

                        st.error(
                            f"Error consultando Supabase: {exc}"
                        )

                        st.stop()

                    # Procesar fotografías individualmente
                    for idx, foto in enumerate(subidas):

                        numero = idx + 1

                        mensaje.info(
                            f"⬆️ Subiendo {numero}/{total}: "
                            f"{foto.name}"
                        )

                        try:

                            contenido = foto.getvalue()

                            jpeg = preparar_jpeg(contenido)

                            firma = hashlib.sha256(
                                jpeg
                            ).hexdigest()[:24]

                            nombre = (
                                f"documentacion_{firma}.jpg"
                            )

                            if nombre in existentes:

                                ya_existian += 1

                            else:

                                nube.subir_foto_nube(
                                    pedido_id,
                                    nombre,
                                    jpeg
                                )

                                existentes.add(nombre)

                                nuevas_ok += 1

                        except Exception as exc:

                            fallidas.append(
                                f"{foto.name}: {str(exc)}"
                            )

                        barra.progress(
                            numero / total,
                            text=(
                                f"Procesadas {numero}/{total}"
                            )
                        )

                    mensaje.empty()

                    st.divider()

                    st.subheader("📊 Resultado de la carga")

                    st.success(
                        f"✅ Fotografías nuevas: {nuevas_ok}"
                    )

                    st.info(
                        f"☁️ Fotografías que ya existían: "
                        f"{ya_existian}"
                    )

                    if fallidas:

                        st.error(
                            f"❌ Fotografías con errores: "
                            f"{len(fallidas)}"
                        )

                        for error in fallidas:
                            st.write(f"• {error}")

                    else:

                        st.success(
                            "🎉 Todas las fotografías fueron "
                            "procesadas correctamente."
                        )

                    st.caption(
                        "Actualiza la página para consultar "
                        "la galería de fotografías guardadas."
                    )



        # ==================================================
        # TOMAR FOTOGRAFÍAS CON CÁMARA
        # ==================================================

        elif vista_documentacion == "📷 Cámara":

            cam = st.camera_input(
                "Tomar fotografía",
                key=f"cam_documentacion_{pedido_id}"
            )


            if cam:

                try:

                    jpeg = preparar_jpeg(
                        cam.getvalue()
                    )

                    firma = hashlib.sha256(
                        jpeg
                    ).hexdigest()[:24]

                    clave_procesada = (
                        f"{pedido_id}|cam_documentacion|{firma}"
                    )


                    if clave_procesada in st.session_state["procesados"]:

                        st.info(
                            "ℹ️ Esta fotografía ya fue procesada."
                        )

                    else:

                        _, creada, firma = subir_foto_movil(
                            pedido_id,
                            "documentacion_",
                            jpeg
                        )

                        st.session_state["procesados"][
                            clave_procesada
                        ] = True

                        if creada:

                            st.success(
                                "✅ Fotografía guardada correctamente."
                            )

                        else:

                            st.info(
                                "ℹ️ Esta fotografía ya estaba guardada "
                                "y no se creó un duplicado."
                            )


                except Exception as exc:

                    st.error(
                        f"❌ No se pudo subir la fotografía: {exc}"
                    )


    st.divider()


    # ======================================================
    # GALERÍA ÚNICA DE FOTOGRAFÍAS DEL PEDIDO
    # ======================================================

    st.subheader("🖼️ Fotografías guardadas")

    # Se muestran todas las fotografías del pedido,
    # incluidas las que ya existían con otros prefijos.
    # Así no se ocultan fotografías antiguas.

    fotos_guardadas = nube.obtener_fotos_nube(
        pedido_id
    ) or []


    if fotos_guardadas:

        st.caption(
            f"Total de fotografías en este pedido: "
            f"{len(fotos_guardadas)}"
        )

        cols = st.columns(2)

        for idx, nombre_foto in enumerate(fotos_guardadas):

            with cols[idx % 2]:

                try:

                    bytes_img = nube.descargar_foto_nube(
                        pedido_id,
                        nombre_foto
                    )

                    b64 = base64.b64encode(
                        bytes_img
                    ).decode("utf-8")


                    mime = (
                        "image/png"
                        if nombre_foto.lower().endswith(".png")
                        else "image/jpeg"
                    )


                    st.markdown(
                        f"""
                        <div style="
                            text-align:center;
                            margin-bottom:5px;
                        ">
                            <img
                                src="data:{mime};base64,{b64}"
                                style="
                                    width:100%;
                                    height:160px;
                                    object-fit:cover;
                                    border-radius:8px;
                                    border:1px solid #ddd;
                                "
                            >

                            <div style="
                                font-size:11px;
                                color:#64748b;
                                margin-top:4px;
                                overflow-wrap:anywhere;
                            ">
                                {nombre_foto}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                    if st.button(
                        "🗑️ Borrar",
                        key=f"del_foto_{pedido_id}_{nombre_foto}",
                        width="stretch"
                    ):

                        try:

                            eliminar_foto_verificada(
                                pedido_id,
                                nombre_foto
                            )

                            st.session_state[
                                "confirmar_borrado_movil"
                            ] = True

                            # Permite volver a subir una fotografía
                            # si se eliminó previamente.

                            st.session_state["procesados"] = {}

                            st.cache_data.clear()

                            st.rerun()


                        except Exception as exc:

                            st.error(
                                f"❌ No se pudo borrar la fotografía: {exc}"
                            )


                except Exception as exc:

                    st.error(
                        f"No se pudo mostrar {nombre_foto}: {exc}"
                    )


    else:

        st.info(
            "Todavía no hay fotografías guardadas en este pedido."
        )
