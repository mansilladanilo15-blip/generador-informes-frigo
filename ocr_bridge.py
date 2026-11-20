
"""OCR de estibas optimizado para CPU y procesamiento por lotes."""

import os
import re
import threading
from io import BytesIO

os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

from PIL import Image, ImageOps
import numpy as np

_ocr_local = threading.local()
error_ocr = None


try:
    from paddleocr import PaddleOCR
    import paddle

    paddle.set_device("cpu")

    def obtener_ocr():
        """Inicializa PaddleOCR una sola vez por hilo."""

        if not hasattr(_ocr_local, "model"):

            _ocr_local.model = PaddleOCR(
                lang="es",
                use_textline_orientation=True,
                enable_mkldnn=False,
                cpu_threads=2,
                rec_batch_num=4
            )

        return _ocr_local.model

except Exception as exc:
    error_ocr = str(exc)


def _extraer_textos(resultado):

    textos = []
    confianzas = []

    if resultado is None:
        return textos, confianzas

    if isinstance(resultado, dict):
        res = resultado

    elif isinstance(resultado, (list, tuple)):
        if not resultado:
            return textos, confianzas

        res = resultado[0]

    else:
        res = resultado

    if isinstance(res, dict):

        textos = res.get("rec_texts", []) or []
        confianzas = res.get("rec_scores", []) or []

    else:

        textos = getattr(res, "rec_texts", []) or []
        confianzas = getattr(res, "rec_scores", []) or []

    return textos, confianzas


def _interpretar_texto(nombre, textos, confianzas):

    texto_completo = " ".join(str(t) for t in textos)
    texto_upper = texto_completo.upper()

    confianza_promedio = (
        sum(float(c) for c in confianzas) / len(confianzas)
        if confianzas else 0.0
    )

    pata = None
    cajas = None

    match_cartel = re.search(
        r"PATA[S]?\s*[/\\]\s*CAJA[S]?\D*(\d{1,3})\s*[/\\]\s*(\d{1,4})",
        texto_upper
    )

    if match_cartel:

        pata = int(match_cartel.group(1))
        cajas = int(match_cartel.group(2))

    else:

        matches = re.finditer(
            r"\b(\d{1,3})\s*[/\\]\s*(\d{1,4})\b",
            texto_upper
        )

        for match in matches:

            num1 = int(match.group(1))
            num2 = int(match.group(2))

            if not (num1 <= 31 and num2 <= 12) and num1 <= 99:

                pata = num1
                cajas = num2
                break

    if pata is None:
        pata = 99

    if cajas is None:
        cajas = 0

    return {
        "archivo": nombre,
        "pata": pata,
        "total_cajas": cajas,
        "texto_crudo": texto_completo,
        "confianza": round(confianza_promedio, 3)
    }


def _preparar_imagen(contenido_bytes):

    with Image.open(BytesIO(contenido_bytes)) as original:

        img = ImageOps.exif_transpose(original).convert("RGB")

    max_lado = 1200

    if max(img.width, img.height) > max_lado:

        ratio = max_lado / float(max(img.width, img.height))

        nuevo_tamano = (
            max(1, int(img.width * ratio)),
            max(1, int(img.height * ratio))
        )

        img = img.resize(
            nuevo_tamano,
            Image.Resampling.BILINEAR
        )

    return np.asarray(img)


def analizar_fotos(fotos_bytes_list, progress_callback=None):
    """
    Analiza fotografías en lotes de 4.

    Mantiene el mismo formato de salida:
    archivo, pata, total_cajas, texto_crudo y confianza.
    """

    if error_ocr:
        raise RuntimeError(
            f"El modelo OCR no está disponible. Detalle: {error_ocr}"
        )

    fotos = list(fotos_bytes_list or [])

    resultados = [None] * len(fotos)

    total = len(fotos)

    if not total:
        return []

    ocr_model = obtener_ocr()

    TAMANO_LOTE = 4

    for inicio in range(0, total, TAMANO_LOTE):

        lote = fotos[inicio:inicio + TAMANO_LOTE]

        imagenes_validas = []
        indices_validos = []
        nombres_validos = []

        for posicion, (nombre, contenido) in enumerate(lote):

            indice_real = inicio + posicion

            try:

                imagen = _preparar_imagen(contenido)

                imagenes_validas.append(imagen)
                indices_validos.append(indice_real)
                nombres_validos.append(nombre)

            except Exception as exc:

                resultados[indice_real] = {
                    "archivo": nombre,
                    "pata": None,
                    "total_cajas": None,
                    "texto_crudo": f"ERROR PROCESANDO: {exc}",
                    "confianza": 0.0
                }

        if imagenes_validas:

            try:

                # Procesamiento conjunto de las imágenes.
                predicciones = ocr_model.predict(
                    imagenes_validas,
                    batch_size=len(imagenes_validas)
                )

                predicciones = list(predicciones)

                if len(predicciones) != len(imagenes_validas):
                    raise RuntimeError(
                        "El OCR devolvió una cantidad inesperada de resultados."
                    )

                for indice_real, nombre, prediccion in zip(
                    indices_validos,
                    nombres_validos,
                    predicciones
                ):

                    textos, confianzas = _extraer_textos(prediccion)

                    resultados[indice_real] = _interpretar_texto(
                        nombre,
                        textos,
                        confianzas
                    )

            except Exception as exc:

                # Recuperación individual si falla el lote.
                for indice_real, nombre, imagen in zip(
                    indices_validos,
                    nombres_validos,
                    imagenes_validas
                ):

                    try:

                        prediccion = list(
                            ocr_model.predict(imagen)
                        )

                        textos, confianzas = _extraer_textos(
                            prediccion
                        )

                        resultados[indice_real] = _interpretar_texto(
                            nombre,
                            textos,
                            confianzas
                        )

                    except Exception as error_individual:

                        resultados[indice_real] = {
                            "archivo": nombre,
                            "pata": None,
                            "total_cajas": None,
                            "texto_crudo": (
                                f"ERROR OCR: {error_individual}"
                            ),
                            "confianza": 0.0
                        }

        if progress_callback:

            for posicion, (nombre, _) in enumerate(lote):

                try:

                    progress_callback(
                        inicio + posicion + 1,
                        total,
                        nombre
                    )

                except Exception:
                    pass

    return resultados
