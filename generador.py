import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
import logging
import os
import re
from html import escape

from PIL import Image, ImageOps
from weasyprint import HTML

import config

logging.basicConfig(
    filename=config.LOGS_DIR / "informes.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


def comprimir_foto(ruta_o_bytes, tamano_max=None):
    if tamano_max is None:
        tamano_max = config.ANCHO_MAX_FOTO

    if isinstance(ruta_o_bytes, (str, Path)):
        img = Image.open(ruta_o_bytes)
    else:
        img = Image.open(BytesIO(ruta_o_bytes))

    img = ImageOps.exif_transpose(img)

    if img.width > tamano_max:
        ratio = tamano_max / img.width
        img = img.resize((tamano_max, int(img.height * ratio)))

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    buffer = BytesIO()
    img.save(
        buffer,
        format="JPEG",
        quality=config.CALIDAD_JPEG,
        optimize=True
    )
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def construir_grid_fotos(lista_fotos, tamano_foto=1200):
    """Distribuye las fotografías en páginas de hasta cuatro imágenes.

    Cada bloque es una tabla 2x2 indivisible para evitar que WeasyPrint
    deje dos fotografías en una página y las otras dos en la siguiente.
    """
    if not lista_fotos:
        return ""

    html = []
    total = len(lista_fotos)

    for inicio in range(0, total, 4):
        grupo = lista_fotos[inicio:inicio + 4]
        if inicio > 0:
            html.append('<div class="salto-pagina"></div>')

        clase_tabla = "tabla-fotos tabla-single" if len(grupo) == 1 else "tabla-fotos"
        html.append(f'<table class="{clase_tabla}"><tbody>')

        for fila_inicio in range(0, len(grupo), 2):
            html.append('<tr>')
            fila = grupo[fila_inicio:fila_inicio + 2]

            for foto in fila:
                data_uri = comprimir_foto(
                    foto["archivo"],
                    tamano_max=tamano_foto
                )
                pie = escape(str(foto.get("pie", "Fotografía")))
                clase_contenedor = "contenedor-img single" if len(grupo) == 1 else "contenedor-img"
                html.append('<td class="celda-foto"><div class="' + clase_contenedor + '"><img src="' + data_uri + '" alt="' + pie + '"></div><div class="pie-foto">' + pie + '</div></td>')

            if len(fila) == 1:
                html.append('<td class="celda-foto celda-vacia"></td>')
            html.append('</tr>')

        html.append('</tbody></table>')

    return "".join(html)

def construir_tabla_estibas(filas):
    """Construye el resumen de patas con encabezados centrados y total destacado."""
    if not filas:
        return ""

    html = [
        '<table class="tabla-estibas">',
        '<thead><tr>',
        '<th class="col-numero">N°</th>',
        '<th class="col-pata">PATA</th>',
        '<th class="col-cantidad">CANTIDAD</th>',
        '</tr></thead><tbody>'
    ]

    total = 0
    for indice, fila in enumerate(filas, start=1):
        cantidad = fila.get("cantidad", "")
        pata = fila.get("pata", indice)

        try:
            total += int(cantidad)
        except (TypeError, ValueError):
            pass

        try:
            pata_texto = str(int(pata)) if pata not in (None, "") else str(indice)
        except (TypeError, ValueError):
            pata_texto = str(pata) if pata else str(indice)

        cantidad_texto = escape(str(cantidad if cantidad not in (None, "") else 0))
        html.append(
            '<tr>'
            f'<td>{indice}</td>'
            f'<td>PATA {escape(pata_texto)}</td>'
            f'<td>{cantidad_texto}</td>'
            '</tr>'
        )

    html.append(
        '<tr class="fila-total">'
        '<td colspan="2">TOTAL CAJAS</td>'
        f'<td>{total}</td>'
        '</tr>'
    )
    html.append('</tbody></table>')
    return "".join(html)

def construir_seccion(titulo, contenido, salto_inicial=False):
    salto = (
        '<div class="salto-pagina"></div>'
        if salto_inicial
        else ""
    )

    return f'''
    {salto}
    <div class="titulo-categoria">{titulo}</div>
    {contenido}
    '''


def generar_informe(datos, fotos_por_categoria, filas_estibas=None):
    plantilla = (
        config.BASE_DIR / "plantilla.html"
    ).read_text(encoding="utf-8")

    # Logos
    logo_izq_html_grande = ""
    logo_izq_html = ""

    if config.LOGO_PATH.exists():
        logo_uri = comprimir_foto(config.LOGO_PATH)
        logo_izq_html_grande = f'<img src="{logo_uri}">'
        logo_izq_html = f'<img src="{logo_uri}">'

    logo_der_html_grande = ""
    logo_der_html = ""

    if config.LOGO2_PATH.exists():
        logo2_uri = comprimir_foto(config.LOGO2_PATH)
        logo_der_html_grande = f'<img src="{logo2_uri}">'
        logo_der_html = f'<img src="{logo2_uri}">'

    fecha_gen = datetime.now().strftime("%d/%m/%Y %H:%M")

    tipo = str(datos.get("tipo_informe", "")).strip().lower()

    if "traslado" in tipo:
        titulo_informe = "REPORTE FOTOGRAFICO CONGELADO"
    else:
        titulo_informe = "REPORTE FOTOGRAFICO FRESCO"

    secciones = []

    # 1. Estibas
    fotos_estibas = fotos_por_categoria.get("estibas", [])
    tabla_estibas = filas_estibas or []

    if fotos_estibas or tabla_estibas:
        contenido = construir_tabla_estibas(tabla_estibas)
        if fotos_estibas and tabla_estibas:
            # La tabla resumen ocupa su propio espacio; las fotos comienzan
            # en una página limpia para mantener cuatro imágenes por página.
            contenido += '<div class="salto-pagina"></div>'
        contenido += construir_grid_fotos(
            fotos_estibas,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion("1. Fotos Estibas", contenido)
        )

    # 2. Camión
    fotos_camion = fotos_por_categoria.get("camion", [])

    if fotos_camion:
        contenido = construir_grid_fotos(
            fotos_camion,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion(
                "2. Fotos Camión",
                contenido,
                salto_inicial=len(secciones) > 0
            )
        )

    # 3. Termógrafo
    fotos_termografo = fotos_por_categoria.get("termografo", [])

    if fotos_termografo:
        contenido = construir_grid_fotos(
            fotos_termografo,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion(
                "3. Termógrafo",
                contenido,
                salto_inicial=len(secciones) > 0
            )
        )

    # 4. Sello
    fotos_sello = fotos_por_categoria.get("sello", [])

    if fotos_sello:
        contenido = construir_grid_fotos(
            fotos_sello,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion(
                "4. Sello/s final/es o provisorio/s",
                contenido,
                salto_inicial=len(secciones) > 0
            )
        )

    # 5. Thermo-king
    fotos_thermoking = fotos_por_categoria.get("thermoking", [])

    if fotos_thermoking:
        contenido = construir_grid_fotos(
            fotos_thermoking,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion(
                "5. Thermo-king",
                contenido,
                salto_inicial=len(secciones) > 0
            )
        )

    # 6. Etiqueta
    fotos_etiqueta = fotos_por_categoria.get("etiqueta", [])

    if fotos_etiqueta:
        contenido = construir_grid_fotos(
            fotos_etiqueta,
            tamano_foto=1200
        )
        secciones.append(
            construir_seccion(
                "6. Etiqueta",
                contenido,
                salto_inicial=len(secciones) > 0
            )
        )

    # Número para el encabezado
    nro_pedido_val = str(datos.get("nro_pedido") or "").strip()
    nro_entrega_val = str(datos.get("nro_entrega") or "").strip()

    if nro_pedido_val and nro_pedido_val != "-":
        nro_doc_html = (
            f'<div class="nro-doc">N° {nro_pedido_val}</div>'
        )
    elif nro_entrega_val and nro_entrega_val != "-":
        nro_doc_html = (
            f'<div class="nro-doc">N° {nro_entrega_val}</div>'
        )
    else:
        nro_doc_html = ""

    if nro_pedido_val and nro_pedido_val != "-":
        nro_pedido_display = nro_pedido_val
    else:
        nro_pedido_display = "—"

    if nro_pedido_val and nro_pedido_val != "-":
        pie_nro = nro_pedido_val
    elif nro_entrega_val and nro_entrega_val != "-":
        pie_nro = nro_entrega_val
    else:
        pie_nro = "S/N"

    reemplazos = {
        "{{logo_izq_html_grande}}": logo_izq_html_grande,
        "{{logo_der_html_grande}}": logo_der_html_grande,
        "{{empresa}}": datos.get("empresa", ""),
        "{{titulo_informe}}": titulo_informe,
        "{{nro_doc_html}}": nro_doc_html,
        "{{nro_pedido_display}}": nro_pedido_display,
        "{{tipo_informe}}": datos.get("tipo_informe", ""),
        "{{nro_pedido}}": pie_nro,
        "{{fecha}}": datos.get("fecha", ""),
        "{{nro_entrega}}": datos.get("nro_entrega", "-"),
        "{{guia_despacho}}": datos.get("guia_despacho", "-"),
        "{{cliente}}": datos.get("cliente", ""),
        "{{origen}}": datos.get("origen", ""),
        "{{transporte}}": datos.get("transporte", "-"),
        "{{chofer}}": datos.get("chofer", "-"),
        "{{patente_camion}}": datos.get("patente_camion", "-"),
        "{{patente_rampla}}": datos.get("patente_rampla", "-"),
        "{{sello_final}}": datos.get("sello_final", "-"),
        "{{sellos_provisorios}}": datos.get("sellos_provisorios", "-"),
        "{{nro_termografo}}": datos.get("nro_termografo", "-"),
        "{{secciones}}": "".join(secciones),
        "{{fecha_generacion}}": fecha_gen,
    }

    html_final = plantilla

    for clave, valor in reemplazos.items():
        html_final = html_final.replace(clave, str(valor))

    # Nombre del PDF basado en el tipo de operación, número correspondiente
    # y fecha del pedido ingresada en la aplicación.
    es_traslado = "traslado" in tipo
    if es_traslado:
        numero_documento = datos.get("nro_entrega") or datos.get("nro_pedido") or "SN"
    else:
        numero_documento = datos.get("nro_pedido") or datos.get("nro_entrega") or "SN"

    numero_documento = re.sub(r"[^A-Za-z0-9_-]+", "_", str(numero_documento).strip())
    numero_documento = numero_documento.strip("_") or "SN"

    fecha_pedido = datos.get("fecha") or datos.get("fecha_creacion") or datetime.now()
    if hasattr(fecha_pedido, "strftime"):
        fecha_archivo = fecha_pedido.strftime("%Y-%m-%d")
    else:
        fecha_texto = str(fecha_pedido).strip()
        fecha_archivo = ""
        for formato in (
            "%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S"
        ):
            try:
                fecha_archivo = datetime.strptime(fecha_texto[:19], formato).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        if not fecha_archivo:
            fecha_archivo = datetime.now().strftime("%Y-%m-%d")

    prefijo_nombre = str(getattr(config, "PREFIJO_PDF", "INFORME") or "INFORME").strip()
    nombre_pdf = f"{prefijo_nombre}_{numero_documento}_{fecha_archivo}.pdf"

    # Guardar en la carpeta del pedido cuando exista
    pedido_id = datos.get("pedido_id")

    if pedido_id and os.path.exists(f"temp/pedidos/{pedido_id}"):
        ruta_pdf = (
            Path(f"temp/pedidos/{pedido_id}") / nombre_pdf
        )
    else:
        ruta_pdf = config.SALIDA_DIR / nombre_pdf

    # Generar PDF con WeasyPrint
    ruta_pdf.parent.mkdir(parents=True, exist_ok=True)

    HTML(
        string=html_final,
        base_url=str(config.BASE_DIR)
    ).write_pdf(str(ruta_pdf))

    # Guardar en historial
    try:
        import historial

        historial.guardar_informe(datos, nombre_pdf)
        logging.info(
            f"Informe guardado en historial: {nombre_pdf}"
        )
    except Exception as e:
        logging.error(
            f"ERROR al guardar en historial: {e}"
        )

    # Guardar JSON del último informe
    try:
        import json

        with open(
            config.ULTIMO_INFORME_JSON,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                datos,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception as e:
        logging.warning(
            f"No se pudo guardar último informe: {e}"
        )

    logging.info(f"Informe generado: {ruta_pdf}")
    return ruta_pdf
