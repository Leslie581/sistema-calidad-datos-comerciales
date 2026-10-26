"""Pruebas de SQLite: commit, rollback, idempotencia, restricciones de integridad e inyección SQL (etapa de Nono)."""
from __future__ import annotations

import json
import sqlite3

import pytest

from src.persistencia import carga
from src.persistencia.carga import (ErrorCarga, abrir_conexion, cargar_lote, crear_tablas, registrar_fallo, resumen_bd)
from src.validacion.cuarentena import clasificar_registro
from tests.ayudas_nono import CATALOGO_MINIMO, HOY, fila_valida

AHORA = "2026-10-25T12:00:00"


def valido(n: int, canal: str = "FISICA", **cambios) -> dict:
    pref = "POS-2026-{:04d}" if canal == "FISICA" else "WEB-{:05d}"
    estado, reg = clasificar_registro(fila_valida(canal, id_transaccion=pref.format(n), id_fila_origen=n, **cambios),
                                      "L", AHORA, HOY)
    assert estado == "VALIDO", reg
    return reg


def rechazado(n: int) -> dict:
    estado, reg = clasificar_registro(fila_valida(id_transaccion=f"POS-2026-{n:04d}", id_fila_origen=n, en_catalogo=False),
                                      "L", AHORA, HOY)
    assert estado == "RECHAZADO"
    return reg


def ejecucion(lote="L1", n=0) -> dict:
    return {"lote_id": lote, "inicio": AHORA, "filas_entrada": n, "huellas_entrada": {"a.csv": "x"}, "entorno": {"python": "3"}}


def lote(conn, lote_id, validos, cuarentena, **kw):
    for r in validos:
        r["lote_id"] = lote_id
    for r in cuarentena:
        r["lote_id"] = lote_id
    return cargar_lote(conn, ejecucion(lote_id, len(validos) + len(cuarentena)), validos, cuarentena, CATALOGO_MINIMO, **kw)


def n(conn, tabla):
    return conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


@pytest.fixture
def conn(tmp_path):
    c = abrir_conexion(tmp_path / "t.db")
    crear_tablas(c)
    yield c
    c.close()


# ----------------------------------------------------------------------------- commit
def test_commit_puebla_las_cuatro_tablas(conn):
    r = lote(conn, "L1", [valido(1), valido(2, "ONLINE")], [rechazado(3)])
    assert r["estado"] == "COMMIT" and (r["limpias"], r["cuarentena"], r["catalogo"]) == (2, 1, 1)
    assert [n(conn, t) for t in ("transacciones_limpias", "cuarentena_errores", "catalogo_productos", "ejecuciones")] == [2, 1, 1, 1]
    e = conn.execute("SELECT * FROM ejecuciones").fetchone()
    assert (e["estado"], e["filas_entrada"], e["filas_limpias"], e["filas_cuarentena"]) == ("COMPLETADO", 3, 2, 1)
    assert json.loads(e["huellas_entrada"]) == {"a.csv": "x"}


def test_lectura_de_vuelta_conserva_original_y_tratado(conn):
    lote(conn, "L1", [valido(1, cantidad_origen=500.0, cantidad=500.0, cantidad_cap=8.0, precio_unitario_mxn=100.0,
                              monto_total_mxn=50000.0, monto_total_origen=50000.0, monto_total_mxn_cap=800.0)], [])
    r = conn.execute("SELECT * FROM transacciones_limpias").fetchone()
    assert (r["cantidad_origen"], r["cantidad"], r["cantidad_cap"]) == (500.0, 500, 8)
    assert (r["monto_total_origen"], r["monto_total_mxn"], r["monto_total_mxn_cap"]) == (50000.0, 50000.0, 800.0)
    assert r["fecha_cruda"] == "13-09-2026" and r["fecha_venta"] == "2026-09-13" and r["moneda"] == "MXN"


def test_cuarentena_guarda_detalle_y_original(conn):
    lote(conn, "L1", [], [rechazado(7)])
    q = conn.execute("SELECT * FROM cuarentena_errores").fetchone()
    assert q["codigos_error"] == "PRODUCTO_HUERFANO" and q["id_registro"] == "POS-2026-0007"
    assert json.loads(q["detalle_error"])[0]["codigo"] == "PRODUCTO_HUERFANO"
    assert json.loads(q["registro_original"])["id"] == "POS-2026-0007"


