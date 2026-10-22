import json
import subprocess
import tempfile
import os
import sys
from pathlib import Path

import config

# Buscar la ruta al Python del OCR
if getattr(sys, 'frozen', False):
    base_exe = os.path.dirname(sys.executable)
    ruta_1 = os.path.join(base_exe, ".venv-ocr", "Scripts", "python.exe")
    ruta_2 = os.path.join(os.path.dirname(os.path.dirname(base_exe)), ".venv-ocr", "Scripts", "python.exe")
    
    if os.path.exists(ruta_1):
        PYTHON_OCR = Path(ruta_1)
    elif os.path.exists(ruta_2):
        PYTHON_OCR = Path(ruta_2)
    else:
        PYTHON_OCR = Path(r"C:\Users\dmansillan\OneDrive - Australis Mar SA\Escritorio\generador_informes\.venv-ocr\Scripts\python.exe")
else:
    PYTHON_OCR = config.BASE_DIR / ".venv-ocr" / "Scripts" / "python.exe"

if getattr(sys, 'frozen', False):
    OCR_RUNNER = Path(sys._MEIPASS) / "ocr_runner.py"
else:
    OCR_RUNNER = config.BASE_DIR / "ocr_runner.py"


def analizar_fotos(fotos_bytes_list):
    if not fotos_bytes_list:
        return []

    if not PYTHON_OCR.exists():
        raise FileNotFoundError(f"No se encontró el Python del entorno OCR en:\n{PYTHON_OCR}")
    if not OCR_RUNNER.exists():
        raise FileNotFoundError(f"No se encontró ocr_runner.py en:\n{OCR_RUNNER}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        ruta_json = tmpdir / "resultado.json"
        argumentos = [str(ruta_json)]

        for i, (nombre, contenido) in enumerate(fotos_bytes_list, 1):
            ext = Path(nombre).suffix or ".jpg"
            ruta_temp = tmpdir / f"foto_{i:03d}{ext}"
            ruta_temp.write_bytes(contenido)
            argumentos.append(f"{nombre}|{ruta_temp}")

        # Llamada directa al Python, sin shell y con entorno limpio
        cmd = [str(PYTHON_OCR), str(OCR_RUNNER)] + argumentos

        env_limpio = os.environ.copy()
        env_limpio.pop("PYTHONPATH", None)
        env_limpio.pop("PYTHONHOME", None)

        subprocess.run(
            cmd,
            capture_output=False,
            cwd=str(tmpdir),
            timeout=600,
            env=env_limpio
        )

        if not ruta_json.exists():
            raise RuntimeError("El OCR falló al procesar las imágenes (no se generó el JSON).")

        with open(ruta_json, "r", encoding="utf-8") as f:
            datos = json.load(f)

        return datos