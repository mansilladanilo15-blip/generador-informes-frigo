"""OCR de estibas optimizado para CPU.

Mantiene la misma estructura de salida de analizar_fotos() para ser compatible
con la aplicación de PC. Admite un callback opcional de progreso.
"""
import os
import re
import threading
from io import BytesIO

# Limitar hilos evita sobrecarga en despliegues pequeños; se permiten 2 hilos
# de CPU y un lote de reconocimiento mayor que 1.
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


def _extraer_textos(resultado):
    """Extrae texto y confianza de la respuesta de PaddleOCR 3.x."""
    textos = []
    confianzas = []
    if resultado and len(resultado) > 0:
        res = resultado[0]
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
        sum(float(c) for c in confianzas) / len(confianzas) if confianzas else 0.0
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
        # Mantiene la lógica alternativa existente para carteles sin palabras.
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


def analizar_fotos(fotos_bytes_list, progress_callback=None):
    """Analiza una lista de (nombre, bytes), devolviendo resultados en el mismo orden.

    progress_callback es opcional y recibe (procesadas, total, nombre_actual).
    """
    if error_ocr:
        raise RuntimeError(f"El modelo OCR no está disponible. Detalle: {error_ocr}")

    fotos = list(fotos_bytes_list or [])
    resultados = []
    total = len(fotos)
    if not total:
        return resultados

    ocr_model = obtener_ocr()

    for indice, (nombre, contenido_bytes) in enumerate(fotos, start=1):
        try:
            with Image.open(BytesIO(contenido_bytes)) as original:
                img = ImageOps.exif_transpose(original).convert("RGB")

            # Mantiene el límite original de 1200 px para conservar legibilidad.
            max_lado = 1200
            if max(img.width, img.height) > max_lado:
                ratio = max_lado / float(max(img.width, img.height))
                nuevo_tamano = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                img = img.resize(nuevo_tamano, Image.Resampling.BILINEAR)

            resultado = ocr_model.predict(np.asarray(img))
            textos, confianzas = _extraer_textos(resultado)
            resultados.append(_interpretar_texto(nombre, textos, confianzas))
        except Exception as exc:
            resultados.append({
                "archivo": nombre,
                "pata": None,
                "total_cajas": None,
                "texto_crudo": f"ERROR PROCESANDO: {exc}",
                "confianza": 0.0,
            })
        finally:
            if progress_callback:
                try:
                    progress_callback(indice, total, nombre)
                except Exception:
                    # Un fallo visual del callback no debe interrumpir el OCR.
                    pass

    return resultados
