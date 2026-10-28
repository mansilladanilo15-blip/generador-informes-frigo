import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
import logging
import os

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
    img.save(buffer, format="JPEG", quality=config.CALIDAD_JPEG, optimize=True)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def construir_grid_fotos(lista_fotos, tamano_foto=1200):
    """
    Genera tabla HTML con fotos optimizando el espacio.
    """
    if not lista_fotos:
        return ""

    total = len(lista_fotos)
    html = ""

    # ===== 1 foto =====
    if total == 1:
        foto = lista_fotos[0]
        data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
        pie = foto.get("pie", "Foto 1")
        return f'''
        <table class="tabla-fotos tabla-single">
          <tr>
            <td class="celda-foto single">
              <div class="contenedor-img single">
                <img src="{data_uri}">
              </div>
              <div class="pie-foto">{pie}</div>
            </td>
          </tr>
        </table>
        '''

    # ===== 2 fotos =====
    if total == 2:
        html += '<table class="tabla-fotos"><tr>'
        for i in range(1, 3):
            foto = lista_fotos[i - 1]
            data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
            pie = foto.get("pie", f"Foto {i}")
            html += f'''
            <td class="celda-foto grande">
              <div class="contenedor-img">
                <img src="{data_uri}">
              </div>
              <div class="pie-foto">{pie}</div>
            </td>
            '''
        html += '</tr></table>'
        return html

    # ===== 3 fotos =====
    if total == 3:
        foto1 = lista_fotos[0]
        data1 = comprimir_foto(foto1["archivo"], tamano_max=tamano_foto)
        pie1 = foto1.get("pie", "Foto 1")
        html += f'''
        <table class="tabla-fotos">
          <tr>
            <td class="celda-foto ancha" colspan="2">
              <div class="contenedor-img ancha">
                <img src="{data1}">
              </div>
              <div class="pie-foto">{pie1}</div>
            </td>
          </tr>
        </table>
        '''
        html += '<table class="tabla-fotos"><tr>'
        for i in [2, 3]:
            foto = lista_fotos[i - 1]
            data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
            pie = foto.get("pie", f"Foto {i}")
            html += f'''
            <td class="celda-foto mediana">
              <div class="contenedor-img">
                <img src="{data_uri}">
              </div>
              <div class="pie-foto">{pie}</div>
            </td>
            '''
        html += '</tr></table>'
        return html

    # ===== 4 fotos: 2x2 =====
    if total == 4:
        html += '<table class="tabla-fotos">'
        for fila in range(2):
            html += '<tr>'
            for col in range(2):
                idx = fila * 2 + col + 1
                foto = lista_fotos[idx - 1]
                data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
                pie = foto.get("pie", f"Foto {idx}")
                html += f'''
                <td class="celda-foto mediana">
                  <div class="contenedor-img">
                    <img src="{data_uri}">
                  </div>
                  <div class="pie-foto">{pie}</div>
                </td>
                '''
            html += '</tr>'
        html += '</table>'
        return html

    # ===== 5+ fotos =====
    idx = 1
    primera_pagina = True

    while idx <= total:
        fotos_restantes = total - idx + 1

        if not primera_pagina:
            html += '<div class="salto-pagina"></div>'

        fotos_en_esta_hoja = min(4, fotos_restantes)
        if fotos_restantes <= 4:
            fotos_en_esta_hoja = fotos_restantes

        if fotos_en_esta_hoja == 1:
            foto = lista_fotos[idx - 1]
            data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
            pie = foto.get("pie", f"Foto {idx}")
            html += f'''
            <table class="tabla-fotos tabla-single">
              <tr>
                <td class="celda-foto single">
                  <div class="contenedor-img single">
                    <img src="{data_uri}">
                  </div>
                  <div class="pie-foto">{pie}</div>
                </td>
              </tr>
            </table>
            '''
            idx += 1

        elif fotos_en_esta_hoja == 2:
            html += '<table class="tabla-fotos"><tr>'
            for j in range(2):
                foto = lista_fotos[idx - 1]
                data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
                pie = foto.get("pie", f"Foto {idx}")
                html += f'''
                <td class="celda-foto mediana">
                  <div class="contenedor-img">
                    <img src="{data_uri}">
                  </div>
                  <div class="pie-foto">{pie}</div>
                </td>
                '''
                idx += 1
            html += '</tr></table>'

        elif fotos_en_esta_hoja == 3:
            foto1 = lista_fotos[idx - 1]
            data1 = comprimir_foto(foto1["archivo"], tamano_max=tamano_foto)
            pie1 = foto1.get("pie", f"Foto {idx}")
            html += f'''
            <table class="tabla-fotos">
              <tr>
                <td class="celda-foto mediana" colspan="2">
                  <div class="contenedor-img">
                    <img src="{data1}">
                  </div>
                  <div class="pie-foto">{pie1}</div>
                </td>
              </tr>
            </table>
            '''
            idx += 1
            html += '<table class="tabla-fotos"><tr>'
            for j in range(2):
                foto = lista_fotos[idx - 1]
                data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
                pie = foto.get("pie", f"Foto {idx}")
                html += f'''
                <td class="celda-foto mediana">
                  <div class="contenedor-img">
                    <img src="{data_uri}">
                  </div>
                  <div class="pie-foto">{pie}</div>
                </td>
                '''
                idx += 1
            html += '</tr></table>'

        else:
            html += '<table class="tabla-fotos">'
            for fila in range(2):
                html += '<tr>'
                for col in range(2):
                    foto = lista_fotos[idx - 1]
                    data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
                    pie = foto.get("pie", f"Foto {idx}")
                    html += f'''
                    <td class="celda-foto mediana">
                      <div class="contenedor-img">
                        <img src="{data_uri}">
                      </div>
                      <div class="pie-foto">{pie}</div>
                    </td>
                    '''
                    idx += 1
                html += '</tr>'
            html += '</table>'

        primera_pagina = False

    return html



