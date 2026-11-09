import streamlit as st
import pandas as pd
from datetime import date, datetime
import base64
from io import BytesIO
from PIL import Image, ImageOps
import uuid
import hashlib
import time
import logging
import hmac

import conexion_nube as nube
import config
from generador import generar_informe


st.set_page_config(
    page_title="Generador de Informes",
    page_icon="📄",
    layout="wide"
)


# ============================================================
# CONTROL DE ACCESO ADMINISTRATIVO
# ============================================================

try:
    _ADMIN_PASSWORD_CONFIGURADA = str(
        st.secrets.get("ADMIN_PASSWORD", "")
    )
except Exception:
    _ADMIN_PASSWORD_CONFIGURADA = ""

if not _ADMIN_PASSWORD_CONFIGURADA:
    st.error(
        "🔐 Falta configurar ADMIN_PASSWORD en los Secrets "
        "de Streamlit. La aplicación está bloqueada por seguridad."
    )
    st.stop()

if not st.session_state.get("admin_autenticado", False):
    st.title("🔐 Acceso de administración")
    st.caption(
        "Ingresa la contraseña administrativa para abrir "
        "el generador de informes."
    )

    with st.form("form_acceso_admin", clear_on_submit=True):
        _password_ingresada = st.text_input(
            "Contraseña administrativa",
            type="password"
        )

        _intento_login = st.form_submit_button(
            "Ingresar",
            type="primary",
            use_container_width=True
        )

    if _intento_login:
        if hmac.compare_digest(
            _password_ingresada,
            _ADMIN_PASSWORD_CONFIGURADA
        ):
            st.session_state["admin_autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    st.stop()


if st.sidebar.button(
    "🔒 Cerrar sesión administrativa",
    use_container_width=True
):
    st.session_state.pop("admin_autenticado", None)
    st.rerun()


# ============================================================
# INICIALIZACIÓN
# ============================================================

if "reinicio_count" not in st.session_state:
    st.session_state["reinicio_count"] = 0

if "fotos_ocultas" not in st.session_state:
    st.session_state["fotos_ocultas"] = set()

RC = st.session_state["reinicio_count"]

st.title("📄 Generador de Informes de Pedidos y Traslados")


# ============================================================
# FUNCIONES GENERALES
# ============================================================

def convertir_a_base64(bytes_imagen, max_ancho=800):
    try:
        img = Image.open(BytesIO(bytes_imagen))
        img = ImageOps.exif_transpose(img)

        if img.width > max_ancho:
            ratio = max_ancho / img.width
            img = img.resize(
                (max_ancho, int(img.height * ratio))
            )

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)

        return (
            "data:image/jpeg;base64,"
            + base64.b64encode(buffer.getvalue()).decode("utf-8")
        )

    except Exception:
        return None


@st.dialog("🔍 Vista ampliada", width="large")
def mostrar_zoom(nombre_foto, bytes_foto):
    b64 = convertir_a_base64(
        bytes_foto,
        max_ancho=1600
    )

    if b64:
        st.markdown(
            f'<div style="text-align:center;">'
            f'<img src="{b64}" '
            f'style="max-width:100%; max-height:70vh; '
            f'border:1px solid #ddd; border-radius:8px;">'
            f'</div>',
            unsafe_allow_html=True
        )

        st.caption(f"📸 {nombre_foto}")

    if st.button(
        "❌ Cerrar",
        width="stretch",
        key="close_modal"
    ):
        st.rerun()


def renderizar_galeria(key, fotos, pedido_id, cols_num=4):

    fotos = [
        f for f in fotos
        if f not in st.session_state["fotos_ocultas"]
    ]

    if not fotos:
        return

    cols = st.columns(cols_num)

    for i, f in enumerate(fotos):

        with cols[i % cols_num]:

            img_placeholder = st.empty()
            bytes_img = None

            try:
                bytes_img = nube.descargar_foto_nube(
                    pedido_id,
                    f
                )

                b64 = convertir_a_base64(
                    bytes_img,
                    max_ancho=400
                )

                if b64:
                    img_placeholder.markdown(
                        f'<img src="{b64}" '
                        f'style="width:100%; border:1px solid #ddd; '
                        f'border-radius:6px; margin-bottom:6px;">',
                        unsafe_allow_html=True
                    )

            except Exception:
                img_placeholder.warning("⚠️ Error al cargar")

            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    "🔍 Ver",
                    key=f"{key}_zoom_{i}_{RC}_{f}",
                    width="stretch"
                ):
                    if bytes_img:
                        mostrar_zoom(f, bytes_img)

            with col2:
                if st.button(
                    "🗑️ Borrar",
                    key=f"{key}_del_{i}_{RC}_{f}",
                    width="stretch"
                ):
                    with st.spinner("Borrando..."):
                        nube.borrar_foto_nube(
                            pedido_id,
                            f
                        )

                        st.session_state["fotos_ocultas"].add(f)
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()

            opciones = [
                "Mantener aquí",
                "Mover a Documentación",
                "Mover a Camión",
                "Mover a Termógrafo",
                "Mover a Sello",
                "Mover a Thermo-king"
            ]

            opciones_filtradas = [
                op for op in opciones
                if op != f"Mover a {key.capitalize()}"
            ]

            destino = st.selectbox(
                "Mover foto a:",
                opciones_filtradas,
                key=f"derivar_{key}_{i}_{RC}_{f}",
                label_visibility="collapsed"
            )

            if destino != "Mantener aquí":

                if st.button(
                    "➡️ Confirmar",
                    key=f"btn_mover_{key}_{i}_{RC}_{f}",
                    width="stretch"
                ):

                    prefijo = {
                        "Mover a Documentación": "documentacion_",
                        "Mover a Camión": "camion_",
                        "Mover a Termógrafo": "termografo_",
                        "Mover a Sello": "sello_",
                        "Mover a Thermo-king": "thermoking_"
                    }[destino]

                    nuevo_nombre = (
                        f"{prefijo}{uuid.uuid4().hex[:6]}.jpg"
                    )

                    bytes_foto = nube.descargar_foto_nube(
                        pedido_id,
                        f
                    )

                    nube.subir_foto_nube(
                        pedido_id,
                        nuevo_nombre,
                        bytes_foto
                    )

                    nube.borrar_foto_nube(
                        pedido_id,
                        f
                    )

                    st.session_state["fotos_ocultas"].add(f)
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()


def val(key, default=""):

    ultimo_cargado = st.session_state.get(
        "cargar_ultimo",
        {}
    )

    v = ultimo_cargado.get(key, default)

    return default if v == "-" or v is None else v


