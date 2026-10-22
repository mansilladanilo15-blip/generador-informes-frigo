import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
import logging
import os  # <--- Verifica que esté esta línea

from PIL import Image, ImageOps
import pdfkit

import sys
import os

# Detectar si estamos corriendo como .exe o como script normal
if getattr(sys, 'frozen', False):
    # Si es .exe, buscar en la carpeta temporal interna o al lado del .exe
    BASE_PATH = sys._MEIPASS
else:
    # Si es script normal, buscar en la carpeta del proyecto
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

# Ruta al wkhtmltopdf (debes haber copiado la carpeta a tu proyecto)
WKHTMLTOPDF_PATH = os.path.join(BASE_PATH, "wkhtmltox", "bin", "wkhtmltopdf.exe")

# Si no lo encuentra, usa el que está instalado en el sistema
if not os.path.exists(WKHTMLTOPDF_PATH):
    WKHTMLTOPDF_PATH = r"C:\Users\dmansillan\wkhtmltopdf\wkhtmltox-0.12.6-1.mxe-cross-win64\wkhtmltox\bin\wkhtmltopdf.exe"

PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)
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


def _celda_foto(data_uri, pie, clase):
    return f'''
    <td class="celda-foto {clase}">
      <div class="contenedor-img">
        <img src="{data_uri}">
      </div>
      <div class="pie-foto">{pie}</div>
    </td>
    '''