from html import escape


def construir_tabla_estibas(filas):
    if not filas:
        return ""

    html = """
    <table class="tabla-estibas">
      <thead>
        <tr>
          <th class="col-numero">N°</th>
          <th class="col-producto">Producto</th>
          <th class="col-cantidad">Cantidad</th>
        </tr>
      </thead>
      <tbody>
    """

    total = 0

    # Ordenar por número de pata real, sin cambiar el dato guardado.
    filas_ordenadas = sorted(
        filas,
        key=lambda fila: int(fila.get("pata", 0) or 0)
    )

    for fila in filas_ordenadas:
        pata = int(fila.get("pata", 0) or 0)
        cantidad = int(fila.get("cantidad", 0) or 0)

        total += cantidad

        etiqueta_pata = (
            f"PATA {pata} — REVISAR"
            if pata == 99
            else f"PATA {pata}"
        )

        html += f"""
        <tr>
          <td class="numero-pata">{pata if pata else "—"}</td>
          <td>{escape(etiqueta_pata)}</td>
          <td>{cantidad}</td>
        </tr>
        """

    html += f"""
        <tr class="fila-total">
          <td colspan="2">TOTAL CAJAS:</td>
          <td>{total}</td>
        </tr>
      </tbody>
    </table>
    """

    return html



def construir_seccion(titulo, contenido, salto_inicial=False):
    salto = '<div class="salto-pagina"></div>' if salto_inicial else ""
    return f'''
    {salto}
    <div class="titulo-categoria">{titulo}</div>
    {contenido}
    '''


