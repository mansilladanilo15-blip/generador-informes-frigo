
import streamlit as st
import uuid
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
    """Convierte JPG/PNG/cámara a JPEG real para que extensión y contenido coincidan."""
    try:
        imagen = Image.open(BytesIO(bytes(contenido)))
        imagen = ImageOps.exif_transpose(imagen)

        if imagen.mode != "RGB":
            imagen = imagen.convert("RGB")

        salida = BytesIO()
        imagen.save(salida, format="JPEG", quality=94, optimize=True)

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
    """Nombre determinista por contenido: reintentar una subida no crea otra foto."""

    jpeg = preparar_jpeg(contenido)

    firma = hashlib.sha256(jpeg).hexdigest()[:24]

    nombre = f"{prefijo}{firma}.jpg"

    existentes = nube.obtener_fotos_nube(pedido_id)

    if nombre in existentes:
        return nombre, False, firma

    nube.subir_foto_nube(pedido_id, nombre, jpeg)

    return nombre, True, firma


# ==========================================================
# ELIMINACIÓN INDIVIDUAL VERIFICADA
# ==========================================================

def eliminar_foto_verificada(pedido_id, nombre_foto, intentos=3):
    """Elimina una foto con la función existente y verifica el listado remoto."""

    ultimo_error = None

    try:
        nube.borrar_foto_nube(pedido_id, nombre_foto)

    except Exception as exc:
        ultimo_error = exc

    for intento in range(intentos):

        try:
            fotos_restantes = nube.obtener_fotos_nube(pedido_id) or []

            if nombre_foto not in fotos_restantes:
                return True

        except Exception as exc:
            ultimo_error = exc

        if intento < intentos - 1:
            time.sleep(0.8)

    detalle = f" Detalle: {ultimo_error}" if ultimo_error else ""

    raise RuntimeError(
        f"No se pudo confirmar el borrado de '{nombre_foto}'.{detalle}"
    )


# ==========================================================
# LIMPIAR REFERENCIAS DE ESTIBAS
# ==========================================================

def limpiar_referencias_estiba(pedido_id, nombre_foto):
    """Limpia solo las referencias de la foto en los campos existentes."""

    pedidos = nube.obtener_pedidos_nube() or []

    pedido_data = next(
        (
            p.copy()
            for p in pedidos
            if str(p.get("id")) == str(pedido_id)
        ),
        None
    )

    if pedido_data is None:
        raise RuntimeError(
            "No se encontró el pedido para limpiar los datos de estiba."
        )

    cajas = pedido_data.get("cajas_estibas", {}) or {}
    patas = pedido_data.get("patas_estibas", {}) or {}

    cajas.pop(nombre_foto, None)
    patas.pop(nombre_foto, None)

    pedido_data["cajas_estibas"] = cajas
    pedido_data["patas_estibas"] = patas

    nube.subir_pedido_nube(pedido_id, pedido_data)


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

        /* Oculta el botón "Manage app" de Streamlit Community Cloud */
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

if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False

if "subida_terminada" not in st.session_state:
    st.session_state["subida_terminada"] = False

if "procesados" not in st.session_state:
    st.session_state["procesados"] = {}

if "confirmar_borrado_movil" not in st.session_state:
    st.session_state["confirmar_borrado_movil"] = False


# ==========================================================
# ENCABEZADO
# ==========================================================

st.title("📱  FRIGORIFICO DUMESTRE")


# ==========================================================
# OBTENER PEDIDOS
# ==========================================================

todos_los_pedidos = nube.obtener_pedidos_nube()

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

with st.expander("📂 Historial de Finalizados", expanded=False):

    if finalizados:

        for p in finalizados:
            st.write(
                f"🔒 {p['nro_pedido']} - {p['cliente']}"
            )

    else:

        st.info("Aún no hay finalizados.")


st.divider()


# ==========================================================
# INFORMACIÓN DEL PEDIDO SELECCIONADO
# ==========================================================