# ============================================================
# BASE DE DATOS DE TRANSPORTES
# ============================================================

def obtener_transportes_registrados():

    transportes = {}

    try:
        pedidos = nube.obtener_pedidos_nube()

        for pedido in pedidos:

            nombre = str(
                pedido.get("transporte", "")
            ).strip()

            if not nombre:
                continue

            if nombre.lower() in (
                "-",
                "no asignado",
                "ninguno",
                "n/a"
            ):
                continue

            clave = nombre.casefold()

            if clave not in transportes:
                transportes[clave] = nombre

    except Exception as e:
        st.warning(
            f"No se pudo consultar el registro de transportes: {e}"
        )

    return sorted(
        transportes.values(),
        key=lambda x: x.casefold()
    )


def campo_transporte(
    prefijo,
    valor_actual="",
    disabled=False
):

    transportes = obtener_transportes_registrados()

    valor_actual = str(
        valor_actual or ""
    ).strip()

    if (
        valor_actual
        and valor_actual.lower() not in (
            "-",
            "no asignado"
        )
        and valor_actual.casefold() not in [
            x.casefold() for x in transportes
        ]
    ):
        transportes.append(valor_actual)

    transportes = sorted(
        transportes,
        key=lambda x: x.casefold()
    )

    opciones = [""] + transportes

    indice = 0

    for i, opcion in enumerate(opciones):
        if (
            opcion
            and opcion.casefold() == valor_actual.casefold()
        ):
            indice = i
            break

    st.caption(
        "Selecciona un transporte registrado o ingresa uno nuevo."
    )

    seleccionado = st.selectbox(
        "Transportes registrados",
        options=opciones,
        index=indice,
        format_func=lambda x: (
            "Seleccionar transporte..."
            if x == ""
            else x
        ),
        key=f"{prefijo}_transporte_existente",
        disabled=disabled
    )

    nuevo = st.text_input(
        "Agregar transporte nuevo",
        value="",
        placeholder="Escribe el nombre del transporte",
        key=f"{prefijo}_transporte_nuevo",
        disabled=disabled
    )

    if nuevo.strip():
        return nuevo.strip()

    if seleccionado.strip():
        return seleccionado.strip()

    return valor_actual


# ============================================================
# ELIMINAR FOTOS DE ESTIBAS
# ============================================================

def borrar_fotos_seleccionadas(
    pedido_id,
    df,
    seleccion
):

    if not seleccion:
        return 0

    nombres_a_borrar = [
        df.iloc[idx]["Archivo"]
        for idx in seleccion
    ]

    pedido_data = next(
        (
            p for p in nube.obtener_pedidos_nube()
            if p["id"] == pedido_id
        ),
        {}
    )

    cajas_nube = pedido_data.get(
        "cajas_estibas",
        {}
    )

    patas_nube = pedido_data.get(
        "patas_estibas",
        {}
    )

    for f in nombres_a_borrar:

        nube.borrar_foto_nube(
            pedido_id,
            f
        )

        st.session_state["fotos_ocultas"].add(f)

        if f in cajas_nube:
            del cajas_nube[f]

        if f in patas_nube:
            del patas_nube[f]

    pedido_data["cajas_estibas"] = cajas_nube
    pedido_data["patas_estibas"] = patas_nube

    nube.subir_pedido_nube(
        pedido_id,
        pedido_data
    )

    st.cache_data.clear()

    key_multiselect = f"sel_borrar_estibas_{pedido_id}"

    if key_multiselect in st.session_state:
        del st.session_state[key_multiselect]

    return len(nombres_a_borrar)


def borrar_todas_las_estibas(
    pedido_id,
    fotos_estibas
):

    pedido_data = next(
        (
            p for p in nube.obtener_pedidos_nube()
            if p["id"] == pedido_id
        ),
        {}
    )

    for f in fotos_estibas:

        nube.borrar_foto_nube(
            pedido_id,
            f
        )

        st.session_state["fotos_ocultas"].add(f)

    pedido_data["cajas_estibas"] = {}
    pedido_data["patas_estibas"] = {}

    nube.subir_pedido_nube(
        pedido_id,
        pedido_data
    )

    st.cache_data.clear()

    for key in list(st.session_state.keys()):

        if (
            key.startswith("sel_borrar_estibas_")
            or key.startswith("editor_estibas_")
        ):
            del st.session_state[key]

    return len(fotos_estibas)


# ============================================================
# GENERAR PDF
# ============================================================