def generar_informe(datos, fotos_por_categoria, filas_estibas=None):
    plantilla = (config.BASE_DIR / "plantilla.html").read_text(encoding="utf-8")

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

    tipo = datos.get("tipo_informe", "").lower()
    if "traslado" in tipo:
        titulo_informe = "REPORTE FOTOGRÁFICO CONGELADO"
    else:
        titulo_informe = "REPORTE FOTOGRÁFICO FRESCO"

    secciones = []

    # 1. Estibas
    fotos_estibas = fotos_por_categoria.get("estibas", [])
    tabla_estibas = filas_estibas or []
    if fotos_estibas or tabla_estibas:
        contenido = construir_tabla_estibas(tabla_estibas)
        contenido += construir_grid_fotos(fotos_estibas, tamano_foto=1200)
        secciones.append(construir_seccion("1. Fotos Estibas", contenido))

    # 2. Camión
    fotos_camion = fotos_por_categoria.get("camion", [])
    if fotos_camion:
        contenido = construir_grid_fotos(fotos_camion, tamano_foto=1200)
        secciones.append(construir_seccion(
            "2. Fotos Camión", contenido, salto_inicial=len(secciones) > 0
        ))

    # 3. Termógrafo
    fotos_termografo = fotos_por_categoria.get("termografo", [])
    if fotos_termografo:
        contenido = construir_grid_fotos(fotos_termografo, tamano_foto=1200)
        secciones.append(construir_seccion(
            "3. Termógrafo", contenido, salto_inicial=len(secciones) > 0
        ))

    # 4. Sello
    fotos_sello = fotos_por_categoria.get("sello", [])
    if fotos_sello:
        contenido = construir_grid_fotos(fotos_sello, tamano_foto=1200)
        secciones.append(construir_seccion(
            "4. Sello/s final/es o provisorio/s", contenido,
            salto_inicial=len(secciones) > 0
        ))

    # 5. Thermo-king
    fotos_thermoking = fotos_por_categoria.get("thermoking", [])
    if fotos_thermoking:
        contenido = construir_grid_fotos(fotos_thermoking, tamano_foto=1200)
        secciones.append(construir_seccion(
            "5. Thermo-king", contenido, salto_inicial=len(secciones) > 0
        ))

    # 6. Etiqueta
    fotos_etiqueta = fotos_por_categoria.get("etiqueta", [])
    if fotos_etiqueta:
        contenido = construir_grid_fotos(fotos_etiqueta, tamano_foto=1200)
        secciones.append(construir_seccion(
            "6. Etiqueta", contenido, salto_inicial=len(secciones) > 0
        ))

    # N° para encabezado
    nro_pedido_val = datos.get("nro_pedido", "").strip()
    nro_entrega_val = datos.get("nro_entrega", "").strip()

    if nro_pedido_val and nro_pedido_val != "-":
        nro_doc_html = f'<div class="nro-doc">N° {nro_pedido_val}</div>'
    elif nro_entrega_val and nro_entrega_val != "-":
        nro_doc_html = f'<div class="nro-doc">N° {nro_entrega_val}</div>'
    else:
        nro_doc_html = ""

    if nro_pedido_val and nro_pedido_val != "-":
        nro_pedido_display = nro_pedido_val
    else:
        nro_pedido_display = "—"

    pie_nro = nro_pedido_val if (nro_pedido_val and nro_pedido_val != "-") else (nro_entrega_val if nro_entrega_val != "-" else "S/N")

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
    for k, v in reemplazos.items():
        html_final = html_final.replace(k, str(v))

    nro = datos.get("nro_pedido", "SN").replace("/", "-").replace(" ", "_")
    if not nro or nro == "-" or nro == "SN":
        nro = datos.get("nro_entrega", "SN").replace("/", "-").replace(" ", "_")
    fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    nombre_pdf = f"{config.PREFIJO_PDF}_{nro}_{fecha_str}.pdf"
    
    # 🔥 GUARDAR EN LA CARPETA DEL PEDIDO
    pedido_id = datos.get("pedido_id", None)
    if pedido_id and os.path.exists(f"temp/pedidos/{pedido_id}"):
        ruta_pdf = Path(f"temp/pedidos/{pedido_id}") / nombre_pdf
    else:
        ruta_pdf = config.SALIDA_DIR / nombre_pdf

    # 🔥 GENERAR PDF CON WEASYPRINT
    HTML(string=html_final, base_url=str(config.BASE_DIR)).write_pdf(str(ruta_pdf))

    # Guardar en historial
    try:
        import historial
        historial.guardar_informe(datos, nombre_pdf)
        logging.info(f"Informe guardado en historial: {nombre_pdf}")
    except Exception as e:
        logging.error(f"ERROR al guardar en historial: {e}")

    # Guardar JSON del último informe
    try:
        import json
        with open(config.ULTIMO_INFORME_JSON, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"No se pudo guardar último informe: {e}")

    logging.info(f"Informe generado: {ruta_pdf}")
    return ruta_pdf
