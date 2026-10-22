import os
import sys
import json
import re
from pathlib import Path

# Silenciar mensajes
os.environ["FLAGS_call_stack_level"] = "0"
os.environ["GLOG_minloglevel"] = "3"
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

from paddleocr import PaddleOCR

def extraer_datos_cartel(ocr, ruta_imagen):
    try:
        resultado = ocr.ocr(str(ruta_imagen), cls=True)
    except Exception:
        return {"pata": None, "total_cajas": None, "nro_entrega": None, "fecha": None, "texto_crudo": "", "confianza": 0.0}

    textos, confianzas = [], []
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

    pata, cajas = None, None
    candidatos = []

    if resultado and resultado[0]:
        for linea in resultado[0]:
            try:
                texto = linea[1][0]
                conf = linea[1][1]
            except (IndexError, TypeError):
                continue

            # Buscar formato X/Y
            match = re.search(r'(\d{1,3})\s*[/\s]\s*(\d{1,4})', texto)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2))
                es_fecha = (num1 <= 31 and num2 <= 12) # Descartar fechas
                if not es_fecha:
                    candidatos.append({"num1": num1, "num2": num2, "confianza": conf})

    if candidatos:
        buenos = [c for c in candidatos if c["confianza"] >= 0.80]
        mejor = max(buenos, key=lambda c: c["confianza"]) if buenos else max(candidatos, key=lambda c: c["confianza"])
        pata = mejor["num1"]
        cajas = mejor["num2"]

    match_entrega = re.search(r'\b(\d{7,8})\b', texto_upper)
    entrega = match_entrega.group(1) if match_entrega else None

    match_fecha = re.search(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b', texto_upper)
    fecha = match_fecha.group(1) if match_fecha else None

    return {
        "pata": pata, "total_cajas": cajas, "nro_entrega": entrega,
        "fecha": fecha, "texto_crudo": texto_completo, "confianza": round(confianza_promedio, 3),
    }


def main():
    if len(sys.argv) < 3:
        sys.exit(1)

    ruta_json_salida = Path(sys.argv[1])
    argumentos_fotos = sys.argv[2:]

    pares = []
    for arg in argumentos_fotos:
        if "|" in arg:
            nombre, ruta = arg.split("|", 1)
            ruta_path = Path(ruta)
            if ruta_path.exists():
                pares.append((nombre, ruta_path))

    if not pares:
        sys.exit(1)

    ocr = PaddleOCR(use_angle_cls=True, lang='es', use_gpu=False, show_log=False)

    resultados = []
    for nombre_original, ruta in pares:
        datos = extraer_datos_cartel(ocr, ruta)
        datos["archivo"] = nombre_original
        resultados.append(datos)

    with open(ruta_json_salida, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False)


if __name__ == "__main__":
    main()