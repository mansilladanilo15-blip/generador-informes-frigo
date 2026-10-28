                    <div class="contenedor-img"><img src="{data_uri}" alt="{pie}"></div>
                    <div class="pie-foto">{pie}</div>
                </td>''')
            if len(fila) == 1:
                html.append('<td class="celda-foto celda-vacia"></td>')
            html.append('</tr>')

        html.append('</tbody></table>')

    return "\\n".join(html)


def construir_tabla_estibas(filas):
    """Crea la tabla de estibas usando la pata real guardada y suma las cajas."""
    if not filas:
        return ""

    html = ["""
    <table class="tabla-estibas">
      <thead><tr>
        <th class="col-numero">N°</th>
        <th class="col-producto">Producto</th>
        <th class="col-cantidad">Cantidad</th>
      </tr></thead><tbody>
    """]
    total = 0
    filas_ordenadas = sorted(filas, key=lambda f: int(f.get("pata", 0) or 0))

    for fila in filas_ordenadas:
        try:
            pata = int(fila.get("pata", 0) or 0)
        except (TypeError, ValueError):
            pata = 0
        try:
            cantidad = int(fila.get("cantidad", 0) or 0)
        except (TypeError, ValueError):
            cantidad = 0
        total += cantidad
        producto = f"PATA {pata}" if pata else "PATA SIN ASIGNAR"
        if pata == 99:
            producto = "PATA 99 — PENDIENTE DE REVISIÓN"
        html.append(f"""
        <tr>
          <td><strong>{pata if pata else '—'}</strong></td>
          <td>{escape(producto)}</td>
          <td>{cantidad}</td>
        </tr>
        """)

    html.append(f"""
      <tr class="fila-total">
        <td colspan="2">TOTAL CAJAS:</td><td>{total}</td>
      </tr>
    </tbody></table>
    """)
    return "\n".join(html)


def construir_seccion(titulo, contenido, salto_inicial=False):
    salto = '<div class="salto-pagina"></div>' if salto_inicial else ""
    return f"""
    {salto}
    <section class="seccion-informe">
      <div class="titulo-categoria">{escape(str(titulo))}</div>
      {contenido}
    </section>
    """


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
