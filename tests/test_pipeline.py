"""Pipeline completo contra los TRES datasets OFICIALES (etapa de Nono): conteos, conservación, integridad y evidencias."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest

from src.config import HUELLAS_SHA256, RUTAS_FUENTES
from src.extraccion import ErrorExtraccion, calcular_sha256
from src.pipeline import ejecutar_pipeline, main
from tests.ayudas_nono import HOY
from tests.conftest import RAIZ


@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    d = tmp_path_factory.mktemp("pipeline_oficial")
    r = ejecutar_pipeline(ruta_bd=d / "calidad.db", dir_salida=d / "salida", hoy=HOY)
    return r, d


@pytest.fixture(scope="module")
def bd(corrida):
    r, d = corrida
    c = sqlite3.connect(str(d / "calidad.db"))
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def q(bd, sql, *p):
    return bd.execute(sql, p).fetchall()


# ----------------------------------------------------------------------------- conteos oficiales
def test_ejecucion_completada(corrida):
    r, _ = corrida
    assert r["estado"] == "COMPLETADO" and r["advertencias"] == []
    assert list(r["integridad_originales"].values()) == [True, True, True]


def test_entrada_620_mas_600(corrida):
    r, _ = corrida
    assert r["filas_por_origen"] == {"FISICA": 620, "ONLINE": 600} and r["filas_entrada"] == 1220


def test_conservacion_sin_perdidas_silenciosas(corrida, bd):
    r, _ = corrida
    n_ok = q(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0]
    n_qz = q(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0]
    assert n_ok + n_qz == 1220 == r["filas_entrada"]
    assert (n_ok, n_qz) == (r["validacion"]["validos"], r["validacion"]["cuarentena"])
    filas = {(x["origen"], x["id_fila_origen"]) for x in q(bd, "SELECT origen, id_fila_origen FROM transacciones_limpias")}
    filas |= {(x["origen"], x["id_fila_origen"]) for x in q(bd, "SELECT origen, id_fila_origen FROM cuarentena_errores")}
    assert filas == {("FISICA", i) for i in range(1, 621)} | {("ONLINE", i) for i in range(1, 601)}


def test_resultados_por_canal_coinciden_con_la_referencia_documental(bd):
    """Cifras que resultaron de aplicar las reglas (no se forzaron): coinciden con REGLAS_DE_NEGOCIO §13."""
    limpias = {x[0]: x[1] for x in q(bd, "SELECT origen, COUNT(*) FROM transacciones_limpias GROUP BY origen")}
    cuarentena = {x[0]: x[1] for x in q(bd, "SELECT origen, COUNT(*) FROM cuarentena_errores GROUP BY origen")}
    assert limpias == {"FISICA": 562, "ONLINE": 542} and cuarentena == {"FISICA": 58, "ONLINE": 58}


def test_motivos_de_cuarentena(corrida):
    r, _ = corrida
    p = r["validacion"]["por_codigo"]
    assert (p["DUPLICADO_EXACTO"], p["CANTIDAD_INVALIDA"], p["PRODUCTO_HUERFANO"], p["EMAIL_MALFORMADO"]) == (20, 11, 62, 28)
    assert p["MONTO_INVALIDO"] == 11
    assert set(p) == {"DUPLICADO_EXACTO", "CANTIDAD_INVALIDA", "MONTO_INVALIDO", "PRODUCTO_HUERFANO", "EMAIL_MALFORMADO"}
    assert r["validacion"]["errores_inesperados"] == 0


def test_registros_con_mas_de_un_motivo(bd):
    assert q(bd, "SELECT COUNT(*) FROM cuarentena_errores WHERE num_motivos > 1")[0][0] == 15
    triple = "CANTIDAD_INVALIDA;MONTO_INVALIDO;PRODUCTO_HUERFANO"
    assert q(bd, "SELECT COUNT(*) FROM cuarentena_errores WHERE codigos_error = ?", triple)[0][0] == 1


def test_ejemplos_de_la_guia_aceptados_y_rechazados(bd):
    for id_ in ("POS-2026-0002", "WEB-00002", "POS-2026-0005", "POS-2026-0075", "WEB-00508", "POS-2026-0031", "WEB-00040"):
        assert q(bd, "SELECT 1 FROM transacciones_limpias WHERE id_transaccion=?", id_), id_
    esperados = {"POS-2026-0216": "CANTIDAD_INVALIDA;MONTO_INVALIDO", "POS-2026-0035": "CANTIDAD_INVALIDA;MONTO_INVALIDO",
                 "POS-2026-0017": "PRODUCTO_HUERFANO", "WEB-00004": "EMAIL_MALFORMADO", "WEB-00001": "PRODUCTO_HUERFANO",
                 "WEB-00477": "EMAIL_MALFORMADO;PRODUCTO_HUERFANO",
                 "POS-2026-0493": "CANTIDAD_INVALIDA;MONTO_INVALIDO;PRODUCTO_HUERFANO"}
    for id_, codigos in esperados.items():
        got = {x[0] for x in q(bd, "SELECT codigos_error FROM cuarentena_errores WHERE id_registro=?", id_)}
        assert got == {codigos}, id_
    assert q(bd, "SELECT codigos_error FROM cuarentena_errores WHERE id_registro='POS-2026-0001'")[0][0] == "DUPLICADO_EXACTO"
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias WHERE id_transaccion='POS-2026-0001'")[0][0] == 1   # la 1.ª se conserva


# ----------------------------------------------------------------------------- calidad de las transacciones válidas
def test_validas_tienen_fecha_iso_moneda_mxn_e_importes_coherentes(bd):
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias WHERE fecha_venta NOT GLOB "
                 "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' OR date(fecha_venta) IS NOT fecha_venta")[0][0] == 0
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias WHERE moneda <> 'MXN'")[0][0] == 0
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias "
                 "WHERE ABS(ROUND(cantidad * precio_unitario_mxn, 2) - monto_total_mxn) > 0.01")[0][0] == 0
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias WHERE moneda_original='USD' AND tipo_cambio_aplicado <> 19.5")[0][0] == 0
    assert tuple(q(bd, "SELECT MIN(fecha_venta), MAX(fecha_venta) FROM transacciones_limpias")[0]) == ("2026-09-01", "2026-10-16")


def test_campos_de_transformacion_correctamente_calculados(corrida):
    v = corrida[0]["reporte"]["verificacion_validas"]
    assert v["minmax_difiere_del_recalculo_(>1e-6)"] == 0 and v["segmento_difiere_del_recalculo"] == 0
    assert (v["monto_minmax_min"], v["monto_minmax_max"]) == (0.0, 1.0)
    assert v["monto_incoherente_con_cantidad_x_precio"] == 0 and v["moneda_mxn"] == v["filas"] == 1104


def test_ejemplos_de_valores_originales_y_tratados(bd):
    r = q(bd, "SELECT * FROM transacciones_limpias WHERE id_transaccion='POS-2026-0031'")[0]
    assert (r["cantidad_origen"], r["cantidad"], r["cantidad_cap"]) == (500.0, 500, 8)
    assert r["monto_total_mxn"] > r["monto_total_mxn_cap"] and r["es_outlier_cantidad"] == 1
    r = q(bd, "SELECT * FROM transacciones_limpias WHERE id_transaccion='WEB-00508'")[0]
    assert (r["monto_total_origen"], r["monto_total_mxn"]) == (826360.8, 10329.51)
    assert "MONTO_RECALCULADO_INCONSISTENTE" in json.loads(r["correcciones"])
    r = q(bd, "SELECT * FROM transacciones_limpias WHERE id_transaccion='WEB-00002'")[0]
    assert (r["moneda_original"], r["precio_unitario_original"], r["precio_unitario_mxn"], r["moneda"]) == \
        ("USD", 169.59, 3307.01, "MXN")
    assert r["fecha_cruda"] == "2026-10-12T02:23:00" and r["fecha_venta"] == "2026-10-12"


def test_estados_cancelado_y_devuelto_se_conservan(bd):
    estados = {x[0] for x in q(bd, "SELECT DISTINCT estado_pedido FROM transacciones_limpias WHERE origen='ONLINE'")}
    assert estados == {"COMPLETADO", "PAGADO", "PENDIENTE", "CANCELADO", "DEVUELTO"}


# ----------------------------------------------------------------------------- integridad de la BD y de los originales
def test_integridad_de_la_base(corrida, bd):
    s = corrida[0]["sqlite"]
    assert s["integrity_check"] == "ok" and s["foreign_key_check"] == []
    assert s["conteos"] == {"ejecuciones": 1, "catalogo_productos": 50, "transacciones_limpias": 1104, "cuarentena_errores": 116}
    assert q(bd, "SELECT COUNT(*) FROM transacciones_limpias t LEFT JOIN catalogo_productos c USING(id_producto) "
                 "WHERE c.id_producto IS NULL")[0][0] == 0


def test_originales_intactos_por_sha256(corrida):
    for nombre, huella in HUELLAS_SHA256.items():
        assert calcular_sha256(RAIZ / "datos" / "crudos" / nombre) == huella
    assert corrida[0]["huellas_entrada"] == HUELLAS_SHA256


def test_ejecucion_repetida_es_idempotente(tmp_path):
    kw = dict(ruta_bd=tmp_path / "r.db", dir_salida=tmp_path / "s", hoy=HOY, generar_reportes=False)
    r1, r2 = ejecutar_pipeline(**kw), ejecutar_pipeline(**kw)
    assert r1["estado"] == r2["estado"] == "COMPLETADO" and r1["lote_id"] != r2["lote_id"]
    with closing(sqlite3.connect(str(tmp_path / "r.db"))) as c:
        conteos = [c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                   ("transacciones_limpias", "cuarentena_errores", "catalogo_productos", "ejecuciones")]
        assert conteos == [1104, 116, 50, 2]
        assert c.execute("SELECT DISTINCT lote_id FROM transacciones_limpias").fetchall() == [(r2["lote_id"],)]


# ----------------------------------------------------------------------------- evidencias
def test_se_generan_las_evidencias(corrida):
    _, d = corrida
    for nombre in ("01_resumen_validacion_pydantic.json", "02_conteos_conservacion.csv", "03_cuarentena_por_codigo.csv",
                   "04_ejemplos_aceptados.csv", "05_ejemplos_rechazados.csv", "06_resumen_sqlite.json",
                   "07_consultas_verificacion.txt", "08_metricas_pipeline.json", "09_comparacion_estimaciones.csv",
                   "10_verificacion_transacciones_validas.json", "graficas/cuarentena_por_motivo.png",
                   "graficas/conservacion_por_canal.png"):
        assert (d / "salida" / nombre).stat().st_size > 0, nombre
    assert len(list((d / "salida" / "logs").glob("pipeline_*.log"))) == 1
    assert len(list((d / "salida" / "bitacoras").glob("bitacora_*.json"))) == 1


def test_comparacion_con_estimaciones_solo_difiere_donde_se_explica(corrida):
    cmp = corrida[0]["reporte"]["comparacion_estimaciones"]
    difieren = [c for c in cmp if not c["coincide"]]
    assert [c["metrica"] for c in difieren] == ["Registros con más de un motivo"] and difieren[0]["nota"]


# ----------------------------------------------------------------------------- línea de comandos
def test_python_m_src_pipeline_funciona(tmp_path):
    p = subprocess.run([sys.executable, "-m", "src.pipeline", "--bd", str(tmp_path / "c.db"), "--salida", str(tmp_path / "s")],
                       cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "Estado: COMPLETADO" in p.stdout and "1220  →  limpias: 1104  +  cuarentena: 116" in p.stdout
    assert "Traceback" not in p.stdout + p.stderr


def test_fallo_global_en_la_cli_sale_con_1_y_sin_traceback(tmp_path, capsys):
    simulado = ErrorExtraccion("ventas_online.json no es un JSON válido: simulado")
    with mock.patch("src.pipeline.extraer_fuentes", side_effect=simulado):
        codigo = main(["--bd", str(tmp_path / "c.db"), "--salida", str(tmp_path / "s")])
    salida = capsys.readouterr().out
    assert codigo == 1 and "FALLIDO" in salida and "ErrorExtraccion" in salida and "Traceback" not in salida
    assert "1. Extracción" in salida


def test_huella_alterada_detiene_la_ejecucion(tmp_path):
    rutas = {k: tmp_path / Path(v).name for k, v in RUTAS_FUENTES.items()}
    for k, v in RUTAS_FUENTES.items():
        shutil.copyfile(v, rutas[k])
    rutas["catalogo"].write_text(rutas["catalogo"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
    r = ejecutar_pipeline(rutas, tmp_path / "x.db", tmp_path / "s", hoy=HOY, verificar_huellas=True, generar_reportes=False)
    assert r["estado"] == "FALLIDO" and r["tipo_error"] == "ErrorIntegridad" and r["error_previsto"] is True


def test_cli_con_json_truncado_alterno_falla_sin_traceback_y_conserva_la_bd(tmp_path):
    bd = tmp_path / "c.db"
    assert main(["--bd", str(bd), "--salida", str(tmp_path / "s")]) == 0
    roto = tmp_path / "ventas_online_truncado.json"
    roto.write_text('[{"order_id": "WEB-', encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "src.pipeline", "--bd", str(bd), "--salida", str(tmp_path / "s"),
                        "--online", str(roto)], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert p.returncode == 1 and "FALLIDO" in p.stdout and "no es un JSON válido" in p.stdout
    assert "Traceback" not in p.stdout + p.stderr
    with closing(sqlite3.connect(str(bd))) as c:
        assert c.execute("SELECT COUNT(*) FROM transacciones_limpias").fetchone()[0] == 1104
        assert [r[0] for r in c.execute("SELECT estado FROM ejecuciones ORDER BY inicio")] == ["COMPLETADO", "FALLIDO"]
