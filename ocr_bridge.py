import os
import re
import threading
from io import BytesIO
from PIL import Image
import numpy as np

# 🔥 1. LIMITAR HILOS A NIVEL DE SISTEMA
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
            texto_upper = texto_completo.upper()
            confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0.0

            # --- 🔥 LÓGICA CORREGIDA PARA PATA Y CAJAS 🔥 ---
            pata, cajas = None, None
            entrega = None

            # 1. Buscar el patrón central: "15/52" (Pata/Cajas)
            # Busca números de 1 a 3 dígitos, una barra, y números de 1 a 4 dígitos.
            # Ej: 15/52, 4/120, 01/50
            match_central = re.search(r'\b(\d{1,3})\s*/\s*(\d{1,4})\b', texto_upper)
            
            if match_central:
                pata = int(match_central.group(1))
                cajas = int(match_central.group(2))
            else:
                # Si el OCR falló con la barra, intentar con un espacio (ej: "15 52")
                match_espacio = re.search(r'\b(\d{1,2})\s+(\d{1,4})\b', texto_upper)
                if match_espacio:
                    pata = int(match_espacio.group(1))
                    cajas = int(match_espacio.group(2))

            # 2. Buscar el N° de Entrega (7 u 8 dígitos, ej: 8054669)
            match_entrega = re.search(r'\b(\d{7,8})\b', texto_upper)
            if match_entrega:
                entrega = match_entrega.group(1)

            # 3. Si aún no hay pata, mandar a 99. Si no hay cajas, poner 0.
            if pata is None:
                pata = 99 
            if cajas is None:
                cajas = 0

            resultados.append({
                "archivo": nombre,
                "pata": pata,
                "total_cajas": cajas,
                "nro_entrega": entrega,
                "texto_crudo": texto_completo,
                "confianza": round(confianza_promedio, 3)
            })

        except Exception as e:
            resultados.append({
                "archivo": nombre,
                "pata": None,
                "total_cajas": None,
                "nro_entrega": None,
                "texto_crudo": f"ERROR PROCESANDO: {e}",
                "confianza": 0.0
            })

    return resultados