if pedido:

    if pedido.get("estado") == "Finalizado":

        st.success("🔒 **ESTE PEDIDO HA SIDO FINALIZADO**")

        st.stop()



    if pedido.get("tipo") == "Traslado":

        titulo_cartel = f"🚚 Traslado: {pedido.get('nro_entrega', pedido['nro_pedido'])}"
        subtitulo_cartel = f"Destino: {pedido.get('cliente', '-')}"

    else:

        titulo_cartel = f"📦 Pedido: {pedido['nro_pedido']}"

        nro_entrega = pedido.get("nro_entrega")

        if nro_entrega and str(nro_entrega).strip() not in ("", "-"):
            subtitulo_cartel = (
                f"Entrega: {nro_entrega} | Cliente: {pedido.get('cliente', '-')}"
            )
        else:
            subtitulo_cartel = f"Cliente: {pedido.get('cliente', '-')}"

    with st.container(border=True):

        st.markdown(
            f"<h2 style='text-align:center; color:#1a4d8f;'>{titulo_cartel}</h2>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<h4 style='text-align:center;'>{subtitulo_cartel}</h4>",
            unsafe_allow_html=True
        )

    pedido_id = pedido["id"]



    # ======================================================
    # CONFIRMACIÓN DE ELIMINACIÓN INDIVIDUAL
    # ======================================================

    if st.session_state.get("confirmar_borrado_movil"):

        st.success("✅ Borrado confirmado en la nube.")

        if st.button(
            "🔄 Actualizar Galería",
            type="primary",
            width="stretch"
        ):

            st.session_state["confirmar_borrado_movil"] = False
            st.session_state.clear()
            st.cache_data.clear()
            st.rerun()


    # ======================================================
    # DATOS DE ESTIBAS DEL PEDIDO
    # ======================================================

    pedido_data = next(
        (
            p for p in nube.obtener_pedidos_nube()
            if p["id"] == pedido_id
        ),
        {}
    )

    cajas_nube = pedido_data.get("cajas_estibas", {}) or {}
    patas_nube = pedido_data.get("patas_estibas", {}) or {}


    # ======================================================
    # 0. DOCUMENTACIÓN
    # ======================================================

    fotos_doc = nube.obtener_fotos_nube(pedido_id) or []

    fotos_doc = [
        f for f in fotos_doc
        if f.startswith("documentacion_")
    ]


    with st.expander(
        f"📄 0. Documentación ({len(fotos_doc)})",
        expanded=True
    ):

        vista_doc = st.radio(
            "Selecciona una opción:",
            ["🖼️ Galería", "📷 Cámara"],
            horizontal=True,
            key=f"vista_doc_{pedido_id}"
        )


        # --------------------------------------------------
        # GALERÍA DE DOCUMENTACIÓN
        # --------------------------------------------------

        if vista_doc == "🖼️ Galería":

            subidas = st.file_uploader(
                "Subir documentación",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"gal_doc_{pedido_id}"
            )

            if subidas:

                progreso = st.progress(0)
                texto_prog = st.empty()

                total = len(subidas)

                nuevas_ok = 0
                ya_existian = 0
                fallidas = []

                for idx, foto in enumerate(subidas):

                    texto_prog.info(
                        f"⏳ Verificando {idx + 1} de {total}: {foto.name}"
                    )

                    try:

                        _, creada, firma = subir_foto_movil(
                            pedido_id,
                            "documentacion_",
                            foto.getvalue()
                        )

                        st.session_state["procesados"][
                            f"{pedido_id}|documentacion|{firma}"
                        ] = True

                        nuevas_ok += int(creada)
                        ya_existian += int(not creada)

                    except Exception as exc:

                        fallidas.append(f"{foto.name}: {exc}")

                    progreso.progress((idx + 1) / total)


                progreso.empty()
                texto_prog.empty()

                if nuevas_ok:
                    st.success(
                        f"✅ Documentación nueva guardada: {nuevas_ok}."
                    )

                if ya_existian:
                    st.info(
                        f"ℹ️ Fotos ya existentes, sin duplicar: {ya_existian}."
                    )

                if fallidas:

                    st.error("No se pudieron subir todas las fotos:")

                    for error in fallidas:
                        st.write(f"• {error}")


        # --------------------------------------------------
        # CÁMARA DE DOCUMENTACIÓN
        # --------------------------------------------------

        elif vista_doc == "📷 Cámara":

            cam = st.camera_input(
                "Tomar foto",
                key=f"cam_doc_{pedido_id}"
            )

            if cam:

                try:

                    _, creada, firma = subir_foto_movil(
                        pedido_id,
                        "documentacion_",
                        cam.getvalue()
                    )

                    if creada:

                        st.session_state["procesados"][
                            f"{pedido_id}|cam_documentacion|{firma}"
                        ] = True

                        st.success("✅ Foto guardada en la nube.")

                    else:

                        st.info(
                            "ℹ️ Esta foto ya estaba guardada; "
                            "no se creó un duplicado."
                        )

                except Exception as exc:

                    st.error(f"❌ No se pudo subir la foto: {exc}")


        # --------------------------------------------------
        # GALERÍA DE DOCUMENTACIÓN GUARDADA
        # --------------------------------------------------

        if fotos_doc:

            cols = st.columns(2)

            for idx, f in enumerate(fotos_doc):

                with cols[idx % 2]:

                    bytes_img = nube.descargar_foto_nube(
                        pedido_id,
                        f
                    )

                    b64 = base64.b64encode(bytes_img).decode("utf-8")

                    mime = (
                        "image/png"
                        if f.lower().endswith(".png")
                        else "image/jpeg"
                    )

                    st.markdown(f"""
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
                    """, unsafe_allow_html=True)


                    if st.button(
                        "🗑️ Borrar",
                        key=f"del_doc_{pedido_id}_{f}",
                        width="stretch"
                    ):

                        try:

                            eliminar_foto_verificada(
                                pedido_id,
                                f
                            )

                            st.session_state[
                                "confirmar_borrado_movil"
                            ] = True

                            st.session_state["procesados"] = {}
                            st.session_state["subida_terminada"] = False

                            st.cache_data.clear()
                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"❌ No se pudo borrar la foto: {exc}"
                            )


    st.divider()


    # ======================================================
    # 1. ESTIBAS
    # ======================================================

    fotos_estibas = nube.obtener_fotos_nube(pedido_id) or []

    fotos_estibas = [
        f for f in fotos_estibas
        if f.startswith("estiba_pata_")
    ]


    if "expand_estibas" not in st.session_state:
        st.session_state["expand_estibas"] = True


    with st.expander(
        f"📦 1. Estibas ({len(fotos_estibas)})",
        expanded=st.session_state["expand_estibas"]
    ):

        vista_estibas = st.radio(
            "Selecciona una opción:",
            ["🖼️ Galería", "📷 Cámara"],
            horizontal=True,
            key=f"vista_estibas_{pedido_id}"
        )


        # --------------------------------------------------
        # GALERÍA DE ESTIBAS
        # --------------------------------------------------

        if vista_estibas == "🖼️ Galería":

            subidas = st.file_uploader(
                "Selecciona varias fotos",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"gal_estibas_multi_{pedido_id}"
            )

            if subidas:

                progreso = st.progress(0)
                texto_prog = st.empty()

                total = len(subidas)

                nuevas_ok = 0
                ya_existian = 0
                fallidas = []

                for idx, foto in enumerate(subidas):

                    texto_prog.info(
                        f"⏳ Verificando {idx + 1} de {total}: {foto.name}"
                    )

                    try:

                        _, creada, firma = subir_foto_movil(
                            pedido_id,
                            "estiba_pata_99_REVISAR_",
                            foto.getvalue()
                        )

                        st.session_state["procesados"][
                            f"{pedido_id}|estiba|{firma}"
                        ] = True

                        nuevas_ok += int(creada)
                        ya_existian += int(not creada)

                    except Exception as exc:

                        fallidas.append(f"{foto.name}: {exc}")

                    progreso.progress((idx + 1) / total)


                progreso.empty()
                texto_prog.empty()

                if nuevas_ok:

                    st.success(
                        f"✅ Fotos de estiba nuevas guardadas: {nuevas_ok}."
                    )

                if ya_existian:

                    st.info(
                        "ℹ️ Fotos que ya estaban en la nube "
                        f"y no se duplicaron: {ya_existian}."
                    )

                if fallidas:

                    st.error("No se pudieron subir todas las fotos:")

                    for error in fallidas:
                        st.write(f"• {error}")


        # --------------------------------------------------
        # CÁMARA DE ESTIBAS
        # --------------------------------------------------

        elif vista_estibas == "📷 Cámara":

            cam = st.camera_input(
                "Tomar foto",
                key=f"cam_estiba_{pedido_id}"
            )

            if cam:

                try:

                    _, creada, firma = subir_foto_movil(
                        pedido_id,
                        "estiba_pata_99_REVISAR_",
                        cam.getvalue()
                    )

                    if creada:

                        st.session_state["procesados"][
                            f"{pedido_id}|cam_estiba|{firma}"
                        ] = True

                        st.success(
                            "✅ Foto de estiba guardada. "
                            "El administrador puede procesarla desde la PC."
                        )

                    else:

                        st.info(
                            "ℹ️ Esta foto ya estaba guardada; "
                            "no se creó un duplicado."
                        )

                except Exception as exc:

                    st.error(
                        f"❌ No se pudo subir la foto de estiba: {exc}"
                    )


        st.divider()


        # --------------------------------------------------
        # GALERÍA DE ESTIBAS GUARDADAS
        # --------------------------------------------------

        if fotos_estibas:

            cols = st.columns(2)

            for idx, f in enumerate(fotos_estibas):

                with cols[idx % 2]:

                    bytes_img = nube.descargar_foto_nube(
                        pedido_id,
                        f
                    )

                    b64 = base64.b64encode(bytes_img).decode("utf-8")

                    mime = (
                        "image/png"
                        if f.lower().endswith(".png")
                        else "image/jpeg"
                    )

                    pata_asignada = patas_nube.get(
                        f,
                        f.split("_")[2].replace(".jpg", "").split("_")[0]
                    )

                    cajas = cajas_nube.get(f, 0)


                    st.markdown(f"""
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
                                font-size:12px;
                                color:#1a4d8f;
                                font-weight:bold;
                                margin-top:2px;
                            ">
                                📦 Pata {pata_asignada} ({cajas} cajas)
                            </div>
                        </div>
                    """, unsafe_allow_html=True)


                    if st.button(
                        "🗑️ Borrar",
                        key=f"del_estiba_{pedido_id}_{f}",
                        width="stretch"
                    ):

                        try:

                            eliminar_foto_verificada(
                                pedido_id,
                                f
                            )

                            limpiar_referencias_estiba(
                                pedido_id,
                                f
                            )

                            st.session_state[
                                "confirmar_borrado_movil"
                            ] = True

                            st.session_state["procesados"] = {}
                            st.session_state["subida_terminada"] = False

                            st.cache_data.clear()
                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"❌ No se pudo borrar la foto de estiba: {exc}"
                            )

        else:

            st.info("No hay fotos de estibas subidas.")


    st.divider()


    # ======================================================
    # OTRAS CATEGORÍAS
    # ======================================================

    st.markdown("### 📸 Otras Categorías")


    def mostrar_categoria(titulo, prefijo):

        fotos_brutas = nube.obtener_fotos_nube(pedido_id) or []

        fotos = [
            f for f in fotos_brutas
            if f.startswith(prefijo)
        ]


        with st.expander(
            f"{titulo} ({len(fotos)})",
            expanded=False
        ):


            # ----------------------------------------------
            # FOTOGRAFÍAS GUARDADAS
            # ----------------------------------------------

            if fotos:

                cols = st.columns(2)

                for idx, f in enumerate(fotos):

                    with cols[idx % 2]:

                        bytes_img = nube.descargar_foto_nube(
                            pedido_id,
                            f
                        )

                        b64 = base64.b64encode(
                            bytes_img
                        ).decode("utf-8")


                        st.markdown(f"""
                            <div style="
                                text-align:center;
                                margin-bottom:5px;
                            ">
                                <img
                                    src="data:image/jpeg;base64,{b64}"
                                    style="
                                        width:100%;
                                        height:160px;
                                        object-fit:cover;
                                        border-radius:8px;
                                        border:1px solid #ddd;
                                    "
                                >
                            </div>
                        """, unsafe_allow_html=True)


                        if st.button(
                            "🗑️ Borrar",
                            key=f"del_{pedido_id}_{f}",
                            width="stretch"
                        ):

                            try:

                                eliminar_foto_verificada(
                                    pedido_id,
                                    f
                                )

                                st.session_state[
                                    "confirmar_borrado_movil"
                                ] = True

                                st.session_state["procesados"] = {}
                                st.session_state["subida_terminada"] = False

                                st.cache_data.clear()
                                st.rerun()

                            except Exception as exc:

                                st.error(
                                    f"❌ No se pudo borrar la foto: {exc}"
                                )


            # ----------------------------------------------
            # SELECTOR GALERÍA / CÁMARA
            # ----------------------------------------------

            vista_categoria = st.radio(
                "Selecciona una opción:",
                ["🖼️ Galería", "📷 Cámara"],
                horizontal=True,
                key=f"vista_{pedido_id}_{prefijo}"
            )


            # ----------------------------------------------
            # SUBIR DESDE GALERÍA
            # ----------------------------------------------

            if vista_categoria == "🖼️ Galería":

                subidas = st.file_uploader(
                    "Subir fotos",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key=f"gal_{pedido_id}_{prefijo}"
                )

                if subidas:

                    progreso = st.progress(0)
                    texto_prog = st.empty()

                    total = len(subidas)

                    nuevas_ok = 0
                    ya_existian = 0
                    fallidas = []

                    for idx, foto_categoria in enumerate(subidas):

                        texto_prog.info(
                            f"⏳ Verificando {idx + 1} de {total}: "
                            f"{foto_categoria.name}"
                        )

                        try:

                            _, creada, firma = subir_foto_movil(
                                pedido_id,
                                prefijo,
                                foto_categoria.getvalue()
                            )

                            st.session_state["procesados"][
                                f"{pedido_id}|{prefijo}|{firma}"
                            ] = True

                            nuevas_ok += int(creada)
                            ya_existian += int(not creada)

                        except Exception as exc:

                            fallidas.append(
                                f"{foto_categoria.name}: {exc}"
                            )

                        progreso.progress((idx + 1) / total)


                    progreso.empty()
                    texto_prog.empty()

                    if nuevas_ok:

                        st.success(
                            f"✅ Fotos nuevas guardadas: {nuevas_ok}."
                        )

                    if ya_existian:

                        st.info(
                            "ℹ️ Fotos que ya estaban guardadas, "
                            f"sin duplicar: {ya_existian}."
                        )

                    if fallidas:

                        st.error("No se pudieron subir todas las fotos:")

                        for error in fallidas:
                            st.write(f"• {error}")


            # ----------------------------------------------
            # TOMAR FOTO CON CÁMARA
            # ----------------------------------------------

            elif vista_categoria == "📷 Cámara":

                cam = st.camera_input(
                    "Tomar foto",
                    key=f"cam_{pedido_id}_{prefijo}"
                )

                if cam:

                    try:

                        _, creada, firma = subir_foto_movil(
                            pedido_id,
                            prefijo,
                            cam.getvalue()
                        )

                        if creada:

                            st.session_state["procesados"][
                                f"{pedido_id}|cam_{prefijo}|{firma}"
                            ] = True

                            st.success("✅ Foto guardada en la nube.")

                        else:

                            st.info(
                                "ℹ️ Esta foto ya estaba guardada; "
                                "no se creó un duplicado."
                            )

                    except Exception as exc:

                        st.error(
                            f"❌ No se pudo subir la foto: {exc}"
                        )


    # ======================================================
    # CATEGORÍAS DE FOTOGRAFÍAS
    # ======================================================

    mostrar_categoria(
        "2. Fotos Camión",
        "camion_"
    )

    mostrar_categoria(
        "3. Termógrafo",
        "termografo_"
    )

    mostrar_categoria(
        "4. Sellos",
        "sello_"
    )

    mostrar_categoria(
        "5. Thermo-king",
        "thermoking_"
    )