def _generar_pdf_pedido(pedido_id):

    from pathlib import Path

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
            "No se encontró el pedido en la nube."
        )

    nombres_fotos = list(
        nube.obtener_fotos_nube(pedido_id) or []
    )

    prefijos = {
        "documentacion": "documentacion_",
        "camion": "camion_",
        "termografo": "termografo_",
        "sello": "sello_",
        "thermoking": "thermoking_",
        "etiqueta": "etiqueta_",
        "estibas": "estiba_pata_",
    }

    cajas_nube = pedido_data.get(
        "cajas_estibas",
        {}
    ) or {}

    patas_nube = pedido_data.get(
        "patas_estibas",
        {}
    ) or {}

    nro_termografo = str(
        pedido_data.get("nro_termografo") or ""
    ).strip()

    def obtener_numero_pata(nombre):

        valor = patas_nube.get(nombre)

        if valor not in (None, "", 0, "0"):
            try:
                return int(valor)
            except (TypeError, ValueError):
                pass

        partes = nombre.split("_")

        try:
            return int(partes[2])
        except (IndexError, TypeError, ValueError):
            return 999999

    etiquetas_categoria = {
        "camion": "Camión",
        "sello": "Sello",
        "thermoking": "Thermo-King",
        "etiqueta": "Etiqueta",
        "documentacion": "Documentación",
    }

    def descargar_categoria(prefijo, categoria):

        resultado = []

        nombres_categoria = [
            n for n in nombres_fotos
            if n.startswith(prefijo)
        ]

        if categoria == "estibas":
            nombres_categoria.sort(
                key=obtener_numero_pata
            )

        for nombre in nombres_categoria:

            try:
                contenido = nube.descargar_foto_nube(
                    pedido_id,
                    nombre
                )

            except Exception as exc:
                logging.warning(
                    "No se pudo descargar la foto %s: %s",
                    nombre,
                    exc
                )
                continue

            indice = len(resultado) + 1

            if categoria == "estibas":

                pata = obtener_numero_pata(nombre)

                if pata == 999999:
                    pata = indice

                pie = f"Estiba · Pata {pata}"

            elif categoria == "termografo":

                if nro_termografo and nro_termografo != "-":
                    pie = (
                        f"Termógrafo N° {nro_termografo} "
                        f"· Foto {indice}"
                    )
                else:
                    pie = f"Termógrafo · Foto {indice}"

            else:

                pie = (
                    f"{etiquetas_categoria.get(categoria, categoria.title())} "
                    f"· Foto {indice}"
                )

            resultado.append({
                "archivo": contenido,
                "pie": pie
            })

        return resultado

    fotos_por_categoria = {
        "estibas": descargar_categoria(
            prefijos["estibas"],
            "estibas"
        ),
        "camion": descargar_categoria(
            prefijos["camion"],
            "camion"
        ),
        "termografo": descargar_categoria(
            prefijos["termografo"],
            "termografo"
        ),
        "sello": descargar_categoria(
            prefijos["sello"],
            "sello"
        ),
        "thermoking": descargar_categoria(
            prefijos["thermoking"],
            "thermoking"
        ),
        "etiqueta": descargar_categoria(
            prefijos["etiqueta"],
            "etiqueta"
        ),
        "documentacion": descargar_categoria(
            prefijos["documentacion"],
            "documentacion"
        ),
    }

    filas_estibas = []

    nombres_estibas = [
        n for n in nombres_fotos
        if n.startswith("estiba_pata_")
    ]

    nombres_estibas.sort(
        key=obtener_numero_pata
    )

    for nombre in nombres_estibas:

        try:
            cantidad = int(
                cajas_nube.get(nombre, 0) or 0
            )
        except (TypeError, ValueError):
            cantidad = 0

        pata = obtener_numero_pata(nombre)

        filas_estibas.append({
            "pata": (
                pata
                if pata != 999999
                else len(filas_estibas) + 1
            ),
            "cantidad": cantidad
        })

    datos = {
        "pedido_id": pedido_id,
        "empresa": pedido_data.get(
            "empresa",
            "Australis Mar SA"
        ),
        "tipo_informe": pedido_data.get(
            "tipo",
            "Pedido de venta"
        ),
        "nro_pedido": pedido_data.get(
            "nro_pedido",
            ""
        ),
        "nro_entrega": pedido_data.get(
            "nro_entrega",
            "-"
        ),
        "fecha": (
            pedido_data.get("fecha")
            or pedido_data.get("fecha_creacion", "")
        ),
        "origen": pedido_data.get(
            "origen",
            "Planta Dumestre"
        ),
        "cliente": pedido_data.get(
            "cliente",
            ""
        ),
        "guia_despacho": pedido_data.get(
            "guia_despacho",
            "-"
        ),
        "transporte": pedido_data.get(
            "transporte",
            "-"
        ),
        "chofer": pedido_data.get(
            "chofer",
            "-"
        ),
        "patente_camion": pedido_data.get(
            "patente_camion",
            "-"
        ),
        "patente_rampla": pedido_data.get(
            "patente_rampla",
            "-"
        ),
        "sello_final": pedido_data.get(
            "sello_final",
            "-"
        ),
        "sellos_provisorios": pedido_data.get(
            "sellos_provisorios",
            "-"
        ),
        "nro_termografo": nro_termografo or "-"
    }

    ruta_pdf = generar_informe(
        datos,
        fotos_por_categoria,
        filas_estibas
    )

    ruta_pdf = Path(ruta_pdf)

    if not ruta_pdf.exists():
        raise RuntimeError(
            f"El generador no creó el archivo PDF: {ruta_pdf}"
        )

    pdf_bytes = ruta_pdf.read_bytes()

    if not pdf_bytes:
        raise RuntimeError(
            "El PDF generado está vacío."
        )

    return pdf_bytes, ruta_pdf.name


# ============================================================
# GESTIÓN DE PEDIDOS
# ============================================================

def mostrar_gestion_pedidos():

    st.subheader("📋 Gestión de Pedidos")

    tipo_pedido = st.radio(
        "Selecciona el tipo:",
        ["Pedido de venta", "Traslado"],
        horizontal=True
    )

    st.divider()

    with st.form("crear_pedido"):

        col1, col2 = st.columns(2)

        if tipo_pedido == "Traslado":

            with col1:
                nuevo_nro = st.text_input(
                    "N° de Entrega *"
                )

                nuevo_destino = st.text_input(
                    "Destino *"
                )

            with col2:
                nuevo_transporte = campo_transporte(
                    prefijo="crear_pedido",
                    valor_actual=""
                )

        else:

            with col1:
                nuevo_nro = st.text_input(
                    "N° Pedido *"
                )

                nuevo_cliente = st.text_input(
                    "Cliente *"
                )

            with col2:
                nuevo_transporte = campo_transporte(
                    prefijo="crear_pedido",
                    valor_actual=""
                )

                nuevo_nro_entrega = st.text_input(
                    "N° de Entrega (Opcional)"
                )

        crear = st.form_submit_button(
            "➕ Crear Pedido",
            type="primary"
        )

        if crear and nuevo_nro:

            pedido_id = str(uuid.uuid4())

            codigo_pedido = (
                f"{nuevo_nro}_{uuid.uuid4().hex[:4]}"
            )

            if tipo_pedido == "Traslado":

                datos = {
                    "id": pedido_id,
                    "codigo_pedido": codigo_pedido,
                    "nro_pedido": nuevo_nro,
                    "nro_entrega": nuevo_nro,
                    "cliente": nuevo_destino,
                    "tipo": tipo_pedido,
                    "transporte": nuevo_transporte or "No asignado",
                    "estado": "Pendiente de fotos",
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "guia_despacho": "-",
                    "chofer": "-",
                    "patente_camion": "-",
                    "patente_rampla": "-",
                    "sello_final": "-",
                    "sellos_provisorios": "-",
                    "nro_termografo": "-"
                }

            else:

                datos = {
                    "id": pedido_id,
                    "codigo_pedido": codigo_pedido,
                    "nro_pedido": nuevo_nro,
                    "nro_entrega": nuevo_nro_entrega or "-",
                    "cliente": nuevo_cliente,
                    "tipo": tipo_pedido,
                    "transporte": nuevo_transporte or "No asignado",
                    "estado": "Pendiente de fotos",
                    "fecha": datetime.now().strftime("%Y-%m-%d"),
                    "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "guia_despacho": "-",
                    "chofer": "-",
                    "patente_camion": "-",
                    "patente_rampla": "-",
                    "sello_final": "-",
                    "sellos_provisorios": "-",
                    "nro_termografo": "-"
                }

            nube.subir_pedido_nube(
                pedido_id,
                datos
            )

            st.success("✅ Pedido creado.")
            st.rerun()


