# -*- mode: python ; coding: utf-8 -*-
import os
import streamlit
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

# 1. Obtener la ruta de Streamlit
streamlit_dir = os.path.dirname(streamlit.__file__)
static_dir = os.path.join(streamlit_dir, 'static')
runtime_dir = os.path.join(streamlit_dir, 'runtime')

datas = [
    # Tus archivos
    ('app.py', '.'),
    ('generador.py', '.'),
    ('config.py', '.'),
    ('historial.py', '.'),
    ('ocr_bridge.py', '.'),
    ('ocr_runner.py', '.'),
    ('plantilla.html', '.'),
    ('header.html', '.'),
    ('footer.html', '.'),
    ('assets', 'assets'),
    ('temp', 'temp'),
    
    # 🚨 AQUÍ ESTÁ LA CLAVE: Incluir la carpeta de wkhtmltopdf
    # Asegúrate de que el nombre 'wkhtmltox' coincida con la carpeta que copiaste
    ('wkhtmltox', 'wkhtmltox'),
    
    # Archivos de Streamlit
    (static_dir, 'streamlit/static'),
    (runtime_dir, 'streamlit/runtime'),
]

# 2. Metadatos de Streamlit
datas += copy_metadata('streamlit')
datas += copy_metadata('altair')
datas += copy_metadata('pydeck')

# 3. Forzar la inclusión de pdfkit y sus dependencias
hiddenimports = ['pdfkit']
hiddenimports += collect_submodules('streamlit')
hiddenimports += collect_submodules('altair')
hiddenimports += collect_submodules('pydeck')

a = Analysis(
    ['lanzador.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeneradorInformes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeneradorInformes',
)