# ----------------------------------------------------------------------------- rollback
def test_rollback_si_falla_la_segunda_tabla_deja_la_bd_como_estaba(conn, monkeypatch):
    lote(conn, "L1", [valido(1), valido(2)], [rechazado(3)])
    antes = [n(conn, t) for t in ("transacciones_limpias", "cuarentena_errores", "catalogo_productos", "ejecuciones")]
    original = carga._insertar

    def falla_en_cuarentena(c, tabla, filas):
        if tabla == "cuarentena_errores":
            raise sqlite3.OperationalError("disco lleno (simulado)")
        return original(c, tabla, filas)

    monkeypatch.setattr(carga, "_insertar", falla_en_cuarentena)
    with pytest.raises(ErrorCarga, match=r"Carga revertida \(rollback\)"):
        lote(conn, "L2", [valido(10), valido(11), valido(12)], [rechazado(13)])
    assert [n(conn, t) for t in ("transacciones_limpias", "cuarentena_errores", "catalogo_productos", "ejecuciones")] == antes
    assert conn.execute("SELECT COUNT(*) FROM transacciones_limpias WHERE id_transaccion='POS-2026-0010'").fetchone()[0] == 0
    assert conn.in_transaction is False


def test_rollback_por_violacion_de_llave_primaria_restaura_el_lote_anterior(conn):
    lote(conn, "L1", [valido(1)], [])
    with pytest.raises(ErrorCarga):
        lote(conn, "L2", [valido(5), valido(5)], [])              # mismo id_transaccion dos veces
    assert [r[0] for r in conn.execute("SELECT id_transaccion FROM transacciones_limpias")] == ["POS-2026-0001"]
    assert [r[0] for r in conn.execute("SELECT lote_id FROM ejecuciones")] == ["L1"]


def test_la_conexion_sigue_usable_tras_un_rollback(conn):
    with pytest.raises(ErrorCarga):
        lote(conn, "L1", [valido(5), valido(5)], [])
    assert lote(conn, "L2", [valido(6)], [])["estado"] == "COMMIT"


def test_error_no_sqlite_a_mitad_tambien_revierte(conn, monkeypatch):
    lote(conn, "L1", [valido(1)], [])

    def explota(c, tabla, filas):
        raise KeyError("columna_inexistente")

    monkeypatch.setattr(carga, "_insertar", explota)
    with pytest.raises(ErrorCarga, match="KeyError"):
        lote(conn, "L2", [valido(2)], [])
    assert n(conn, "transacciones_limpias") == 1


# ----------------------------------------------------------------------------- idempotencia
def test_recarga_repetida_no_duplica_y_acumula_historial(conn):
    for i in range(3):
        lote(conn, f"L{i}", [valido(1), valido(2)], [rechazado(3)])
    assert (n(conn, "transacciones_limpias"), n(conn, "cuarentena_errores"), n(conn, "catalogo_productos")) == (2, 1, 1)
    assert n(conn, "ejecuciones") == 3
    assert conn.execute("SELECT DISTINCT lote_id FROM transacciones_limpias").fetchall()[0][0] == "L2"


def test_modo_agregar_suma_filas_nuevas_y_rechaza_repetidas(conn):
    lote(conn, "L1", [valido(1)], [])
    assert lote(conn, "L2", [valido(2)], [], reemplazar=False)["estado"] == "COMMIT"
    assert n(conn, "transacciones_limpias") == 2 and n(conn, "ejecuciones") == 2
    with pytest.raises(ErrorCarga):                              # mismo POS-2026-0001 → PK repetida → rollback
        lote(conn, "L3", [valido(1)], [], reemplazar=False)
    assert n(conn, "transacciones_limpias") == 2 and n(conn, "ejecuciones") == 2


