"""
F7 · Carga transaccional a SQLite (responsable: Nono).

ESTRATEGIA DE IDEMPOTENCIA (snapshot por ejecución)
    El contenido de `transacciones_limpias`, `cuarentena_errores` y `catalogo_productos` es SIEMPRE el resultado
    de la última ejecución COMPLETADA. Se logra borrando y volviendo a insertar dentro de UNA sola transacción:
    ejecutar el pipeline N veces sobre los mismos datos deja las mismas filas (sin duplicados) y una fila más en
    `ejecuciones` (el historial). Si algo falla a mitad de la carga, `rollback()` restaura el estado anterior:
    nunca hay filas parciales ni limpias sin su cuarentena. Las llaves (PK de id_transaccion, UNIQUE de
    origen+fila, UNIQUE de lote+origen+fila) son la red de seguridad si algún día se desactiva el reemplazo.
    Con `reemplazar=False` el lote se AGREGA: una transacción ya existente provoca violación de PK → rollback.

ERRORES
    `ErrorCarga` = falla GLOBAL de persistencia (interrumpe la ejecución, la BD queda como estaba).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DDL = Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")
TABLAS = ("ejecuciones", "catalogo_productos", "transacciones_limpias", "cuarentena_errores")


class ErrorCarga(Exception):
    """La carga no pudo completarse; la transacción se revirtió (rollback)."""


def abrir_conexion(ruta_bd: str | Path) -> sqlite3.Connection:
    """Conexión en modo manual de transacciones (BEGIN/COMMIT explícitos) y con llaves foráneas activas."""
    if str(ruta_bd) != ":memory:":
        Path(ruta_bd).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta_bd), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def crear_tablas(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)


def _insertar(conn: sqlite3.Connection, tabla: str, filas: list[dict]) -> int:
    """INSERT parametrizado (nunca se concatenan valores en el SQL: evita inyección)."""
    if not filas:
        return 0
    cols = list(filas[0].keys())
    sql = f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    conn.executemany(sql, [tuple(f[c] for c in cols) for f in filas])
    return len(filas)


def _upsert_catalogo(conn: sqlite3.Connection, filas: list[dict]) -> int:
    """El catálogo es referencia maestra: se actualiza por llave (no falla si el modo es «agregar»)."""
    sql = ("INSERT INTO catalogo_productos (id_producto, nombre_producto, categoria, precio_base_mxn, stock_minimo, proveedor) "
           "VALUES (:id_producto, :nombre_producto, :categoria, :precio_base_mxn, :stock_minimo, :proveedor) "
           "ON CONFLICT(id_producto) DO UPDATE SET nombre_producto=excluded.nombre_producto, "
           "categoria=excluded.categoria, precio_base_mxn=excluded.precio_base_mxn, stock_minimo=excluded.stock_minimo, "
           "proveedor=excluded.proveedor")
    conn.executemany(sql, filas)
    return len(filas)


def filas_catalogo(catalogo) -> list[dict]:
    out = []
    for r in catalogo.to_dict(orient="records"):
        out.append({"id_producto": str(r["id_producto"]).strip().upper(), "nombre_producto": r["nombre_producto"],
                    "categoria": r["categoria"], "precio_base_mxn": float(r["precio_base_mxn"]),
                    "stock_minimo": None if r.get("stock_minimo") is None else int(r["stock_minimo"]),
                    "proveedor": r.get("proveedor")})
    return out


def cargar_lote(conn: sqlite3.Connection, ejecucion: dict, validos: list[dict], cuarentena: list[dict],
                catalogo: list[dict], reemplazar: bool = True) -> dict:
    """Carga atómica: ejecución + catálogo + limpias + cuarentena en UNA transacción.

    `ejecucion` = {lote_id, inicio, huellas_entrada, entorno, filas_entrada}. Devuelve los conteos confirmados.
    """
    lote_id = ejecucion["lote_id"]
    fecha_carga = datetime.now().isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if reemplazar:      # orden inverso a las dependencias (hijas primero)
            conn.execute("DELETE FROM cuarentena_errores")
            conn.execute("DELETE FROM transacciones_limpias")
            conn.execute("DELETE FROM catalogo_productos")
        conn.execute(
            "INSERT INTO ejecuciones (lote_id, inicio, fin, estado, filas_entrada, filas_limpias, filas_cuarentena, "
            "huellas_entrada, entorno) VALUES (?, ?, ?, 'COMPLETADO', ?, ?, ?, ?, ?)",
            (lote_id, ejecucion["inicio"], fecha_carga, ejecucion["filas_entrada"], len(validos), len(cuarentena),
             json.dumps(ejecucion.get("huellas_entrada"), ensure_ascii=False),
             json.dumps(ejecucion.get("entorno"), ensure_ascii=False)))
        n_cat = _upsert_catalogo(conn, catalogo)
        n_ok = _insertar(conn, "transacciones_limpias",
                         [{**v, "lote_id": lote_id, "fecha_carga": fecha_carga} for v in validos])
        n_qz = _insertar(conn, "cuarentena_errores", cuarentena)
        conn.commit()
        return {"lote_id": lote_id, "estado": "COMMIT", "catalogo": n_cat, "limpias": n_ok, "cuarentena": n_qz}
    except Exception as e:  # noqa: BLE001 — cualquier fallo a mitad de la transacción debe revertirla
        conn.rollback()
        log.error("Carga del lote %s revertida (rollback): %s: %s", lote_id, type(e).__name__, e)
        raise ErrorCarga(f"Carga revertida (rollback) del lote {lote_id}: {type(e).__name__}: {e}") from e


def registrar_fallo(conn: sqlite3.Connection, lote_id: str, inicio: str, etapa: str, error: str,
                    huellas: dict | None = None, entorno: dict | None = None, filas_entrada: int | None = None) -> bool:
    """Deja constancia de una ejecución FALLIDA en el historial (no toca los datos). True si se pudo escribir."""
    try:
        crear_tablas(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO ejecuciones (lote_id, inicio, fin, estado, filas_entrada, huellas_entrada, entorno, "
            "etapa_fallida, error) VALUES (?, ?, ?, 'FALLIDO', ?, ?, ?, ?, ?)",
            (lote_id, inicio, datetime.now().isoformat(timespec="seconds"), filas_entrada,
             json.dumps(huellas, ensure_ascii=False), json.dumps(entorno, ensure_ascii=False), etapa, error[:2000]))
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        log.error("No se pudo registrar la ejecución fallida %s en la BD: %s", lote_id, e)
        return False


def resumen_bd(conn: sqlite3.Connection) -> dict:
    """Conteos, verificaciones de integridad y DDL real: evidencia de la carga."""
    conteos = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS}
    return {
        "conteos": conteos,
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_check": [tuple(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()],
        "tablas": {t: [{"columna": c["name"], "tipo": c["type"], "no_nulo": bool(c["notnull"]), "pk": bool(c["pk"])}
                       for c in conn.execute(f"PRAGMA table_info({t})")] for t in TABLAS},
        "indices": [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' "
                                                    "AND name NOT LIKE 'sqlite_%' ORDER BY name")],
        "sqlite_version": sqlite3.sqlite_version,
    }
