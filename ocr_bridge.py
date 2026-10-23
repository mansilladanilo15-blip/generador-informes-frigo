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
                lang='es',                # 🔥 Volvemos a Español para leer mejor "PATA/CAJAS"
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

            # Mantenemos un buen tamaño para que los números gruesos se lean bien
            max_lado = 1200  
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
            texto_upper = texto_completo.upper()
            confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0.0

            # --- 🔥 LÓGICA DE BÚSQUEDA BASADA EN TU CARTEL 🔥 ---
            pata, cajas = None, None

            # 1. Buscamos el formato exacto del cartel: PATA/CAJAS X/Y
            # \D* significa "cualquier cosa que no sea un número" (por si el OCR lee "PATA/CAJAS 11/54" o "PATAS/CAJAS 11/54")
            match_cartel = re.search(r'PATA[S]?\s*[/\\]\s*CAJA[S]?\D*(\d{1,3})\s*[\/\\]\s*(\d{1,4})', texto_upper)
            
            if match_cartel:
                pata = int(match_cartel.group(1))
                cajas = int(match_cartel.group(2))
            else:
                # 2. Si el OCR no leyó "PATA/CAJAS" por alguna sombra, buscamos cualquier "X/Y"
                # pero filtramos para que NO sea la fecha (que tiene 2 barras) ni la entrega.
                # Buscamos algo que tenga entre 1 y 3 dígitos, barra, y 1 a 4 dígitos.
                matches = re.finditer(r'\b(\d{1,3})\s*[\/\\]\s*(\d{1,4})\b', texto_upper)
                for m in matches:
                    num1 = int(m.group(1))
                    num2 = int(m.group(2))
                    # Si no parece una fecha (día/mes) y num1 es menor a 99, lo tomamos
                    if not (num1 <= 31 and num2 <= 12) and num1 <= 99:
                        pata = num1
                        cajas = num2
                        break

            # 3. Si de todas formas falló, que quede en 99 para que lo revises
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
