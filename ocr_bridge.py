import os
import re
import threading
from io import BytesIO
from PIL import Image
import numpy as np

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

try:
    from paddleocr import PaddleOCR
    import paddle

    paddle.set_device('cpu')
    _ocr_local = threading.local()

    def obtener_ocr():
        if not hasattr(_ocr_local, "model"):
            _ocr_local.model = PaddleOCR(
                lang='en',
                use_textline_orientation=True,
                enable_mkldnn=False,
                cpu_threads=1,        
                rec_batch_num=1,      
            )
        return _ocr_local.model

    error_ocr = None
except Exception as e:
    error_ocr = str(e)


def analizar_fotos(fotos_bytes_list):
    if error_ocr:
        raise Exception(f"El modelo OCR no está disponible. Detalle: {error_ocr}")

    resultados = []

    for nombre, contenido_bytes in fotos_bytes_list:
        try:
            ocr_model = obtener_ocr()
            img = Image.open(BytesIO(contenido_bytes)).convert("RGB")

            max_lado = 1000  
            if max(img.width, img.height) > max_lado:
                ratio = max_lado / max(img.width, img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)))

            img_array = np.array(img)
            resultado = ocr_model.predict(img_array)

            textos = []
            confianzas = []

            if resultado and len(resultado) > 0:
                res = resultado[0]
                if isinstance(res, dict):
                    textos = res.get('rec_texts', [])
                    confianzas = res.get('rec_scores', [])
                else:
                    textos = getattr(res, 'rec_texts', [])
                    confianzas = getattr(res, 'rec_scores', [])

            texto_completo = " ".join(textos)
            # Limpiamos el texto de espacios extra
            texto_upper = texto_completo.upper()
            confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0.0

            # --- 🔥 LÓGICA ESTRICTA BASADA EN LA FOTO 🔥 ---
            pata, cajas = None, None

            # 1. Buscar el patrón "NÚMERO / NÚMERO" (Ej: 9/55, 15 / 52)
            # Esto captura específicamente el número de pata y de cajas en el centro.
            match = re.search(r'(\d{1,2})\s*[\/|]\s*(\d{1,4})', texto_upper)
            
            if match:
                pata = int(match.group(1))
                cajas = int(match.group(2))
            
            # 2. Si por alguna razón el OCR falló y no encontró la barra, 
            # buscamos si hay dos números juntos (ej: 9 55)
            if pata is None or cajas is None:
                match_espacio = re.search(r'\b(\d{1,2})\s+(\d{2,4})\b', texto_upper)
                if match_espacio:
                    # Validamos que el primer número sea menor a 50 (para no confundir con la entrega)
                    if int(match_espacio.group(1)) < 50:
                        pata = int(match_espacio.group(1))
                        cajas = int(match_espacio.group(2))

            # 3. Si aún no hay pata, mandar a 99. Si no hay cajas, poner 0.
            if pata is None:
                pata = 99 
            if cajas is None:
                cajas = 0

            resultados.append({
                "archivo": nombre,
                "pata": pata,
                "total_cajas": cajas,
                "texto_crudo": texto_completo,
                "confianza": round(confianza_promedio, 3)
            })

        except Exception as e:
            resultados.append({
                "archivo": nombre,
                "pata": None,
                "total_cajas": None,
                "texto_crudo": f"ERROR PROCESANDO: {e}",
                "confianza": 0.0
            })

    return resultados