# ----------------------------------------------------------------------------- restricciones de la base (defensa en profundidad)
def insertar_directo(conn, fila):
    conn.execute("INSERT INTO ejecuciones VALUES ('LX', 'a', 'b', 'COMPLETADO', 1, 1, 0, NULL, NULL, NULL, NULL) "
                 "ON CONFLICT DO NOTHING")
    conn.execute("INSERT OR IGNORE INTO catalogo_productos VALUES ('PROD-010','x','y',100,1,'p')")
    fila = {**fila, "lote_id": "LX", "fecha_carga": "2026-10-25"}
    cols = list(fila)
    conn.execute(f"INSERT INTO transacciones_limpias ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 [fila[c] for c in cols])


def test_control_la_fila_base_si_se_inserta_directo(conn):
    """Sin esto, las pruebas de abajo podrían «pasar» por un motivo ajeno (p. ej. una llave foránea)."""
    fila = valido(1)
    fila.pop("lote_id", None)
    insertar_directo(conn, fila)
    assert n(conn, "transacciones_limpias") == 1


@pytest.mark.parametrize("cambio", [
    {"cantidad": 0}, {"cantidad_cap": -1}, {"moneda_original": "EUR"}, {"moneda": "USD"}, {"fecha_venta": "2026-02-31"},
    {"fecha_venta": "13-09-2026"}, {"monto_minmax": 1.2}, {"segmento_importe": "Premium"}, {"monto_total_mxn": 0},
    {"precio_unitario_mxn": -1}, {"id_transaccion": "X-1"}, {"es_outlier_monto": 2}, {"origen": "TIENDA"},
    {"estado_pedido": "ENVIADO", "origen": "ONLINE", "id_transaccion": "WEB-00001"},
    {"estado_pedido": "COMPLETADO"},                                              # FISICA con estado
    {"id_producto": "PROD-404"},                                                  # no existe en el catálogo → FK
    {"metodo_pago": None}, {"registro_original": None},
])
def test_la_base_rechaza_datos_invalidos_aunque_no_pasen_por_pydantic(conn, cambio):
    fila = {**valido(1), **cambio}
    fila.pop("lote_id", None)
    with pytest.raises(sqlite3.IntegrityError):
        insertar_directo(conn, fila)


def test_la_base_rechaza_cuarentena_sin_motivo(conn):
    lote(conn, "L1", [], [])
    for motivo in ("", "   "):
        q = {**rechazado(1), "motivo_rechazo_cuarentena": motivo, "lote_id": "L1"}
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO cuarentena_errores (lote_id, id_registro, origen, id_fila_origen, etapa_deteccion, "
                         "codigos_error, num_motivos, motivo_rechazo_cuarentena, detalle_error, registro_original, "
                         "fecha_cuarentena) VALUES (:lote_id, :id_registro, :origen, :id_fila_origen, :etapa_deteccion, "
                         ":codigos_error, :num_motivos, :motivo_rechazo_cuarentena, :detalle_error, :registro_original, "
                         ":fecha_cuarentena)", q)


def test_una_transaccion_se_cuenta_una_vez_por_ejecucion(conn):
    q = rechazado(1)
    with pytest.raises(ErrorCarga):
        lote(conn, "L1", [], [q, dict(q)])                         # misma fila de origen dos veces
    assert n(conn, "cuarentena_errores") == 0


def test_integridad_referencial_activa_por_conexion(tmp_path):
    c = abrir_conexion(tmp_path / "x.db")
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    c.close()


# ----------------------------------------------------------------------------- inyección SQL
def test_consultas_parametrizadas_tratan_el_id_malicioso_como_texto(conn):
    malicioso = "'; DROP TABLE transacciones_limpias;--"
    estado, q = clasificar_registro(fila_valida(id_transaccion=malicioso), "L", AHORA, HOY)
    assert estado == "RECHAZADO" and q["id_registro"] == malicioso
    lote(conn, "L1", [valido(1)], [q])
    assert n(conn, "transacciones_limpias") == 1
    assert conn.execute("SELECT id_registro FROM cuarentena_errores").fetchone()[0] == malicioso


# ----------------------------------------------------------------------------- historial y resumen
def test_registrar_fallo_deja_historial_sin_tocar_los_datos(conn):
    lote(conn, "L1", [valido(1)], [])
    assert registrar_fallo(conn, "L2", AHORA, "1. Extracción", "ErrorExtraccion: JSON roto", {"a": "b"}, {"python": "3"}, None)
    e = conn.execute("SELECT estado, etapa_fallida, error FROM ejecuciones WHERE lote_id='L2'").fetchone()
    assert tuple(e) == ("FALLIDO", "1. Extracción", "ErrorExtraccion: JSON roto")
    assert n(conn, "transacciones_limpias") == 1


def test_no_se_puede_registrar_una_ejecucion_completada_que_no_cuadra(conn):
    with pytest.raises(sqlite3.IntegrityError):                    # R1.4 también como CHECK en la tabla
        conn.execute("INSERT INTO ejecuciones VALUES ('LM','a','b','COMPLETADO',10,5,4,NULL,NULL,NULL,NULL)")


def test_resumen_bd(conn):
    lote(conn, "L1", [valido(1)], [rechazado(2)])
    r = resumen_bd(conn)
    assert r["integrity_check"] == "ok" and r["foreign_key_check"] == []
    assert r["conteos"] == {"ejecuciones": 1, "catalogo_productos": 1, "transacciones_limpias": 1, "cuarentena_errores": 1}
    assert any(c["columna"] == "id_transaccion" and c["pk"] for c in r["tablas"]["transacciones_limpias"])
    assert "ix_cuarentena_codigos" in r["indices"]
