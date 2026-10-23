import re
import os
import sys
from io import BytesIO
from PIL import Image
import numpy as np

# 🔥 IMPORTAMOS PADDLE OCR Y PADDLE PARA CONTROLAR EL DISPOSITIVO
try:
    from paddleocr import PaddleOCR
    import paddle

    # Forzamos CPU (esto ya lo tenías y está bien)
    paddle.set_device('cpu')

    ocr_model = PaddleOCR(
        use_angle_cls=True,  # Aún se acepta en 3.x (aunque puede mostrar un warning)
        lang='en'
        # ❌ ELIMINADO: show_log=False
    )
    error_ocr = None
except Exception as e:
    ocr_model = None
    error_ocr = str(e)


def analizar_fotos(fotos_bytes_list):
    """
    Procesa una lista de fotos directamente en la nube.
    fotos_bytes_list: [(nombre, bytes), ...]
    """
    if not ocr_model:
        raise Exception(f"El modelo OCR no está disponible. Detalle: {error_ocr}")

    resultados = []

    for nombre, contenido_bytes in fotos_bytes_list:
        try:
            # Convertimos los bytes a una imagen compatible con PaddleOCR
            img = Image.open(BytesIO(contenido_bytes)).convert("RGB")

            # Reducimos el tamaño si es muy grande (ahorra RAM y acelera)
            max_lado = 1600
            if max(img.width, img.height) > max_lado:
                ratio = max_lado / max(img.width, img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)))

            img_array = np.array(img)

            # Ejecutamos el OCR (en 3.x, .ocr sigue funcionando, aunque .predict es lo nuevo)
            resultado = ocr_model.ocr(img_array, cls=True)

            textos = []
            confianzas = []
            if resultado and resultado[0]:
                for linea in resultado[0]:
                    try:
                        textos.append(linea[1][0])
                        confianzas.append(linea[1][1])
                    except (IndexError, TypeError):
                        continue

            texto_completo = " ".join(textos)
            texto_upper = texto_completo.upper()
            confianza_promedio = sum(confianzas) / len(confianzas) if confianzas else 0.0

            # --- BUSCAR PATAS Y CAJAS (formato "X/Y" o "X Y") ---
            pata, cajas = None, None
            candidatos = []

            if resultado and resultado[0]:
                for linea in resultado[0]:
                    try:
                        texto = linea[1][0]
                        conf = linea[1][1]
                    except (IndexError, TypeError):
                        continue

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