# ============================================================
# SELECCIÓN DE MODO
# ============================================================

if st.session_state.get(
    "forzar_modo_informe",
    False
):

    st.session_state["selector_modo"] = "📄 Generar Informe"
    st.session_state["forzar_modo_informe"] = False
    st.session_state["reinicio_count"] += 1
    st.rerun()


modo = st.radio(
    "Modo:",
    [
        "📄 Generar Informe",
        "📋 Gestión de Pedidos"
    ],
    horizontal=True,
    key="selector_modo"
)

if modo == "📋 Gestión de Pedidos":
    mostrar_gestion_pedidos()
    st.stop()


# ============================================================
# CARGA DEL PEDIDO ACTUAL
# ============================================================

pedido_actual = st.session_state.get(
    "pedido_actual_id",
    ""
)

bloqueado = False

pedidos_nube = nube.obtener_pedidos_nube()

if pedido_actual:

    for p in pedidos_nube:

        if p["id"] == pedido_actual:

            bloqueado = (
                p.get("estado") == "Finalizado"
            )

            st.session_state["cargar_ultimo"] = p


# ============================================================
# BARRA LATERAL
# ============================================================

with st.sidebar:

    st.markdown("### 🧭 Navegación Rápida")

    if not pedidos_nube:

        st.info("No hay pedidos creados.")

    else:

        pendientes = [
            p for p in pedidos_nube
            if p.get("estado") != "Finalizado"
        ]

        finalizados = [
            p for p in pedidos_nube
            if p.get("estado") == "Finalizado"
        ]

        def boton_pedido(p, icono):

            label = (
                f"{icono} {p['nro_pedido']} "
                f"- {p['cliente'][:15]}..."
            )

            if p["id"] == pedido_actual:

                st.button(
                    label,
                    key=f"nav_{p['id']}",
                    type="primary",
                    width="stretch",
                    disabled=True
                )

            else:

                if st.button(
                    label,
                    key=f"nav_{p['id']}",
                    width="stretch"
                ):

                    st.session_state["cargar_ultimo"] = p
                    st.session_state["pedido_actual_id"] = p["id"]
                    st.session_state["reinicio_count"] += 1
                    st.session_state["fotos_ocultas"] = set()
                    st.rerun()

        if pendientes:

            st.markdown("**🟡 Pendientes**")

            for p in pendientes:
                boton_pedido(p, "📦")

        if finalizados:

            st.divider()
            st.markdown("**🟢 Finalizados**")

            # Clasificar pedidos finalizados por semana ISO y año.
            # Se utiliza primero la fecha del pedido y, si no existe,
            # la fecha de creación como respaldo.
            def clave_semana_pedido(p):
                valor_fecha = p.get("fecha") or p.get("fecha_creacion")

                try:
                    if isinstance(valor_fecha, datetime):
                        fecha_pedido = valor_fecha.date()
                    elif isinstance(valor_fecha, date):
                        fecha_pedido = valor_fecha
                    else:
                        fecha_pedido = date.fromisoformat(
                            str(valor_fecha).strip()[:10]
                        )

                    iso = fecha_pedido.isocalendar()
                    return (iso.year, iso.week)
                except (TypeError, ValueError):
                    return None

            pedidos_por_semana = {}
            for pedido_finalizado in finalizados:
                clave = clave_semana_pedido(pedido_finalizado)
                pedidos_por_semana.setdefault(clave, []).append(
                    pedido_finalizado
                )

            semanas_ordenadas = sorted(
                [k for k in pedidos_por_semana if k is not None],
                reverse=True
            )

            opciones_semana = ["Todas las semanas"]
            claves_por_opcion = {"Todas las semanas": "todas"}

            for anio_semana, numero_semana in semanas_ordenadas:
                etiqueta = (
                    f"Semana {numero_semana:02d} - {anio_semana} "
                    f"({len(pedidos_por_semana[(anio_semana, numero_semana)])})"
                )
                opciones_semana.append(etiqueta)
                claves_por_opcion[etiqueta] = (anio_semana, numero_semana)

            if None in pedidos_por_semana:
                etiqueta_sin_fecha = (
                    f"Sin fecha ({len(pedidos_por_semana[None])})"
                )
                opciones_semana.append(etiqueta_sin_fecha)
                claves_por_opcion[etiqueta_sin_fecha] = None

            semana_actual = date.today().isocalendar()
            clave_actual = (semana_actual.year, semana_actual.week)
            indice_inicial = 0

            for indice, opcion in enumerate(opciones_semana):
                if claves_por_opcion[opcion] == clave_actual:
                    indice_inicial = indice
                    break
            else:
                if len(opciones_semana) > 1:
                    indice_inicial = 1

            filtro_semana = st.selectbox(
                "📅 Filtrar por semana",
                opciones_semana,
                index=indice_inicial,
                key="filtro_semana_pedidos_finalizados"
            )

            clave_seleccionada = claves_por_opcion[filtro_semana]

            if clave_seleccionada == "todas":
                finalizados_filtrados = finalizados
            else:
                finalizados_filtrados = pedidos_por_semana.get(
                    clave_seleccionada, []
                )

            if finalizados_filtrados:
                for p in finalizados_filtrados:
                    boton_pedido(p, "🔒")
            else:
                st.caption("No hay pedidos finalizados para esta semana.")

    st.divider()

    if pedido_actual:

        st.markdown("### ⚠️ Zona de Peligro")

        with st.expander("🗑️ Eliminar Pedido Actual"):

            st.warning(
                f"¿Estás seguro de que deseas eliminar el pedido "
                f"**{st.session_state['cargar_ultimo'].get('nro_pedido', '')}**?"
            )

            st.write(
                "Esta acción borrará el pedido y **TODAS** "
                "sus fotos de la nube. No se puede deshacer."
            )

            if st.button(
                "Sí, eliminar pedido definitivamente",
                type="primary",
                width="stretch"
            ):

                with st.spinner(
                    "Eliminando pedido y fotos..."
                ):

                    nube.borrar_pedido_nube_admin(
                        pedido_actual
                    )

                    st.session_state["pedido_actual_id"] = ""
                    st.session_state["cargar_ultimo"] = {}
                    st.session_state["reinicio_count"] += 1

                    st.success(
                        "✅ Pedido eliminado correctamente."
                    )

                    time.sleep(1.5)
                    st.rerun()

    st.divider()

    if st.button(
        "🧹 Reiniciar app",
        width="stretch"
    ):
        st.session_state.clear()
        st.rerun()


