from pathlib import Path

BASE_DIR = Path(__file__).parent
ENTRADA_DIR = BASE_DIR / "entrada"
SALIDA_DIR = BASE_DIR / "salida"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

LOGO_PATH = ASSETS_DIR / "logo.png"
LOGO2_PATH = ASSETS_DIR / "logo2.png"
ULTIMO_INFORME_JSON = TEMP_DIR / "ultimo_informe.json"

HEADER_HTML = BASE_DIR / "header.html"
FOOTER_HTML = BASE_DIR / "footer.html"

EXTENSIONES_FOTOS = {".jpg", ".jpeg", ".png", ".webp"}
ANCHO_MAX_FOTO = 800
CALIDAD_JPEG = 80
PREFIJO_PDF = "INFORME"

for d in [ENTRADA_DIR, SALIDA_DIR, ASSETS_DIR, LOGS_DIR, TEMP_DIR]:
    d.mkdir(exist_ok=True)