"""OCR de estibas optimizado para CPU y procesamiento por lotes.

Mantiene la interfaz analizar_fotos(fotos_bytes_list, progress_callback=None)
compatible con app.py. Utiliza PaddleOCR 3.x y conserva un fallback individual
si el procesamiento por lotes no está disponible en la versión instalada.
"""

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
        """Inicializa PaddleOCR una sola vez por hilo y reutiliza el modelo."""
        if not hasattr(_ocr_local, "model"):
            _ocr_local.model = PaddleOCR(
                lang="es",
                use_textline_orientation=True,
                enable_mkldnn=False,
                cpu_threads=2,
                rec_batch_num=4,
            )
        return _ocr_local.model

except Exception as exc:
    error_ocr = str(exc)


def _materializar_resultados(salida):
    """Convierte la salida de predict() (lista o generador) en una lista."""
    if salida is None:
        return []
    if isinstance(salida, (list, tuple)):
        return list(salida)
    if isinstance(salida, dict) or hasattr(salida, "json"):
        return [salida]
    try:
        return list(salida)
    except TypeError:
        return [salida]


def _extraer_textos(resultado):
    """Extrae texto y confianza de un resultado PaddleOCR 3.x."""
    textos = []
    confianzas = []

    if isinstance(resultado, (list, tuple)):
        resultado = resultado[0] if resultado else None
    if resultado is None:
        return textos, confianzas

    datos = resultado if isinstance(resultado, dict) else getattr(resultado, "json", None)
    if callable(datos):
        datos = datos()

    if isinstance(datos, dict):
        datos = datos.get("res", datos)
        if isinstance(datos, dict):
            textos = datos.get("rec_texts", []) or []
            confianzas = datos.get("rec_scores", []) or []

    if not textos and not isinstance(resultado, dict):
        textos = getattr(resultado, "rec_texts", []) or []
        confianzas = getattr(resultado, "rec_scores", []) or []

    return textos, confianzas


def _interpretar_texto(nombre, textos, confianzas):
    texto_completo = " ".join(str(t) for t in textos)
    texto_upper = texto_completo.upper()

    confianza_promedio = (
        sum(float(c) for c in confianzas) / len(confianzas)
        if confianzas else 0.0
    )

    pata, cajas = None, None

    match_cartel = re.search(
        r"PATA[S]?\s*[/\\]\s*CAJA[S]?\D*(\d{1,3})\s*[/\\]\s*(\d{1,4})",
        texto_upper,
    )

    if match_cartel:
        pata = int(match_cartel.group(1))
        cajas = int(match_cartel.group(2))
    else:
        matches = re.finditer(r"\b(\d{1,3})\s*[/\\]\s*(\d{1,4})\b", texto_upper)
        for match in matches:
            num1 = int(match.group(1))
            num2 = int(match.group(2))
            if not (num1 <= 31 and num2 <= 12) and num1 <= 99:
                pata, cajas = num1, num2
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
        "confianza": round(confianza_promedio, 3),
    }


def _preparar_imagen(nombre, contenido_bytes):
    with Image.open(BytesIO(contenido_bytes)) as original:
        img = ImageOps.exif_transpose(original).convert("RGB")

    max_lado = 1200
    lado_mayor = max(img.width, img.height)
    if lado_mayor > max_lado:
        ratio = max_lado / float(lado_mayor)
        nuevo_tamano = (
            max(1, int(img.width * ratio)),
            max(1, int(img.height * ratio)),
        )
        img = img.resize(nuevo_tamano, Image.Resampling.BILINEAR)

    return np.asarray(img)


def analizar_fotos(fotos_bytes_list, progress_callback=None):
    """Analiza varias fotos en lotes, preservando el orden de entrada."""
    if error_ocr:
        raise RuntimeError(f"El modelo OCR no está disponible. Detalle: {error_ocr}")

    fotos = list(fotos_bytes_list or [])
    total = len(fotos)
    if not total:
        return []

    ocr_model = obtener_ocr()
    resultados = [None] * total
    imagenes_validas = []
    indices_validos = []

    for indice, (nombre, contenido_bytes) in enumerate(fotos):
        try:
            imagenes_validas.append(_preparar_imagen(nombre, contenido_bytes))
            indices_validos.append(indice)
        except Exception as exc:
            resultados[indice] = {
                "archivo": nombre,
                "pata": None,
                "total_cajas": None,
                "texto_crudo": f"ERROR PROCESANDO: {exc}",
                "confianza": 0.0,
            }

    # PaddleOCR 3.x admite listas de imágenes y batch_size en predict().
    # Se limita a 4 imágenes por lote para moderar el uso de RAM en Streamlit Cloud.
    tamano_lote = 4
    procesadas = set()

    for inicio in range(0, len(imagenes_validas), tamano_lote):
        fin = min(inicio + tamano_lote, len(imagenes_validas))
        lote_imgs = imagenes_validas[inicio:fin]
        lote_indices = indices_validos[inicio:fin]

        try:
            lote_resultados = _materializar_resultados(
                ocr_model.predict(lote_imgs, batch_size=len(lote_imgs))
            )
            if len(lote_resultados) != len(lote_imgs):
                raise RuntimeError(
                    "PaddleOCR devolvió una cantidad inesperada de resultados."
                )
        except Exception:
            # Compatibilidad: algunas versiones/builds no aceptan listas
            # o batch_size. En ese caso se materializa la salida individual,
            # que puede ser un generador y no necesariamente una lista.
            lote_resultados = []
            for imagen in lote_imgs:
                individual = _materializar_resultados(
                    ocr_model.predict(imagen)
                )
                if not individual:
                    raise RuntimeError(
                        "PaddleOCR no devolvió resultados para una fotografía."
                    )
                lote_resultados.append(individual[0])

        for indice_original, resultado in zip(lote_indices, lote_resultados):
            nombre = fotos[indice_original][0]
            try:
                textos, confianzas = _extraer_textos(resultado)
                resultados[indice_original] = _interpretar_texto(
                    nombre, textos, confianzas
                )
            except Exception as exc:
                resultados[indice_original] = {
                    "archivo": nombre,
                    "pata": None,
                    "total_cajas": None,
                    "texto_crudo": f"ERROR PROCESANDO: {exc}",
                    "confianza": 0.0,
                }
            procesadas.add(indice_original)

        if progress_callback:
            for indice_original in lote_indices:
                try:
                    progress_callback(
                        indice_original + 1,
                        total,
                        fotos[indice_original][0],
                    )
                except Exception:
                    pass

    # Reportar también las imágenes que fallaron al abrirse.
    if progress_callback:
        for indice, (nombre, _) in enumerate(fotos):
            if indice not in procesadas and resultados[indice] is not None:
                try:
                    progress_callback(indice + 1, total, nombre)
                except Exception:
                    pass

    return resultados