# ============================================================
# DATOS GENERALES Y TRANSPORTE
# ============================================================

st.subheader("📋 Datos generales")

if bloqueado:
    st.warning("🔒 Pedido FINALIZADO.")


fecha_guardada = val(
    "fecha",
    date.today().isoformat()
)

try:

    fecha_inicial = (
        fecha_guardada
        if isinstance(fecha_guardada, date)
        else date.fromisoformat(
            str(fecha_guardada)[:10]
        )
    )

except (TypeError, ValueError):
    fecha_inicial = date.today()


with st.form("datos"):

    # --------------------------------------------------------
    # DATOS GENERALES
    # --------------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:

        empresa = st.text_input(
            "Empresa",
            value=val(
                "empresa",
                "Australis Mar SA"
            ),
            disabled=bloqueado
        )

        tipo_informe = st.selectbox(
            "Tipo",
            [
                "Pedido de venta",
                "Traslado"
            ],
            index=(
                0
                if val(
                    "tipo",
                    val("tipo_informe", "Pedido de venta")
                ) == "Pedido de venta"
                else 1
            ),
            disabled=bloqueado
        )

        nro_pedido = st.text_input(
            "N° Pedido",
            value=val("nro_pedido", ""),
            disabled=bloqueado
        )

    with c2:

        fecha = st.date_input(
            "Fecha",
            value=fecha_inicial,
            disabled=bloqueado
        )

        origen = st.text_input(
            "Origen",
            value=val(
                "origen",
                "Planta Dumestre"
            ),
            disabled=bloqueado
        )

        cliente = st.text_input(
            "Cliente",
            value=val("cliente", ""),
            disabled=bloqueado
        )

    with c3:

        nro_entrega = st.text_input(
            "N° Entrega",
            value=val("nro_entrega", ""),
            disabled=bloqueado
        )

        guia_despacho = st.text_input(
            "Guía Despacho",
            value=val("guia_despacho", ""),
            disabled=bloqueado
        )

    st.divider()

    # --------------------------------------------------------
    # TRANSPORTE
    # --------------------------------------------------------

    st.subheader("🚛 Transporte")

    transportes = obtener_transportes_registrados()

    transporte_actual = str(
        val("transporte", "")
    ).strip()

    if (
        transporte_actual
        and transporte_actual.lower() not in (
            "-",
            "no asignado",
            "ninguno",
            "n/a"
        )
        and transporte_actual.casefold() not in [
            x.casefold() for x in transportes
        ]
    ):
        transportes.append(transporte_actual)

    transportes = sorted(
        transportes,
        key=lambda x: x.casefold()
    )

    opciones_transportes = [""] + transportes

    indice_transporte = 0

    for i, opcion in enumerate(opciones_transportes):

        if (
            opcion
            and opcion.casefold() == transporte_actual.casefold()
        ):
            indice_transporte = i
            break

    # FILA 1:
    # Transporte registrado | Agregar transporte | Chofer

    t1, t2, t3 = st.columns(3)

    with t1:

        transporte_seleccionado = st.selectbox(
            "Transporte registrado",
            options=opciones_transportes,
            index=indice_transporte,
            format_func=lambda x: (
                "Seleccionar transporte..."
                if x == ""
                else x
            ),
            key=f"informe_{pedido_actual or 'nuevo'}_transporte_existente",
            disabled=bloqueado
        )

    with t2:

        transporte_nuevo = st.text_input(
            "Agregar transporte",
            value="",
            placeholder="Escribe un transporte nuevo",
            key=f"informe_{pedido_actual or 'nuevo'}_transporte_nuevo",
            disabled=bloqueado
        )

    with t3:

        chofer = st.text_input(
            "Chofer",
            value=val("chofer", ""),
            disabled=bloqueado
        )

    # El transporte nuevo tiene prioridad sobre el seleccionado.

    if transporte_nuevo.strip():
        transporte = transporte_nuevo.strip()
    elif transporte_seleccionado.strip():
        transporte = transporte_seleccionado.strip()
    else:
        transporte = transporte_actual

    # FILA 2:
    # Patente Camión | Patente Rampla

    t4, t5 = st.columns(2)

    with t4:

        patente_camion = st.text_input(
            "Patente Camión",
            value=val("patente_camion", ""),
            disabled=bloqueado
        )

    with t5:

        patente_rampla = st.text_input(
            "Patente Rampla",
            value=val("patente_rampla", ""),
            disabled=bloqueado
        )

    # FILA 3:
    # Sello Final | Sellos Provisorios

    t6, t7 = st.columns(2)

    with t6:

        sello_final = st.text_input(
            "Sello Final",
            value=val("sello_final", ""),
            disabled=bloqueado
        )

    with t7:

        sellos_provisorios = st.text_input(
            "Sellos Provisorios",
            value=val("sellos_provisorios", ""),
            disabled=bloqueado
        )

    # FILA 4:
    # Termógrafo

    nro_termografo = st.text_input(
        "N° Termógrafo",
        value=val("nro_termografo", ""),
        disabled=bloqueado
    )

    st.divider()

    # BOTÓN DE GUARDADO A ANCHO COMPLETO

    guardar_datos = st.form_submit_button(
        "💾 Guardar datos",
        type="primary",
        width="stretch",
        disabled=bloqueado
    )

    if guardar_datos:

        if not pedido_actual:

            st.error(
                "Primero debes seleccionar o crear un pedido."
            )

        else:

            with st.spinner("Guardando datos del pedido..."):

                pedidos_actualizados = nube.obtener_pedidos_nube()

                pedido_encontrado = False

                for p in pedidos_actualizados:

                    if str(p.get("id")) == str(pedido_actual):

                        p.update({
                            "empresa": empresa,
                            "tipo": tipo_informe,
                            "origen": origen,
                            "nro_pedido": nro_pedido,
                            "nro_entrega": nro_entrega,
                            "cliente": cliente,
                            "fecha": fecha.strftime("%Y-%m-%d"),
                            "guia_despacho": guia_despacho,
                            "transporte": transporte or "No asignado",
                            "chofer": chofer,
                            "patente_camion": patente_camion,
                            "patente_rampla": patente_rampla,
                            "sello_final": sello_final,
                            "sellos_provisorios": sellos_provisorios,
                            "nro_termografo": nro_termografo
                        })

                        nube.subir_pedido_nube(
                            pedido_actual,
                            p
                        )

                        pedido_encontrado = True
                        break

                if pedido_encontrado:

                    st.success(
                        "✅ Datos del pedido guardados correctamente."
                    )

                    st.rerun()

                else:

                    st.error(
                        "No se encontró el pedido seleccionado en la nube."
                    )


