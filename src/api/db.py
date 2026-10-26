"""Acceso de SOLO LECTURA a SQLite para la API. El navegador nunca toca la base; la API tampoco la modifica."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ErrorApi(Exception):
    """Error controlado con código estable (lo traduce el manejador global a JSON)."""

    def __init__(self, codigo: str, mensaje: str, estado: int = 400):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.estado = codigo, mensaje, estado


@contextmanager
def conectar(ruta_bd: Path):
    """Conexión `mode=ro` + `query_only`: aunque hubiera un bug, desde aquí no se puede escribir.

    Una transacción de lectura da una vista consistente aunque el pipeline esté reemplazando datos en ese momento
    (el pipeline carga todo en una sola transacción: se ve la carga anterior completa o la nueva completa).
    """
    ruta = Path(ruta_bd)
    if not ruta.is_file():
        raise ErrorApi("BD_NO_ENCONTRADA", "Todavía no existe la base de datos. Ejecuta el pipeline desde el Centro ETL.", 503)
    try:
        conn = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as e:
        raise ErrorApi("BD_NO_DISPONIBLE", f"No se pudo abrir la base de datos: {e}", 503) from e
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        conn.execute("BEGIN")
        yield conn
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            raise ErrorApi("BD_SIN_ESQUEMA", "La base existe pero no tiene las tablas del pipeline. Ejecuta el pipeline.", 503) from e
        raise ErrorApi("BD_ERROR", f"Error al consultar la base de datos: {e}", 503) from e
    finally:
        conn.close()


def filas(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def fila(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return None if r is None else dict(r)


def escalar(conn: sqlite3.Connection, sql: str, params=()):
    return conn.execute(sql, params).fetchone()[0]


def patron_like(texto: str) -> str:
    """Búsqueda «contiene» segura: escapa % _ \\ (se usa con ESCAPE '\\')."""
    return "%" + texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
