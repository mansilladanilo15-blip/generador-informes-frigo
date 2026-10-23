import os
import re
import threading
from io import BytesIO
from PIL import Image
import numpy as np

# 🔥 1. LIMITAR HILOS A NIVEL DE SISTEMA (Evita que Streamlit bloquee la app)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

try:
    from paddleocr import PaddleOCR
    import paddle

    # Forzamos CPU
    paddle.set_device('cpu')

    # Variable global para el modelo (se inicializa por hilo para evitar crashes en Streamlit)
    _ocr_local = threading.local()

    def obtener_ocr():
        """Obtiene una instancia de OCR para el hilo actual."""
        if not hasattr(_ocr_local, "model"):
            # 🔥 2. "DIETA" DE RECURSOS PARA PADDLEOCR
            _ocr_local.model = PaddleOCR(
                lang='en',
                use_textline_orientation=True,
                enable_mkldnn=False,  # Evita el crash std::exception en CPU
                cpu_threads=1,        # 🔥 Solo usa 1 núcleo de CPU
                rec_batch_num=1,      # 🔥 Procesa el texto en lotes de 1
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
            # Obtener modelo del hilo actual
            ocr_model = obtener_ocr()

            # Convertir bytes a imagen
            img = Image.open(BytesIO(contenido_bytes)).convert("RGB")

            # 🔥 3. REDUCIR EL TAMAÑO DE LA IMAGEN (Ahorra muchísima CPU)
            max_lado = 1000  # Antes 1600, ahora 1000
            if max(img.width, img.height) > max_lado:
                ratio = max_lado / max(img.width, img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)))

            img_array = np.array(img)

            # Usar .predict() en lugar de .ocr() para PaddleOCR 3.x
            resultado = ocr_model.predict(img_array)

            textos = []
            confianzas = []

            # Extraer resultados según el formato de PaddleOCR 3.x
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

            # --- BUSCAR PATAS Y CAJAS ---
            pata, cajas = None, None
            candidatos = []

            for i, texto in enumerate(textos):
                conf = confianzas[i] if i < len(confianzas) else 0.0
                match = re.search(r'(\d{1,3})\s*[/\s]\s*(\d{1,4})', texto)
                if match:
                    num1 = int(match.group(1))
                    num2 = int(match.group(2))
                    es_fecha = (num1 <= 31 and num2 <= 12)
                    if not es_fecha:
                        candidatos.append({"num1": num1, "num2": num2, "confianza": conf})

            if candidatos:
                buenos = [c for c in candidatos if c["confianza"] >= 0.80]
                mejor = max(buenos, key=lambda c: c["confianza"]) if buenos else max(candidatos, key=lambda c: c["confianza"])
                pata = mejor["num1"]
                cajas = mejor["num2"]

            # Buscar otros datos
            match_entrega = re.search(r'\b(\d{7,8})\b', texto_upper)
            entrega = match_entrega.group(1) if match_entrega else None

            match_fecha = re.search(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b', texto_upper)
            fecha = match_fecha.group(1) if match_fecha else None

            resultados.append({
                "archivo": nombre,
                "pata": pata,
                "total_cajas": cajas,
                "nro_entrega": entrega,
                "fecha": fecha,
                "texto_crudo": texto_completo,
                "confianza": round(confianza_promedio, 3)
            })

        except Exception as e:
            resultados.append({
                "archivo": nombre,
                "pata": None,
                "total_cajas": None,
                "nro_entrega": None,
                "fecha": None,
                "texto_crudo": f"ERROR PROCESANDO: {e}",
                "confianza": 0.0
            })

    return resultados