# ============================================================
# FOTOGRAFÍAS
# ============================================================

st.subheader("📷 Fotos")

if pedido_actual:

    fotos = nube.obtener_fotos_nube(
        pedido_actual
    )

    # --------------------------------------------------------
    # DOCUMENTACIÓN
    # --------------------------------------------------------

    with st.expander(
        "0. Documentación",
        expanded=False
    ):

        docs = [
            x for x in fotos
            if x.startswith("documentacion_")
        ]

        if docs:

            renderizar_galeria(
                "documentacion",
                docs,
                pedido_actual,
                cols_num=4
            )

        else:
            st.info("No hay documentación.")

        if not bloqueado:

            st.markdown(
                "**Subir fotos manualmente:**"
            )

            nuevas = st.file_uploader(
                "Subir documentación",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key=f"up_doc_{RC}"
            )

            if nuevas and st.button(
                "📤 Guardar documentación",
                key=f"guardar_docs_{pedido_actual}_{RC}"
            ):

                subidas_ok = 0
                errores_subida = []

                for foto_doc in nuevas:

                    try:

                        firma = hashlib.sha256(
                            foto_doc.getvalue()
                        ).hexdigest()[:16]

                        nombre = f"documentacion_{firma}.jpg"

                        existentes = nube.obtener_fotos_nube(
                            pedido_actual
                        )

                        if nombre not in existentes:

                            nube.subir_foto_nube(
                                pedido_actual,
                                nombre,
                                foto_doc.getvalue()
                            )

                            subidas_ok += 1

                    except Exception as exc:

                        errores_subida.append(
                            f"{foto_doc.name}: {exc}"
                        )

                if errores_subida:

                    st.error(
                        "Algunas fotos no se pudieron guardar:"
                    )

                    for error in errores_subida:
                        st.write(f"• {error}")

                else:

                    st.success(
                        f"Documentación guardada. "
                        f"Nuevas fotos: {subidas_ok}."
                    )

                    st.session_state["reinicio_count"] += 1
                    st.session_state["fotos_ocultas"] = set()
                    st.rerun()

    # --------------------------------------------------------
    # ESTIBAS
    # --------------------------------------------------------

    with st.expander(
        "1. Estibas",
        expanded=True
    ):

        estibas = [
            x for x in fotos
            if (
                x.startswith("estiba_pata_")
                and x not in st.session_state["fotos_ocultas"]
            )
        ]

        if not bloqueado:

            if estibas:

                with st.expander(
                    "🧨 Zona de Peligro (Limpiar todas las estibas)"
                ):

                    st.warning(
                        "Esto eliminará TODAS las fotos de estibas "
                        "de este pedido en la nube. "
                        "Úsalo solo si necesitas empezar de cero."
                    )

                    if st.button(
                        "🗑️ Borrar TODAS las fotos de estibas",
                        type="primary",
                        width="stretch"
                    ):

                        with st.spinner(
                            "Eliminando todas las fotos..."
                        ):

                            cant = borrar_todas_las_estibas(
                                pedido_actual,
                                estibas
                            )

                            st.success(
                                f"✅ Se eliminaron {cant} fotos de la nube."
                            )

                            st.session_state["reinicio_count"] += 1
                            time.sleep(1.5)
                            st.rerun()

            st.markdown(
                "### 📤 Subir y Procesar Fotos Nuevas"
            )

            st.info(
                "Sube las fotos de WhatsApp. "
                "El OCR les asignará el número de Pata "
                "y contará las cajas."
            )

            fotos_manuales = st.file_uploader(
                "Selecciona las fotos",
                type=["jpg", "png"],
                accept_multiple_files=True,
                key=f"up_estiba_{RC}"
            )

            if fotos_manuales:

                if st.button(
                    "🚀 Analizar y Guardar Fotos",
                    type="primary",
                    width="stretch"
                ):

                    progreso = st.progress(0)
                    texto_progreso = st.empty()

                    from ocr_bridge import analizar_fotos

                    total_fotos = len(fotos_manuales)
                    patas_guardadas = 0
                    errores = []
                    omitidas = 0

                    pedido_data = next(
                        (
                            p for p in nube.obtener_pedidos_nube()
                            if p["id"] == pedido_actual
                        ),
                        {}
                    )

                    if "cajas_estibas" not in pedido_data:
                        pedido_data["cajas_estibas"] = {}

                    if "patas_estibas" not in pedido_data:
                        pedido_data["patas_estibas"] = {}

                    for idx, foto in enumerate(fotos_manuales):

                        texto_progreso.info(
                            f"⏳ Procesando foto {idx + 1} "
                            f"de {total_fotos}: {foto.name}"
                        )

                        resultados = analizar_fotos([
                            (foto.name, foto.getvalue())
                        ])

                        for r in resultados:

                            pata_detectada = r.get("pata")
                            cajas_detectadas = r.get(
                                "total_cajas",
                                0
                            )

                            contenido_foto = foto.getvalue()

                            firma_foto = hashlib.sha256(
                                contenido_foto
                            ).hexdigest()[:16]

                            if (
                                pata_detectada
                                and pata_detectada != 99
                            ):

                                nuevo_nombre = (
                                    f"estiba_pata_{int(pata_detectada)}_"
                                    f"{firma_foto}.jpg"
                                )

                                if nuevo_nombre in fotos:
                                    omitidas += 1

                                nube.subir_foto_nube(
                                    pedido_actual,
                                    nuevo_nombre,
                                    contenido_foto
                                )

                                pedido_data["cajas_estibas"][nuevo_nombre] = (
                                    cajas_detectadas
                                )

                                pedido_data["patas_estibas"][nuevo_nombre] = (
                                    pata_detectada
                                )

                                patas_guardadas += 1

                            else:

                                nuevo_nombre = (
                                    f"estiba_pata_99_REVISAR_"
                                    f"{firma_foto}.jpg"
                                )

                                nube.subir_foto_nube(
                                    pedido_actual,
                                    nuevo_nombre,
                                    contenido_foto
                                )

                                pedido_data["cajas_estibas"][nuevo_nombre] = (
                                    cajas_detectadas
                                )

                                pedido_data["patas_estibas"][nuevo_nombre] = 99

                                errores.append(foto.name)

                        progreso.progress(
                            (idx + 1) / total_fotos
                        )

                    nube.subir_pedido_nube(
                        pedido_actual,
                        pedido_data
                    )

                    texto_progreso.empty()
                    progreso.empty()

                    if errores:

                        st.warning(
                            f"⚠️ Se procesaron {patas_guardadas} fotos. "
                            f"Fotos sin pata: {', '.join(errores)}"
                        )

                    else:

                        st.success(
                            f"✅ Se procesaron y guardaron "
                            f"{patas_guardadas} fotos correctamente."
                        )

                    st.session_state["reinicio_count"] += 1
                    time.sleep(2)
                    st.rerun()

        st.divider()

        if estibas:

            st.markdown(
                "### 📋 Resumen de Patas y Cajas"
            )

            # PROCESAR FOTOS QUE VIENEN DEL CELULAR CON PATA 99

            if not bloqueado:

                fotos_99 = [
                    f for f in estibas
                    if (
                        len(f.split("_")) > 2
                        and f.split("_")[2] == "99"
                    )
                ]

                if fotos_99:

                    st.warning(
                        f"⚠️ Hay {len(fotos_99)} fotos subidas "
                        "desde el celular que no tienen pata asignada "
                        "(Pata 99)."
                    )

                    if st.button(
                        "🔍 Procesar OCR a fotos pendientes (Pata 99)",
                        type="primary",
                        width="stretch"
                    ):

                        with st.spinner(
                            "El OCR está analizando las fotos nuevas..."
                        ):

                            from ocr_bridge import analizar_fotos

                            pedido_data = next(
                                (
                                    p for p in nube.obtener_pedidos_nube()
                                    if p["id"] == pedido_actual
                                ),
                                {}
                            )

                            if "cajas_estibas" not in pedido_data:
                                pedido_data["cajas_estibas"] = {}

                            if "patas_estibas" not in pedido_data:
                                pedido_data["patas_estibas"] = {}

                            for f in fotos_99:

                                bytes_foto = nube.descargar_foto_nube(
                                    pedido_actual,
                                    f
                                )

                                resultados = analizar_fotos([
                                    (f, bytes_foto)
                                ])

                                for r in resultados:

                                    pata_detectada = r.get("pata")
                                    cajas_detectadas = r.get(
                                        "total_cajas",
                                        0
                                    )

                                    if (
                                        pata_detectada
                                        and pata_detectada != 99
                                    ):

                                        firma_foto = hashlib.sha256(
                                            bytes_foto
                                        ).hexdigest()[:16]

                                        nuevo_nombre = (
                                            f"estiba_pata_{int(pata_detectada)}_"
                                            f"{firma_foto}.jpg"
                                        )

                                        nube.subir_foto_nube(
                                            pedido_actual,
                                            nuevo_nombre,
                                            bytes_foto
                                        )

                                        nube.borrar_foto_nube(
                                            pedido_actual,
                                            f
                                        )

                                        pedido_data["cajas_estibas"][nuevo_nombre] = (
                                            cajas_detectadas
                                        )

                                        pedido_data["patas_estibas"][nuevo_nombre] = (
                                            pata_detectada
                                        )

                                        if f in pedido_data["cajas_estibas"]:
                                            del pedido_data["cajas_estibas"][f]

                                        if f in pedido_data["patas_estibas"]:
                                            del pedido_data["patas_estibas"][f]

                            nube.subir_pedido_nube(
                                pedido_actual,
                                pedido_data
                            )

                            st.success(
                                "✅ Fotos procesadas y patas asignadas correctamente."
                            )

                            st.session_state["reinicio_count"] += 1
                            time.sleep(1.5)
                            st.rerun()

            # CONSTRUCCIÓN DE LA TABLA DE ESTIBAS

            pedido_data = next(
                (
                    p for p in nube.obtener_pedidos_nube()
                    if p["id"] == pedido_actual
                ),
                {}
            )

            cajas_nube = pedido_data.get(
                "cajas_estibas",
                {}
            )

            patas_nube = pedido_data.get(
                "patas_estibas",
                {}
            )

            datos_tabla = []

            for f in estibas:

                pata_original = (
                    f.split("_")[2]
                    .replace(".jpg", "")
                    .split("_")[0]
                )

                pata_guardada = patas_nube.get(
                    f,
                    int(pata_original)
                    if pata_original.isdigit()
                    else 0
                )

                cajas_guardadas = cajas_nube.get(
                    f,
                    0
                )

                datos_tabla.append({
                    "Archivo": f,
                    "Pata Final (Editable)": pata_guardada,
                    "Cajas": cajas_guardadas
                })

            df_editado = pd.DataFrame(datos_tabla)

            if not df_editado.empty:

                df_editado_nuevo = st.data_editor(
                    df_editado,
                    width="stretch",
                    disabled=bloqueado,
                    hide_index=True,
                    num_rows="fixed",
                    key=f"editor_estibas_{pedido_actual}",
                    column_config={
                        "Archivo": st.column_config.TextColumn(
                            "Archivo",
                            disabled=True
                        ),
                        "Pata Final (Editable)": st.column_config.NumberColumn(
                            "Pata Final"
                        ),
                        "Cajas": st.column_config.NumberColumn(
                            "Cajas"
                        )
                    }
                )

                if not bloqueado:

                    if st.button(
                        "💾 Guardar Cambios en Tabla",
                        type="primary",
                        width="stretch"
                    ):

                        with st.spinner("Guardando cambios..."):

                            nuevas_cajas = {}
                            nuevas_patas = {}

                            for index, row in df_editado_nuevo.iterrows():

                                archivo_actual = row["Archivo"]

                                nuevas_cajas[archivo_actual] = int(
                                    row["Cajas"]
                                )

                                nuevas_patas[archivo_actual] = int(
                                    row["Pata Final (Editable)"]
                                )

                            pedido_data["cajas_estibas"] = nuevas_cajas
                            pedido_data["patas_estibas"] = nuevas_patas

                            nube.subir_pedido_nube(
                                pedido_actual,
                                pedido_data
                            )

                            st.success(
                                "✅ Cambios guardados. "
                                "La App Móvil ya refleja las nuevas Patas y Cajas."
                            )

                            time.sleep(1.5)
                            st.rerun()

                    filas_seleccionadas = st.multiselect(
                        "Selecciona las fotos que deseas eliminar "
                        "(puedes elegir varias):",
                        options=range(len(df_editado_nuevo)),
                        format_func=lambda i: (
                            f"Pata {df_editado_nuevo.iloc[i]['Pata Final (Editable)']} "
                            f"- {df_editado_nuevo.iloc[i]['Archivo']}"
                        ),
                        key=f"sel_borrar_estibas_{pedido_actual}"
                    )

                    if filas_seleccionadas:

                        if st.button(
                            "🗑️ Eliminar Fotos Seleccionadas",
                            type="primary",
                            width="stretch"
                        ):

                            with st.spinner("Borrando fotos..."):

                                cant = borrar_fotos_seleccionadas(
                                    pedido_actual,
                                    df_editado_nuevo,
                                    filas_seleccionadas
                                )

                                st.success(
                                    f"✅ {cant} fotos eliminadas correctamente."
                                )

                                st.session_state["reinicio_count"] += 1
                                time.sleep(1)
                                st.rerun()

                total_patas = len(df_editado_nuevo)

                try:

                    total_cajas = int(
                        pd.to_numeric(
                            df_editado_nuevo["Cajas"],
                            errors="coerce"
                        ).fillna(0).sum()
                    )

                except Exception:
                    total_cajas = 0

                col_m1, col_m2 = st.columns(2)

                col_m1.metric(
                    label="📦 Total Patas Detectadas",
                    value=total_patas
                )

                col_m2.metric(
                    label="🧊 Total Cajas Detectadas",
                    value=total_cajas
                )

                st.divider()

                st.markdown(
                    "### ✏️ Revisión Foto por Foto"
                )

                col_tabla, col_preview = st.columns([1.5, 1])

                with col_preview:

                    archivo_sel = st.selectbox(
                        "Ver foto:",
                        df_editado_nuevo["Archivo"].tolist(),
                        key=f"sel_ocr_{RC}_{pedido_actual}"
                    )

                    if archivo_sel:

                        b = nube.descargar_foto_nube(
                            pedido_actual,
                            archivo_sel
                        )

                        b64 = convertir_a_base64(
                            b,
                            600
                        )

                        if b64:
                            st.markdown(
                                f'<img src="{b64}" '
                                f'style="width:100%; border-radius:8px;">',
                                unsafe_allow_html=True
                            )

                with col_tabla:

                    st.info(
                        "Edita la Pata y las Cajas en la tabla "
                        "y presiona 'Guardar Cambios en Tabla'."
                    )

    # --------------------------------------------------------
    # SECCIONES EXTRA DE FOTOGRAFÍAS
    # --------------------------------------------------------

    def seccion_extra(titulo, prefijo):

        with st.expander(
            titulo,
            expanded=False
        ):

            items = [
                x for x in fotos
                if x.startswith(prefijo)
            ]

            if items:

                renderizar_galeria(
                    prefijo,
                    items,
                    pedido_actual,
                    cols_num=4
                )

            else:
                st.info("No hay fotos.")

            if not bloqueado:

                st.markdown(
                    "**Subir fotos manualmente:**"
                )

                nuevas = st.file_uploader(
                    f"Subir fotos ({titulo})",
                    type=["jpg", "jpeg", "png"],
                    accept_multiple_files=True,
                    key=f"up_{prefijo}_{RC}"
                )

                if nuevas and st.button(
                    f"📤 Guardar fotos ({titulo})",
                    key=f"guardar_{prefijo}_{pedido_actual}_{RC}"
                ):

                    subidas_ok = 0
                    errores_subida = []

                    for foto_categoria in nuevas:

                        try:

                            firma = hashlib.sha256(
                                foto_categoria.getvalue()
                            ).hexdigest()[:16]

                            nombre = f"{prefijo}{firma}.jpg"

                            existentes = nube.obtener_fotos_nube(
                                pedido_actual
                            )

                            if nombre not in existentes:

                                nube.subir_foto_nube(
                                    pedido_actual,
                                    nombre,
                                    foto_categoria.getvalue()
                                )

                                subidas_ok += 1

                        except Exception as exc:

                            errores_subida.append(
                                f"{foto_categoria.name}: {exc}"
                            )

                    if errores_subida:

                        st.error(
                            "Algunas fotos no se pudieron guardar:"
                        )

                        for error in errores_subida:
                            st.write(f"• {error}")

                    else:

                        st.success(
                            f"Fotos guardadas. Nuevas: {subidas_ok}."
                        )

                        st.session_state["reinicio_count"] += 1
                        st.session_state["fotos_ocultas"] = set()
                        st.rerun()

    seccion_extra(
        "2. Camión",
        "camion_"
    )

    seccion_extra(
        "3. Termógrafo",
        "termografo_"
    )

    seccion_extra(
        "4. Sellos",
        "sello_"
    )

    seccion_extra(
        "5. Thermo-king",
        "thermoking_"
    )

    seccion_extra(
        "6. Etiquetas",
        "etiqueta_"
    )


