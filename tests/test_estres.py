"""Pruebas de estrés (etapa de Nono): datos corruptos inyectados sobre COPIAS de registros reales.

La lógica de cada escenario vive en `datos/estres/generar_estres.py` (una sola implementación, compartida con el
script que genera `salidas/etapa_nono/estres/resultados_estres.csv`). Los originales de datos/crudos/ no se tocan.
"""
from __future__ import annotations

import sys

import pytest

from tests.conftest import RAIZ

sys.path.insert(0, str(RAIZ / "datos" / "estres"))
import generar_estres as ge  # noqa: E402

IDS_FILA = [f"E{i:02d}" for i in list(range(1, 18)) + list(range(20, 41))]
IDS_GLOBALES = [f"G{i:02d}" for i in range(1, 11)]


@pytest.fixture(scope="module")
def corrida_filas(tmp_path_factory):
    filas, extra = ge.ejecutar_escenarios_fila(tmp_path_factory.mktemp("estres_filas"))
    return {f["id"]: f for f in filas}, extra


@pytest.fixture(scope="module")
def corrida_globales(tmp_path_factory):
    return {r["id"]: r for r in ge.ejecutar_escenarios_globales(tmp_path_factory.mktemp("estres_globales"))}


def test_los_originales_no_se_tocan_al_generar_datos_corruptos(corrida_filas):
    from src.extraccion import verificar_integridad
    assert all(verificar_integridad().values())


def test_el_pipeline_procesa_los_validos_aunque_haya_invalidos(corrida_filas):
    _, extra = corrida_filas
    assert extra["resumen"]["estado"] == "COMPLETADO"
    inv = extra["invariantes"]
    assert inv["limpias"] > 0 and inv["cuarentena"] > 0


@pytest.mark.parametrize("sid", IDS_FILA)
def test_escenario_por_registro(corrida_filas, sid):
    filas, _ = corrida_filas
    f = filas[sid]
    assert f["ok"], f"{sid} {f['escenario']}: esperado {f['esperado']} · obtenido {f['obtenido']} · {f['motivo']}"


def test_invariantes_del_lote_con_datos_corruptos(corrida_filas):
    inv = corrida_filas[1]["invariantes"]
    assert inv["conserva_conteo"], "nada se pierde: limpias + cuarentena = entrada"
    assert inv["cuarentena_sin_motivo_vacio"] and inv["fechas_iso_en_limpias"]
    assert inv["tabla_limpias_existe"], "la inyección SQL no debe borrar la tabla"


def test_todo_registro_rechazado_conserva_su_registro_original(corrida_filas):
    import sqlite3
    c = sqlite3.connect(str(corrida_filas[1]["bd"]))
    assert c.execute("SELECT COUNT(*) FROM cuarentena_errores WHERE registro_original IS NULL "
                     "OR trim(registro_original) = ''").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM cuarentena_errores WHERE detalle_error IS NULL").fetchone()[0] == 0
    c.close()


def test_inyeccion_sql_queda_como_texto_en_la_cuarentena(corrida_filas):
    import sqlite3
    c = sqlite3.connect(str(corrida_filas[1]["bd"]))
    ids = {r[0] for r in c.execute("SELECT id_registro FROM cuarentena_errores")}
    c.close()
    assert "'; DROP TABLE transacciones_limpias;--" in ids


def test_efectos_de_las_correcciones_en_registros_validos(corrida_filas):
    import sqlite3
    _, extra = corrida_filas
    fila = {f["id"]: f["fila"] for f in corrida_filas[0].values()}
    c = sqlite3.connect(str(extra["bd"]))
    mediana = c.execute("SELECT cantidad_origen, cantidad, monto_total_mxn FROM transacciones_limpias "
                        "WHERE origen='FISICA' AND id_fila_origen=?", (fila["E03"],)).fetchone()
    assert mediana[0] is None and mediana[1] >= 1 and mediana[2] > 0          # E03: cantidad imputada, monto recalculado
    corregido = c.execute("SELECT monto_total_origen, monto_total_mxn, correcciones FROM transacciones_limpias "
                          "WHERE origen='FISICA' AND id_fila_origen=?", (fila["E13"],)).fetchone()
    assert corregido[0] == 93502.40 and corregido[1] != corregido[0] and "MONTO_RECALCULADO_INCONSISTENTE" in corregido[2]
    emoji = c.execute("SELECT direccion_envio FROM transacciones_limpias WHERE origen='ONLINE' AND id_fila_origen=?",
                      (fila["E31"],)).fetchone()
    assert emoji[0] == "Calle Ñandú 5 😀, Colima"
    c.close()


@pytest.mark.parametrize("sid", IDS_GLOBALES)
def test_escenario_global(corrida_globales, sid):
    r = corrida_globales[sid]
    assert r["ok"], f"{sid} {r['escenario']}: esperado {r['esperado']} · obtenido {r['obtenido']} · {r['motivo']}"
