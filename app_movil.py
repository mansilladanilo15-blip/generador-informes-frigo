
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
    """Convierte JPG/PNG a JPEG real."""

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
    # CARGA AUTOMÁTICA DE FOTOGRAFÍAS
    # ======================================================

    st.markdown("### 📸 Documentación")

    with st.container(border=True):

        subidas = st.file_uploader(
            "Seleccionar fotografías",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key=f"gal_documentacion_{pedido_id}"
        )

        if subidas:

            total = len(subidas)

            # Consultar fotografías existentes una sola vez
            try:

                existentes = set(
                    nube.obtener_fotos_nube(pedido_id) or []
                )

            except Exception as exc:

                st.error(
                    f"❌ Error consultando las fotografías: {exc}"
                )

                st.stop()


            # Identificar fotografías que aún no se procesaron
            pendientes_carga = []

            for foto in subidas:

                try:

                    contenido = foto.getvalue()
                    jpeg = preparar_jpeg(contenido)

                    firma = hashlib.sha256(
                        jpeg
                    ).hexdigest()[:24]

                    nombre = f"documentacion_{firma}.jpg"

                    clave_procesada = (
                        f"{pedido_id}|{firma}"
                    )

                    if clave_procesada in st.session_state["procesados"]:
                        continue

                    pendientes_carga.append({
                        "nombre_original": foto.name,
                        "jpeg": jpeg,
                        "nombre": nombre,
                        "firma": firma,
                        "clave": clave_procesada
                    })

                except Exception as exc:

                    st.error(
                        f"❌ No se pudo preparar {foto.name}: {exc}"
                    )


            if pendientes_carga:

                cantidad = len(pendientes_carga)

                barra = st.progress(
                    0,
                    text=f"Preparando fotografías: 0/{cantidad}"
                )

                mensaje = st.empty()

                nuevas_ok = 0
                ya_existian = 0
                fallidas = []


                # Procesar y subir automáticamente
                for idx, elemento in enumerate(pendientes_carga):

                    numero = idx + 1

                    mensaje.info(
                        f"⬆️ Subiendo fotografía {numero}/{cantidad}"
                    )

                    try:

                        nombre = elemento["nombre"]

                        if nombre in existentes:

                            ya_existian += 1

                        else:

                            nube.subir_foto_nube(
                                pedido_id,
                                nombre,
                                elemento["jpeg"]
                            )

                            existentes.add(nombre)

                            nuevas_ok += 1


                        # Evitar repetir la misma carga
                        st.session_state["procesados"][
                            elemento["clave"]
                        ] = True


                    except Exception as exc:

                        fallidas.append(
                            f"{elemento['nombre_original']}: {str(exc)}"
                        )


                    barra.progress(
                        numero / cantidad,
                        text=f"Procesadas {numero}/{cantidad}"
                    )


                mensaje.empty()

                st.divider()

                st.subheader("📊 Resultado de la carga")

                st.success(
                    f"✅ Fotografías nuevas: {nuevas_ok}"
                )

                st.info(
                    f"☁️ Fotografías que ya existían: {ya_existian}"
                )

                if fallidas:

                    st.error(
                        f"❌ Fotografías con errores: {len(fallidas)}"
                    )

                    for error in fallidas:
                        st.write(f"• {error}")

                else:

                    st.success(
                        "🎉 Todas las fotografías fueron procesadas correctamente."
                    )

            else:

                st.success(
                    "✅ Las fotografías seleccionadas ya fueron procesadas."
                )


    st.divider()


    # ======================================================
    # GALERÍA DE FOTOGRAFÍAS DEL PEDIDO
    # ======================================================

    st.subheader("🖼️ Fotografías guardadas")

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


                    # Mostrar fotografía sin nombre de archivo
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

                            # Permitir volver a subir una fotografía
                            # si fue eliminada previamente.

                            st.session_state["procesados"] = {}

                            st.cache_data.clear()

                            st.rerun()


                        except Exception as exc:

                            st.error(
                                f"❌ No se pudo borrar la fotografía: {exc}"
                            )


                except Exception as exc:

                    st.error(
                        f"No se pudo mostrar la fotografía: {exc}"
                    )


    else:

        st.info(
            "Todavía no hay fotografías guardadas en este pedido."
        )