# ============================================================
# GENERAR PDF Y FINALIZAR PEDIDO
# ============================================================

st.divider()

c1, c2 = st.columns(2)

with c1:

    if st.button(
        "🚀 Generar PDF",
        type="primary",
        width="stretch"
    ):

        if not pedido_actual:

            st.error(
                "Selecciona un pedido antes de generar el informe."
            )

        else:

            with st.spinner("Generando PDF..."):

                try:

                    pdf_bytes, nombre_pdf = _generar_pdf_pedido(
                        pedido_actual
                    )

                    st.success("✅ Informe generado.")

                    st.download_button(
                        label="📥 Descargar PDF",
                        data=pdf_bytes,
                        file_name=nombre_pdf,
                        mime="application/pdf",
                        type="primary",
                        width="stretch"
                    )

                except Exception as exc:

                    st.error(
                        f"❌ Error al generar el PDF: {exc}"
                    )


with c2:

    if pedido_actual and not bloqueado:

        if st.button(
            "✅ Finalizar Pedido",
            width="stretch"
        ):

            pedidos = nube.obtener_pedidos_nube()

            for p in pedidos:

                if p["id"] == pedido_actual:

                    p["estado"] = "Finalizado"

                    nube.subir_pedido_nube(
                        pedido_actual,
                        p
                    )

                    st.rerun()

    elif pedido_actual and bloqueado:

        if st.button(
            "🔓 Reabrir Pedido",
            type="primary",
            width="stretch"
        ):

            pedidos = nube.obtener_pedidos_nube()

            for p in pedidos:

                if p["id"] == pedido_actual:

                    p["estado"] = "Pendiente de fotos"

                    nube.subir_pedido_nube(
                        pedido_actual,
                        p
                    )

                    st.rerun()
