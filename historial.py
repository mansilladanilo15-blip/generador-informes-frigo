"""
historial.py
------------
Base de datos SQLite para guardar todos los informes generados.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

import config


DB_PATH = config.TEMP_DIR / "historial.db"


def init_db():
    """Crea la tabla si no existe."""
    config.TEMP_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS informes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_creacion TEXT NOT NULL,
            nro_pedido TEXT,
            tipo_informe TEXT,
            cliente TEXT,
            archivo_pdf TEXT,
            datos_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def guardar_informe(datos: dict, nombre_pdf: str):
    """Guarda un informe en la base de datos."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO informes
        (fecha_creacion, nro_pedido, tipo_informe, cliente, archivo_pdf, datos_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        datos.get("nro_pedido", ""),
        datos.get("tipo_informe", ""),
        datos.get("cliente", ""),
        nombre_pdf,
        json.dumps(datos, ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def obtener_todos(limite=50):
    """Devuelve todos los informes, más recientes primero."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fecha_creacion, nro_pedido, tipo_informe, cliente, archivo_pdf
        FROM informes
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))
    filas = [dict(f) for f in cursor.fetchall()]
    conn.close()
    return filas


def obtener_ultimo():
    """Devuelve el último informe guardado (dict con todos los datos)."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT datos_json FROM informes ORDER BY id DESC LIMIT 1
    """)
    fila = cursor.fetchone()
    conn.close()
    if fila:
        return json.loads(fila["datos_json"])
    return None


def obtener_por_id(informe_id):
    """Devuelve los datos de un informe específico."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT datos_json FROM informes WHERE id = ?
    """, (informe_id,))
    fila = cursor.fetchone()
    conn.close()
    if fila:
        return json.loads(fila["datos_json"])
    return None


def contar():
    """Cuenta cuántos informes hay."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM informes")
    n = cursor.fetchone()[0]
    conn.close()
    return n