def construir_grid_fotos(lista_fotos, tamano_foto=1200):
    if not lista_fotos:
        return ""

    total = len(lista_fotos)
    html = ""

    if total == 1:
        foto = lista_fotos[0]
        data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
        pie = foto.get("pie", "Foto 1")
        return f'''
        <table class="tabla-fotos tabla-single">
          <tr>
            {_celda_foto(data_uri, pie, "single")}
          </tr>
        </table>
        '''

    if total == 2:
        html += '<table class="tabla-fotos"><tr>'
        for i in range(1, 3):
            foto = lista_fotos[i - 1]
            data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
            pie = foto.get("pie", f"Foto {i}")
            html += _celda_foto(data_uri, pie, "grande")
        html += '</tr></table>'
        return html

    if total == 3:
        foto1 = lista_fotos[0]
        data1 = comprimir_foto(foto1["archivo"], tamano_max=tamano_foto)
        pie1 = foto1.get("pie", "Foto 1")
        html += f'''
        <table class="tabla-fotos">
          <tr>
            <td class="celda-foto ancha" colspan="2">
              <div class="contenedor-img">
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
            html += _celda_foto(data_uri, pie, "mediana")
        html += '</tr></table>'
        return html

    if total == 4:
        html += '<table class="tabla-fotos">'
        for fila in range(2):
            html += '<tr>'
            for col in range(2):
                idx = fila * 2 + col + 1
                foto = lista_fotos[idx - 1]
                data_uri = comprimir_foto(foto["archivo"], tamano_max=tamano_foto)
                pie = foto.get("pie", f"Foto {idx}")
                html += _celda_foto(data_uri, pie, "mediana")
            html += '</tr>'
        html += '</table>'
        return html

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
                {_celda_foto(data_uri, pie, "single")}
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
                html += _celda_foto(data_uri, pie, "mediana")
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
                html += _celda_foto(data_uri, pie, "mediana")
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
                    html += _celda_foto(data_uri, pie, "mediana")
                    idx += 1
                html += '</tr>'
            html += '</table>'

        primera_pagina = False

    return html


def construir_tabla_estibas(filas):
    if not filas:
        return ""

    # Se agrega page-break-inside: avoid para que la tabla no se corte
    html = '''
    <table class="tabla-estibas" style="page-break-inside: avoid;">
      <thead>
        <tr>
          <th style="width:20%;">N°</th>
          <th style="width:50%;">Producto</th>
          <th style="width:30%;">Cantidad</th>
        </tr>
      </thead>
      <tbody>
    '''
    
    total = 0
    for i, f in enumerate(filas, start=1):
        cantidad_str = str(f.get("cantidad", "")).strip()
        try:
            total += int(cantidad_str)
        except (ValueError, TypeError):
            pass
            
        html += f'''
        <tr>
          <td><strong>{i}</strong></td>
          <td>PATA</td>
          <td>{cantidad_str}</td>
        </tr>
        '''
        
    # Fila de TOTAL modificada: Fondo blanco, letras azules y borde grueso
    html += f'''
    <tr style="background-color: #ffffff;">
      <td colspan="2" style="text-align: right; padding-right: 15px; font-size: 11px; font-weight: bold; color: #1a4d8f; border-top: 2px solid #1a4d8f;">TOTAL CAJAS:</td>
      <td style="text-align: center; font-size: 12px; font-weight: bold; color: #1a4d8f; border-top: 2px solid #1a4d8f;">{total}</td>
    </tr>
    '''
    html += '</tbody></table>'
    
    return html


def construir_seccion(titulo, contenido, salto_inicial=False):
    salto = '<div class="salto-pagina"></div>' if salto_inicial else ""
    return f'''
    {salto}
    <div class="titulo-categoria">{titulo}</div>
    {contenido}
    '''


def _construir_portada_html(datos, reemplazos):
    """Genera el HTML de la portada (solo primera página, con encabezado grande)."""
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <style>
        @page {{ size: Letter; margin: 2.54cm; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: 'Segoe UI', Arial, sans-serif;
          font-size: 10px;
          color: #2c3e50;
          line-height: 1.3;
        }}
        .encabezado {{
          width: 100%;
          border-bottom: 3px solid #1a4d8f;
          padding-bottom: 8px;
          margin-bottom: 8px;
        }}
        .encabezado td {{ vertical-align: middle; }}
        .logo-box-izq, .logo-box-der {{
          width: 130px;
          height: 110px;
          vertical-align: middle;
        }}
        .logo-box-izq {{ text-align: left; }}
        .logo-box-der {{ text-align: right; }}
        .logo-box-izq img, .logo-box-der img {{
          height: 100px;
          width: auto;
          max-width: 130px;
          object-fit: contain;
          display: inline-block;
          vertical-align: middle;
        }}
        .titulo-box {{ text-align: center; padding: 0 10px; }}
        .empresa {{
          font-size: 9px;
          font-weight: 600;
          color: #1a4d8f;
          letter-spacing: 0.8px;
          text-transform: uppercase;
        }}
        .titulo-box h1 {{
          font-size: 14px;
          color: #1a4d8f;
          margin: 1px 0;
        }}
        .nro-doc {{
          font-size: 9px;
          font-weight: 700;
          color: #e74c3c;
        }}
        .banda-estado {{
          background: #f2f6fb;
          border-left: 3px solid #1a4d8f;
          padding: 4px 8px;
          margin: 5px 0;
          font-size: 8.5px;
        }}
        .banda-estado .etiqueta {{ font-weight: 700; color: #1a4d8f; }}
        .banda-estado .separador {{ color: #ccc; margin: 0 6px; }}
        .tabla-datos {{
          width: 100%;
          border-collapse: collapse;
          border: 1px solid #d0d7de;
          margin-bottom: 8px;
        }}
        .tabla-datos td {{
          padding: 4px 7px;
          border: 1px solid #d0d7de;
          font-size: 9px;
        }}
        .etiqueta-campo {{
          width: 15%;
          background: #f2f6fb;
          font-weight: 600;
          color: #1a4d8f;
          text-transform: uppercase;
        }}
        .valor-campo {{ width: 35%; }}
        .subtitulo {{
          background: #e8f0fa;
          color: #1a4d8f;
          font-weight: 700;
          font-size: 9px;
          text-transform: uppercase;
          padding: 4px 7px;
          border: 1px solid #d0d7de;
          border-bottom: none;
        }}
      </style>
    </head>
    <body>
      <table class="encabezado">
        <tr>
          <td class="logo-box-izq">{reemplazos["{{logo_izq_html_grande}}"]}</td>
          <td class="titulo-box">
            <div class="empresa">{reemplazos["{{empresa}}"]}</div>
            <h1>{reemplazos["{{titulo_informe}}"]}</h1>
            {reemplazos["{{nro_doc_html}}"]}
          </td>
          <td class="logo-box-der">{reemplazos["{{logo_der_html_grande}}"]}</td>
        </tr>
      </table>

      <div class="banda-estado">
        <span class="etiqueta">FECHA:</span> {reemplazos["{{fecha}}"]}
        <span class="separador">|</span>
        <span class="etiqueta">N° ENTREGA:</span> {reemplazos["{{nro_entrega}}"]}
        <span class="separador">|</span>
        <span class="etiqueta">GUÍA DESPACHO:</span> {reemplazos["{{guia_despacho}}"]}
      </div>

      <table class="tabla-datos">
        <tr>
          <td class="etiqueta-campo">Cliente / Destino</td>
          <td class="valor-campo">{reemplazos["{{cliente}}"]}</td>
          <td class="etiqueta-campo">Origen</td>
          <td class="valor-campo">{reemplazos["{{origen}}"]}</td>
        </tr>
        <tr>
          <td class="etiqueta-campo">N° Pedido</td>
          <td class="valor-campo">{reemplazos["{{nro_pedido_display}}"]}</td>
          <td class="etiqueta-campo">Tipo</td>
          <td class="valor-campo">{reemplazos["{{tipo_informe}}"]}</td>
        </tr>
      </table>

      <div class="subtitulo">🚛 Datos del transporte</div>
      <table class="tabla-datos" style="margin-bottom: 12px;">
        <tr>
          <td class="etiqueta-campo">Transporte</td>
          <td class="valor-campo">{reemplazos["{{transporte}}"]}</td>
          <td class="etiqueta-campo">Chofer</td>
          <td class="valor-campo">{reemplazos["{{chofer}}"]}</td>
        </tr>
        <tr>
          <td class="etiqueta-campo">Patente Camión</td>
          <td class="valor-campo">{reemplazos["{{patente_camion}}"]}</td>
          <td class="etiqueta-campo">Patente Rampla</td>
          <td class="valor-campo">{reemplazos["{{patente_rampla}}"]}</td>
        </tr>
        <tr>
          <td class="etiqueta-campo">Sello Final</td>
          <td class="valor-campo">{reemplazos["{{sello_final}}"]}</td>
          <td class="etiqueta-campo">Sellos Provisorios</td>
          <td class="valor-campo">{reemplazos["{{sellos_provisorios}}"]}</td>
        </tr>
        <tr>
          <td class="etiqueta-campo">N° Termógrafo</td>
          <td class="valor-campo" colspan="3">{reemplazos["{{nro_termografo}}"]}</td>
        </tr>
      </table>
    </body>
    </html>
    """
    return html


def generar_informe(datos, fotos_por_categoria, filas_estibas=None):
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
    titulo_informe = "REPORTE FOTOGRÁFICO CONGELADO" if "traslado" in tipo else "REPORTE FOTOGRÁFICO FRESCO"

    # Secciones
    secciones = []
    fotos_estibas = fotos_por_categoria.get("estibas", [])
    tabla_estibas = filas_estibas or []
    if fotos_estibas or tabla_estibas:
        contenido = construir_tabla_estibas(tabla_estibas)
        contenido += construir_grid_fotos(fotos_estibas, tamano_foto=1200)
        secciones.append(construir_seccion("1. Fotos Estibas", contenido))

    fotos_camion = fotos_por_categoria.get("camion", [])
    if fotos_camion:
        contenido = construir_grid_fotos(fotos_camion, tamano_foto=1200)
        secciones.append(construir_seccion("2. Fotos Camión", contenido, salto_inicial=len(secciones) > 0))

    fotos_termografo = fotos_por_categoria.get("termografo", [])
    if fotos_termografo:
        contenido = construir_grid_fotos(fotos_termografo, tamano_foto=1200)
        secciones.append(construir_seccion("3. Termógrafo", contenido, salto_inicial=len(secciones) > 0))

    fotos_sello = fotos_por_categoria.get("sello", [])
    if fotos_sello:
        contenido = construir_grid_fotos(fotos_sello, tamano_foto=1200)
        secciones.append(construir_seccion("4. Sello/s final/es o provisorio/s", contenido, salto_inicial=len(secciones) > 0))

    fotos_thermoking = fotos_por_categoria.get("thermoking", [])
    if fotos_thermoking:
        contenido = construir_grid_fotos(fotos_thermoking, tamano_foto=1200)
        secciones.append(construir_seccion("5. Thermo-king", contenido, salto_inicial=len(secciones) > 0))

    fotos_etiqueta = fotos_por_categoria.get("etiqueta", [])
    if fotos_etiqueta:
        contenido = construir_grid_fotos(fotos_etiqueta, tamano_foto=1200)
        secciones.append(construir_seccion("6. Etiqueta", contenido, salto_inicial=len(secciones) > 0))

    # Reemplazos
    nro_pedido_val = datos.get("nro_pedido", "").strip()
    nro_entrega_val = datos.get("nro_entrega", "").strip()
    nro_doc_html = f'<div class="nro-doc">N° {nro_pedido_val}</div>' if nro_pedido_val and nro_pedido_val != "-" else (f'<div class="nro-doc">N° {nro_entrega_val}</div>' if nro_entrega_val and nro_entrega_val != "-" else "")
    nro_pedido_display = nro_pedido_val if nro_pedido_val and nro_pedido_val != "-" else "—"
    pie_nro = nro_pedido_val if (nro_pedido_val and nro_pedido_val != "-") else (nro_entrega_val if nro_entrega_val != "-" else "S/N")

    reemplazos = {
        "{{logo_izq_html_grande}}": logo_izq_html_grande, "{{logo_der_html_grande}}": logo_der_html_grande,
        "{{empresa}}": datos.get("empresa", ""), "{{titulo_informe}}": titulo_informe,
        "{{nro_doc_html}}": nro_doc_html, "{{nro_pedido_display}}": nro_pedido_display,
        "{{tipo_informe}}": datos.get("tipo_informe", ""), "{{nro_pedido}}": pie_nro,
        "{{fecha}}": datos.get("fecha", ""), "{{nro_entrega}}": datos.get("nro_entrega", "-"),
        "{{guia_despacho}}": datos.get("guia_despacho", "-"), "{{cliente}}": datos.get("cliente", ""),
        "{{origen}}": datos.get("origen", ""), "{{transporte}}": datos.get("transporte", "-"),
        "{{chofer}}": datos.get("chofer", "-"), "{{patente_camion}}": datos.get("patente_camion", "-"),
        "{{patente_rampla}}": datos.get("patente_rampla", "-"), "{{sello_final}}": datos.get("sello_final", "-"),
        "{{sellos_provisorios}}": datos.get("sellos_provisorios", "-"), "{{nro_termografo}}": datos.get("nro_termografo", "-"),
        "{{fecha_generacion}}": fecha_gen,
    }

    portada_path = config.TEMP_DIR / "wk_portada.html"
    cuerpo_path = config.TEMP_DIR / "wk_cuerpo.html"
    header_path = config.TEMP_DIR / "wk_header.html"
    footer_path = config.TEMP_DIR / "wk_footer.html"
    
    portada_pdf = config.TEMP_DIR / "portada_temp.pdf"
    cuerpo_pdf = config.TEMP_DIR / "cuerpo_temp.pdf"

    # 1. Portada HTML (Sin header/footer)
    portada_html = _construir_portada_html(datos, reemplazos)
    with open(portada_path, "w", encoding="utf-8") as f:
        f.write(portada_html)

    # 2. Cuerpo HTML (Con estilos de fotos)
    cuerpo_html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <style>
        @page {{ size: Letter; margin: 0; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 10px; color: #2c3e50; line-height: 1.3; }}
        .titulo-categoria {{ background: #1a4d8f; color: #fff; padding: 5px 10px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; text-align: center; }}
        .tabla-fotos {{ width: 100%; border-collapse: separate; border-spacing: 6px; table-layout: fixed; margin-bottom: 8px; }}
        .tabla-fotos td.celda-foto {{ width: 50%; border: 1px solid #c5cdd6; background: #fff; text-align: center; vertical-align: middle; padding: 3px; page-break-inside: avoid; border-radius: 3px; }}
        .tabla-fotos td.celda-vacia {{ width: 50%; border: none; background: transparent; padding: 0; }}
        .tabla-fotos.tabla-single {{ width: 65%; margin: 15px auto; }}
        .contenedor-img {{ width: 100%; text-align: center; overflow: hidden; line-height: 0; }}
        .contenedor-img img {{ max-width: 100%; width: auto; height: auto; display: block; margin: 0 auto; }}
        .celda-foto.grande .contenedor-img img {{ max-height: 350px; }}
        .celda-foto.mediana .contenedor-img img {{ max-height: 230px; }}
        .celda-foto.ancha .contenedor-img img {{ max-height: 230px; }}
        .celda-foto.single .contenedor-img img {{ max-height: 480px; }}
        .pie-foto {{ font-size: 8px; color: #555; text-align: center; margin-top: 3px; font-weight: 600; line-height: 1.2; padding-top: 2px; border-top: 1px dashed #ddd; }}
        .salto-pagina {{ page-break-after: always; height: 0; line-height: 0; display: block; }}
        .tabla-estibas {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #d0d7de; }}
        .tabla-estibas th {{ background: #1a4d8f; color: #fff; padding: 4px 8px; font-size: 8.5px; text-transform: uppercase; text-align: center; }}
        .tabla-estibas td {{ padding: 4px 8px; border: 1px solid #d0d7de; font-size: 9px; text-align: center; }}
        .tabla-estibas tr:nth-child(even) td {{ background: #f8fafc; }}
      </style>
    </head>
    <body>
      {"".join(secciones)}
    </body>
    </html>
    """
    with open(cuerpo_path, "w", encoding="utf-8") as f:
        f.write(cuerpo_html)

    # 3. Generar PDF Portada
    options_portada = {
        "enable-local-file-access": "", "encoding": "UTF-8", "page-size": "Letter",
        "margin-top": "25.4mm", "margin-bottom": "25.4mm", "margin-left": "25.4mm", "margin-right": "25.4mm",
        "dpi": "96", "image-quality": "85", "disable-smart-shrinking": "", "print-media-type": "",
    }
    pdfkit.from_file(str(portada_path), str(portada_pdf), configuration=PDFKIT_CONFIG, options=options_portada)

    # 4. Preparar Header y Footer
    header_template = (config.BASE_DIR / "header.html").read_text(encoding="utf-8")
    header_html = header_template.replace("{{logo_izq_mini}}", logo_izq_html)
    header_html = header_html.replace("{{logo_der_mini}}", logo_der_html)
    header_html = header_html.replace("{{empresa}}", datos.get("empresa", ""))
    header_html = header_html.replace("{{titulo_informe}}", titulo_informe)
    header_html = header_html.replace("{{nro_pedido}}", pie_nro)
    with open(header_path, "w", encoding="utf-8") as f:
        f.write(header_html)

    footer_template = (config.BASE_DIR / "footer.html").read_text(encoding="utf-8")
    footer_html = footer_template.replace("{{empresa}}", datos.get("empresa", ""))
    with open(footer_path, "w", encoding="utf-8") as f:
        f.write(footer_html)

    # 5. Generar PDF del Cuerpo
    # Usamos footer-html para el diseño y footer-right para inyectar la numeración nativa
    options_cuerpo = {
        "enable-local-file-access": "", "encoding": "UTF-8", "page-size": "Letter",
        "margin-top": "22mm", "margin-bottom": "18mm", "margin-left": "25.4mm", "margin-right": "25.4mm",
        "dpi": "96", "image-quality": "85", "disable-smart-shrinking": "", "print-media-type": "",
        "header-html": str(header_path), "footer-html": str(footer_path),
        "header-spacing": "0", "footer-spacing": "0",
        # Sobrescribimos el texto de la derecha del footer con la paginación real
        "footer-right": "Página [page] de [topage]",
        "footer-font-size": "8",
        "footer-font-name": "Segoe UI",
        "footer-spacing": "-25", # Lo ocultamos del footer.html
    }
    
    # Nota: Al pasar footer-right, wkhtmltopdf imprime el texto flotante. 
    # Para que esto no choque con el footer.html, usaremos una opción más limpia:
    options_cuerpo.pop("footer-html") # Quitamos el HTML externo del pie
    options_cuerpo.update({
        "footer-left": f"{datos.get('empresa', '')} — Documento interno",
        "footer-right": "Página [page] de [topage]",
        "footer-font-size": "8",
        "footer-spacing": "3",
    })
    
    pdfkit.from_file(str(cuerpo_path), str(cuerpo_pdf), configuration=PDFKIT_CONFIG, options=options_cuerpo)

    # 6. Unir Portada + Cuerpo
    from pypdf import PdfReader, PdfWriter
    portada_reader = PdfReader(str(portada_pdf))
    cuerpo_reader = PdfReader(str(cuerpo_pdf))

    writer = PdfWriter()
    for page in portada_reader.pages:
        writer.add_page(page)
    for page in cuerpo_reader.pages:
        writer.add_page(page)

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

    with open(ruta_pdf, "wb") as f:
        writer.write(f)
    writer.close()

    # Historial
    try:
        import historial
        historial.guardar_informe(datos, nombre_pdf)
    except Exception as e:
        pass

    try:
        import json
        with open(config.ULTIMO_INFORME_JSON, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

    return ruta_pdf