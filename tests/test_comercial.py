"""Pulso comercial: fórmulas con datos controlados (SQLite sintético) y contratos de la API con la base REAL del pipeline."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import comercial as co
from src.api.config import Ajustes
from src.api.db import ErrorApi
from src.api.main import crear_app
from src.config import RUTA_SALIDAS
from src.pipeline import ejecutar_pipeline
from tests.ayudas_nono import HOY

CRIT = co.Criterios()


# ----------------------------------------------------------------------------- base sintética mínima (solo columnas que lee el módulo)
def crear_bd(filas: list[dict]) -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE transacciones_limpias (id_transaccion TEXT, origen TEXT, fecha_venta TEXT, id_producto TEXT, nombre_producto TEXT, "
              "categoria TEXT, cantidad INTEGER, monto_total_mxn REAL, monto_total_mxn_cap REAL, estado_pedido TEXT, "
              "es_outlier_cantidad INTEGER, es_outlier_monto INTEGER)")
    for i, f in enumerate(filas):
        r = {"id_transaccion": f"T{i}", "origen": "FISICA", "id_producto": "P1", "nombre_producto": "Producto 1", "categoria": "Hogar", "cantidad": 1,
             "monto_total_mxn": 100.0, "estado_pedido": None, "es_outlier_cantidad": 0, "es_outlier_monto": 0, **f}
        r.setdefault("monto_total_mxn_cap", r["monto_total_mxn"])
        c.execute("INSERT INTO transacciones_limpias VALUES (:id_transaccion, :origen, :fecha_venta, :id_producto, :nombre_producto, :categoria, "
                  ":cantidad, :monto_total_mxn, :monto_total_mxn_cap, :estado_pedido, :es_outlier_cantidad, :es_outlier_monto)", r)
    return c


def dias(mes: str, desde: int, hasta: int, por_dia: int = 2, monto: float = 100.0, origen: str = "FISICA", **extra) -> list[dict]:
    return [{"fecha_venta": f"{mes}-{d:02d}", "origen": origen, "monto_total_mxn": monto, **extra} for d in range(desde, hasta + 1) for _ in range(por_dia)]


def resumen(c, mes=None, desde=None, hasta=None, canal=None, comparacion="equivalente", estados="todas", criterios=CRIT):
    return co.resumen(c, mes, desde, hasta, canal, comparacion, estados, criterios)


# ----------------------------------------------------------------------------- variación porcentual
@pytest.mark.parametrize("actual, anterior, esperado", [(125.0, 100.0, 25.0), (80.0, 100.0, -20.0), (100.0, 100.0, 0.0), (50.0, 0.0, None),
                                                        (0.0, 100.0, -100.0), (None, 100.0, None), (100.0, None, None), (1, 3, -66.67)])
def test_variacion_porcentual(actual, anterior, esperado):
    assert co.variacion_pct(actual, anterior) == esperado


# ----------------------------------------------------------------------------- ventas mensuales, canales, ticket
def test_ventas_mensuales_y_ticket_del_ultimo_mes_con_datos():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0) + dias("2026-10", 1, 16, 3, 200.0))
    r = resumen(c)
    assert r["periodo"]["etiqueta"] == "1–16 oct 2026" and r["filtros"]["mes"] == "2026-10"          # último mes CON datos
    assert (r["actual"]["transacciones"], r["actual"]["importe"], r["actual"]["ticket_promedio"]) == (48, 9600.0, 200.0)
    assert r["actual"]["promedio_diario"] == 600.0 and r["actual"]["dias_con_ventas"] == 16
    assert r["actual"]["primera_venta"] == "2026-10-01" and r["actual"]["ultima_venta"] == "2026-10-16"
    meses = {m["mes"]: m for m in co.meses_disponibles(c)}
    assert meses["2026-09"]["importe"] == 6000.0 and meses["2026-10"]["importe"] == 9600.0
    assert meses["2026-09"]["parcial"] is False and meses["2026-10"]["parcial"] is True and meses["2026-10"]["dias_mes"] == 31


def test_ventas_fisicas_y_online_con_participacion():
    c = crear_bd(dias("2026-10", 1, 10, 1, 300.0, "FISICA") + dias("2026-10", 1, 10, 1, 100.0, "ONLINE"))
    r = resumen(c)
    por = {x["canal"]: x for x in r["canales"]}
    assert por["FISICA"]["importe"] == 3000.0 and por["ONLINE"]["importe"] == 1000.0
    assert (por["FISICA"]["participacion_pct"], por["ONLINE"]["participacion_pct"]) == (75.0, 25.0)
    assert por["FISICA"]["ticket_promedio"] == 300.0 and por["ONLINE"]["transacciones"] == 10
    solo = resumen(c, canal="ONLINE")
    assert solo["actual"]["importe"] == 1000.0 and len(solo["canales"]) == 2          # el filtro no oculta la comparación de canales


def test_importe_comercial_es_el_normalizado_sin_capping():
    c = crear_bd([{"fecha_venta": "2026-10-01", "monto_total_mxn": 50000.0, "monto_total_mxn_cap": 800.0},
                  {"fecha_venta": "2026-10-02", "monto_total_mxn": 100.0, "monto_total_mxn_cap": 100.0}])
    r = resumen(c)
    assert r["actual"]["importe"] == 50100.0                                           # NO 900.0
    assert r["definicion_importe"]["campo"].endswith("monto_total_mxn") and "sin recorte estadístico" in r["definicion_importe"]["texto"]
    assert co.CAMPO_IMPORTE == "monto_total_mxn"


# ----------------------------------------------------------------------------- períodos: parcial, equivalente, ausencia
def test_mes_parcial_se_marca_y_se_compara_con_los_mismos_dias():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0) + dias("2026-10", 1, 16, 2, 100.0))
    r = resumen(c)
    assert r["periodo"]["parcial"] and r["periodo"]["dias"] == 16 and r["periodo"]["dias_calendario_mes"] == 31
    assert (r["anterior"]["inicio"], r["anterior"]["fin"]) == ("2026-09-01", "2026-09-16")      # intervalo equivalente, NO el mes completo
    assert r["homogeneo"] is True and "periodo_parcial" in r["avisos"]
    assert r["anterior_kpis"]["importe"] == 3200.0 and r["actual"]["importe"] == 3200.0
    assert r["variaciones"]["importe_pct"] == 0.0 and r["diagnostico"]["estado"] == "estable"
    assert any(m["id"] == "periodo_parcial" and "16 de los 31 días" in m["texto"] for m in r["diagnostico"]["mensajes"])


def test_mes_completo_contra_mes_anterior_completo_es_homogeneo():
    c = crear_bd(dias("2026-08", 1, 31, 1, 100.0) + dias("2026-09", 1, 30, 1, 100.0) + dias("2026-10", 1, 31, 1, 100.0))
    r = resumen(c, mes="2026-10", comparacion="mes_anterior_completo")
    assert r["periodo"]["parcial"] is False and r["anterior"]["dias"] == 30 and r["homogeneo"] is False       # 31 vs 30 días: no equivalentes
    r2 = resumen(c, mes="2026-09", comparacion="mes_anterior_completo")
    assert r2["homogeneo"] is False                                                                          # 30 vs 31
    r3 = resumen(c, mes="2026-09", comparacion="equivalente")
    assert r3["homogeneo"] is True and (r3["anterior"]["inicio"], r3["anterior"]["fin"]) == ("2026-08-01", "2026-08-30")


def test_comparar_parcial_contra_mes_completo_no_clasifica_tendencia():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0) + dias("2026-10", 1, 16, 2, 100.0))
    r = resumen(c, comparacion="mes_anterior_completo")
    assert r["homogeneo"] is False and "periodos_no_homogeneos" in r["avisos"] and r["diagnostico"]["estado"] == "no_concluyente"
    assert r["variaciones"]["importe_pct"] == -46.67                                  # el total sí se muestra, pero NO se interpreta
    msg = next(m for m in r["diagnostico"]["mensajes"] if m["id"] == "no_homogeneo")
    assert "no son equivalentes" in msg["texto"] and msg["evidencia"]["promedio_diario_variacion_pct"] == 0.0     # el promedio diario sí es comparable


def test_ausencia_de_mes_anterior_no_inventa_porcentaje():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0))
    r = resumen(c)
    assert r["anterior"]["cobertura"] == 0.0 and r["anterior_kpis"] is None and r["homogeneo"] is False
    assert all(v is None for v in r["variaciones"].values())
    assert r["diagnostico"]["estado"] == "sin_comparacion" and "No hay información suficiente para evaluar una tendencia" in r["diagnostico"]["titular"]
    assert resumen(c, comparacion="ninguna")["anterior"] is None


def test_periodo_sin_transacciones_dentro_de_la_cobertura():
    c = crear_bd(dias("2026-09", 1, 10, 1) + dias("2026-09", 20, 30, 1))
    r = resumen(c, desde="2026-09-12", hasta="2026-09-15")
    assert r["actual"]["transacciones"] == 0 and r["actual"]["importe"] == 0 and r["actual"]["ticket_promedio"] is None
    assert r["periodo"]["cobertura"] == 1.0 and r["diagnostico"]["estado"] == "sin_datos"
    assert r["diagnostico"]["mensajes"][0]["id"] == "sin_datos"


def test_rango_fuera_de_la_cobertura_se_declara_sin_datos():
    c = crear_bd(dias("2026-09", 1, 30, 1))
    r = resumen(c, desde="2026-12-01", hasta="2026-12-05")
    assert r["periodo"]["cobertura"] == 0.0 and r["actual"]["transacciones"] == 0 and "Los datos disponibles van del 2026-09-01 al 2026-09-30" in r["diagnostico"]["mensajes"][0]["texto"]


def test_rango_parcialmente_cubierto_se_marca_parcial_y_no_homogeneo():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0))
    r = resumen(c, desde="2026-09-25", hasta="2026-10-04")
    assert r["periodo"]["dias"] == 10 and r["periodo"]["dias_cubiertos"] == 6 and r["periodo"]["parcial"] is True
    assert any(m["id"] == "periodo_parcial" and "6 de sus 10 días" in m["texto"] for m in r["diagnostico"]["mensajes"])
    assert r["homogeneo"] is False


def test_rango_personalizado_compara_con_el_periodo_inmediato_anterior():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0))
    r = resumen(c, desde="2026-09-11", hasta="2026-09-20")
    assert (r["anterior"]["inicio"], r["anterior"]["fin"]) == ("2026-09-01", "2026-09-10") and r["homogeneo"] is True and r["modo"] == "personalizado"


# ----------------------------------------------------------------------------- diagnóstico: reglas y umbrales explícitos
def datos_con_variacion(pct: float) -> sqlite3.Connection:
    return crear_bd(dias("2026-09", 1, 10, 5, 100.0) + dias("2026-10", 1, 10, 5, round(100.0 * (1 + pct / 100), 4)))


@pytest.mark.parametrize("pct, estado, frase", [(5.0, "crecimiento", "aumentaron"), (4.9, "estable", "relativamente estables"), (0.0, "estable", "relativamente estables"),
                                                  (-4.9, "estable", "relativamente estables"), (-5.0, "disminucion", "disminuyeron"), (30.0, "crecimiento", "aumentaron")])
def test_umbrales_de_tendencia(pct, estado, frase):
    r = resumen(datos_con_variacion(pct))
    assert r["diagnostico"]["estado"] == estado
    texto = next(m for m in r["diagnostico"]["mensajes"] if m["id"] == "tendencia")
    assert frase in texto["texto"] and texto["evidencia"]["variacion_pct"] == pytest.approx(pct, abs=0.01)
    assert "$" in texto["texto"] and "1–10 oct 2026" in texto["texto"]               # el mensaje cita las cifras y los períodos


def test_umbrales_configurables():
    c = datos_con_variacion(8.0)
    assert resumen(c)["diagnostico"]["estado"] == "crecimiento"
    assert resumen(c, criterios=co.Criterios(umbral_crecimiento_pct=10.0))["diagnostico"]["estado"] == "estable"
    assert co.clasificar_tendencia(None, CRIT) is None


def test_criterios_desde_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("KOVA_UMBRAL_CRECIMIENTO_PCT", "12.5")
    monkeypatch.setenv("KOVA_MIN_TRANSACCIONES_PERIODO", "abc")                      # valor inválido: se ignora
    crit = co.Criterios.desde_entorno()
    assert crit.umbral_crecimiento_pct == 12.5 and crit.min_transacciones_periodo == 10


def test_pocas_transacciones_no_es_concluyente():
    c = crear_bd(dias("2026-09", 1, 3, 1, 100.0) + dias("2026-10", 1, 3, 1, 500.0))
    r = resumen(c)
    assert r["diagnostico"]["estado"] == "no_concluyente"
    m = next(m for m in r["diagnostico"]["mensajes"] if m["id"] == "pocas_transacciones")
    assert "no es concluyente" in m["texto"] and m["evidencia"]["minimo"] == 10


def test_periodo_anterior_sin_ventas_no_divide_entre_cero():
    c = crear_bd(dias("2026-09", 1, 1, 1, 100.0) + dias("2026-09", 21, 30, 2, 100.0))      # el 11–20 sep está dentro de la cobertura pero sin ventas
    r = resumen(c, desde="2026-09-21", hasta="2026-09-30")
    assert r["anterior_kpis"]["importe"] == 0 and r["variaciones"]["importe_pct"] is None
    assert r["diagnostico"]["estado"] == "sin_comparacion"
    assert any(m["id"] == "anterior_sin_ventas" and "denominador cero" in m["texto"] for m in r["diagnostico"]["mensajes"])


def test_mensajes_de_canal_con_reglas_cuantitativas():
    # física concentra 80 % y crece 100 %; online cae 20 %
    c = crear_bd(dias("2026-09", 1, 10, 5, 100.0, "FISICA") + dias("2026-09", 1, 10, 5, 100.0, "ONLINE")
                 + dias("2026-10", 1, 10, 5, 200.0, "FISICA") + dias("2026-10", 1, 10, 5, 80.0, "ONLINE"))
    ids = {m["id"]: m for m in resumen(c)["diagnostico"]["mensajes"]}
    assert "concentró" in ids["canal_participacion"]["texto"] and ids["canal_participacion"]["evidencia"]["canal"] == "FISICA"
    assert "El canal físico presentó un mejor desempeño" in ids["canal_desempeno"]["texto"]
    reparto = crear_bd(dias("2026-09", 1, 10, 5, 100.0, "FISICA") + dias("2026-09", 1, 10, 5, 100.0, "ONLINE")
                       + dias("2026-10", 1, 10, 5, 100.0, "FISICA") + dias("2026-10", 1, 10, 5, 100.0, "ONLINE"))
    ids2 = {m["id"]: m for m in resumen(reparto)["diagnostico"]["mensajes"]}
    assert "repartidas" in ids2["canal_participacion"]["texto"] and "evolucionaron de forma similar" in ids2["canal_desempeno"]["texto"]
    assert "canal_participacion" not in {m["id"] for m in resumen(c, canal="ONLINE")["diagnostico"]["mensajes"]}   # con un canal filtrado no se compara


def test_atipicas_advierten_y_calculan_la_variacion_sin_ellas():
    base = dias("2026-09", 1, 10, 5, 100.0) + dias("2026-10", 1, 10, 5, 100.0)
    atipicas = [{"fecha_venta": "2026-10-05", "monto_total_mxn": 100000.0, "monto_total_mxn_cap": 500.0, "es_outlier_monto": 1}]
    r = resumen(crear_bd(base + atipicas))
    assert r["atipicas"]["transacciones"] == 1 and r["atipicas"]["participacion_pct"] > 90
    assert r["atipicas"]["sin_atipicas"]["variacion_pct"] == 0.0 and r["variaciones"]["importe_pct"] > 1000
    m = next(m for m in r["diagnostico"]["mensajes"] if m["id"] == "atipicas")
    assert "dominado por ellas" in m["texto"] and "la variación frente al período anterior sería +0.0 %" in m["texto"]
    assert "atipicas" not in {m["id"] for m in resumen(crear_bd(base))["diagnostico"]["mensajes"]}


def test_solo_ventas_efectivas_excluye_cancelados_y_devueltos():
    c = crear_bd(dias("2026-10", 1, 5, 1, 100.0, "ONLINE", estado_pedido="COMPLETADO") + dias("2026-10", 1, 2, 1, 100.0, "ONLINE", estado_pedido="CANCELADO")
                 + dias("2026-10", 3, 3, 1, 100.0, "ONLINE", estado_pedido="DEVUELTO") + dias("2026-10", 1, 5, 1, 100.0, "FISICA"))
    todas, efectivas = resumen(c), resumen(c, estados="efectivas")
    assert todas["actual"]["transacciones"] == 13 and efectivas["actual"]["transacciones"] == 10
    assert todas["no_efectivas"] == {"transacciones": 3, "importe": 300.0}
    assert any(m["id"] == "no_efectivas" for m in todas["diagnostico"]["mensajes"]) and not any(m["id"] == "no_efectivas" for m in efectivas["diagnostico"]["mensajes"])


def test_el_diagnostico_nunca_afirma_rentabilidad_y_siempre_incluye_el_alcance():
    for c in (datos_con_variacion(40.0), datos_con_variacion(-40.0), crear_bd(dias("2026-09", 1, 3, 1))):
        textos = " ".join(m["texto"] for m in resumen(c)["diagnostico"]["mensajes"]).lower()
        assert "rentab" not in textos.replace("no permiten afirmar rentabilidad", "") and "ganancia" not in textos and "utilidad" not in textos
        assert "no hay costos, márgenes ni gastos" in textos


# ----------------------------------------------------------------------------- tendencia, productos
def test_serie_diaria_alineada_y_consistente_con_el_resumen():
    c = crear_bd(dias("2026-09", 1, 30, 2, 100.0) + dias("2026-10", 1, 16, 3, 200.0, "ONLINE"))
    t = co.tendencia(c, None, None, None, None, "equivalente", "todas")
    r = resumen(c)
    assert len(t["dias"]) == t["periodo"]["dias"] == 16
    assert sum(d["importe"] for d in t["dias"]) == pytest.approx(r["actual"]["importe"]) and t["dias"][-1]["acumulado"] == pytest.approx(r["actual"]["importe"])
    assert t["dias"][0]["fecha"] == "2026-10-01" and t["dias"][0]["fecha_anterior"] == "2026-09-01" and t["dias"][15]["fecha_anterior"] == "2026-09-16"
    assert t["dias"][0]["ticket_promedio"] == 200.0 and t["dias"][0]["ticket_anterior"] == 100.0 and t["dias"][0]["online"] == 600.0
    assert [m["mes"] for m in t["meses"]] == ["2026-09", "2026-10"]


def test_serie_diaria_no_dibuja_dias_fuera_de_la_cobertura():
    c = crear_bd(dias("2026-09", 1, 30, 1, 100.0))
    t = co.tendencia(c, None, "2026-09-28", "2026-10-03", None, "equivalente", "todas")
    assert [d["importe"] for d in t["dias"]][:3] == [100.0, 100.0, 100.0] and all(d["importe"] is None for d in t["dias"][3:])
    assert all(d["acumulado"] is None for d in t["dias"][3:])


def test_productos_y_categorias_principales():
    filas = ([{"fecha_venta": "2026-10-01", "id_producto": "A", "nombre_producto": "Alfa", "categoria": "Hogar", "monto_total_mxn": 600.0, "cantidad": 1}] * 2
             + [{"fecha_venta": "2026-10-02", "id_producto": "B", "nombre_producto": "Beta", "categoria": "Ropa", "monto_total_mxn": 300.0, "cantidad": 10}]
             + [{"fecha_venta": "2026-10-03", "id_producto": "C", "nombre_producto": "Gama", "categoria": "Ropa", "monto_total_mxn": 100.0, "cantidad": 1}])
    c = crear_bd(filas)
    p = co.productos(c, None, None, None, None, "equivalente", "todas", "importe", 10)
    assert [x["id_producto"] for x in p["productos"]] == ["A", "B", "C"] and p["importe_total"] == 1600.0
    assert [x["participacion_pct"] for x in p["productos"]] == [75.0, 18.75, 6.25] and sum(x["participacion_pct"] for x in p["productos"]) == pytest.approx(100)
    assert [x["categoria"] for x in p["categorias"]] == ["Hogar", "Ropa"] and p["categorias"][1]["importe"] == 400.0
    assert [x["id_producto"] for x in co.productos(c, None, None, None, None, "equivalente", "todas", "unidades", 10)["productos"]][:1] == ["B"]
    assert len(co.productos(c, None, None, None, None, "equivalente", "todas", "importe", 2)["productos"]) == 2 and p["productos_distintos"] == 3


def test_validaciones_del_modulo():
    c = crear_bd(dias("2026-10", 1, 5, 1))
    for kw, codigo in [({"mes": "2026-13"}, "PARAMETRO_INVALIDO"), ({"mes": "2026-10", "desde": "2026-10-01", "hasta": "2026-10-02"}, "PARAMETRO_INVALIDO"),
                       ({"desde": "2026-10-01"}, "PARAMETRO_INVALIDO"), ({"desde": "2026-10-09", "hasta": "2026-10-01"}, "PARAMETRO_INVALIDO"),
                       ({"desde": "2025-01-01", "hasta": "2026-12-31"}, "PARAMETRO_INVALIDO"), ({"mes": "2026-07"}, "MES_SIN_DATOS"),
                       ({"desde": "2026-10-01", "hasta": "2026-10-02", "comparacion": "mes_anterior_completo"}, "PARAMETRO_INVALIDO"),
                       ({"desde": "2026-02-30", "hasta": "2026-03-01"}, "PARAMETRO_INVALIDO")]:
        with pytest.raises(ErrorApi) as e:
            resumen(c, **kw)
        assert e.value.codigo == codigo, kw


def test_base_sin_ventas():
    with pytest.raises(ErrorApi) as e:
        resumen(crear_bd([]))
    assert e.value.codigo == "SIN_VENTAS" and e.value.estado == 404
    assert co.opciones(crear_bd([]))["hay_datos"] is False


# ----------------------------------------------------------------------------- API con la base REAL del pipeline
@pytest.fixture(scope="module")
def real(tmp_path_factory):
    d = tmp_path_factory.mktemp("comercial")
    aj = Ajustes(ruta_bd=d / "kova.db", dir_salida=d / "salida", raiz_salidas=RUTA_SALIDAS, dist_frontend=d / "sin_dist")
    assert ejecutar_pipeline(ruta_bd=aj.ruta_bd, dir_salida=aj.dir_salida, hoy=HOY, generar_reportes=False)["estado"] == "COMPLETADO"
    con = sqlite3.connect(str(aj.ruta_bd))
    yield TestClient(crear_app(aj)), con
    con.close()


def sql(con, consulta, *p):
    return con.execute(consulta, p).fetchall()


def test_opciones_y_mes_por_defecto_desde_los_datos_no_desde_el_reloj(real):
    c, con = real
    o = c.get("/api/comercial/opciones").json()
    minimo, maximo = sql(con, "SELECT MIN(fecha_venta), MAX(fecha_venta) FROM transacciones_limpias")[0]
    assert o["cobertura"] == {"inicio": minimo, "fin": maximo} and o["mes_por_defecto"] == maximo[:7] == o["meses"][-1]["mes"]
    assert [m["parcial"] for m in o["meses"]] == [False, True]


def test_resumen_real_coincide_con_sqlite(real):
    c, con = real
    r = c.get("/api/comercial/resumen").json()
    n, imp = sql(con, "SELECT COUNT(*), ROUND(SUM(monto_total_mxn), 2) FROM transacciones_limpias WHERE fecha_venta BETWEEN '2026-10-01' AND '2026-10-16'")[0]
    assert (r["actual"]["transacciones"], r["actual"]["importe"]) == (n, imp)
    assert r["actual"]["ticket_promedio"] == round(imp / n, 2)
    ant = sql(con, "SELECT ROUND(SUM(monto_total_mxn), 2) FROM transacciones_limpias WHERE fecha_venta BETWEEN '2026-09-01' AND '2026-09-16'")[0][0]
    assert r["anterior_kpis"]["importe"] == ant and r["variaciones"]["importe_pct"] == round((imp - ant) / ant * 100, 2)
    assert (r["periodo"]["etiqueta"], r["anterior"]["etiqueta"], r["homogeneo"], r["periodo"]["parcial"]) == ("1–16 oct 2026", "1–16 sep 2026", True, True)


def test_el_importe_comercial_no_es_el_importe_con_capping_ni_incluye_cuarentena(real):
    c, con = real
    total_api = sum(m["importe"] for m in c.get("/api/comercial/opciones").json()["meses"])
    comercial, cap = sql(con, "SELECT SUM(monto_total_mxn), SUM(monto_total_mxn_cap) FROM transacciones_limpias")[0]
    assert total_api == pytest.approx(comercial, abs=0.05) and abs(total_api - cap) > 1_000_000      # el capping recorta millones: no son equivalentes
    assert c.get("/api/dashboard").json()["indicadores"]["importe_total_mxn"] == pytest.approx(cap, abs=0.05)   # el Panel sigue mostrando el estadístico
    en_cuarentena = sql(con, "SELECT COUNT(*) FROM cuarentena_errores")[0][0]
    n_api = sum(m["transacciones"] for m in c.get("/api/comercial/opciones").json()["meses"])
    assert n_api == sql(con, "SELECT COUNT(*) FROM transacciones_limpias")[0][0] == 1104 and en_cuarentena == 116 and n_api + en_cuarentena == 1220
    assert sql(con, "SELECT COUNT(*) FROM transacciones_limpias WHERE ABS(monto_total_mxn - ROUND(cantidad * precio_unitario_mxn, 2)) > 0.01")[0][0] == 0


def test_canales_reales_suman_el_total_y_la_participacion_100(real):
    c, _ = real
    r = c.get("/api/comercial/resumen").json()
    assert sum(x["importe"] for x in r["canales"]) == pytest.approx(r["actual"]["importe"], abs=0.05)
    assert sum(x["participacion_pct"] for x in r["canales"]) == pytest.approx(100, abs=0.02)
    ca = c.get("/api/comercial/canales").json()
    assert {x["canal"] for x in ca["canales"]} == {"FISICA", "ONLINE"} and "no se aplica" in ca["nota"]


def test_resumen_real_detecta_atipicas_y_ofrece_la_variacion_sin_ellas(real):
    c, con = real
    r = c.get("/api/comercial/resumen").json()
    n, imp = sql(con, "SELECT COUNT(*), SUM(monto_total_mxn) FROM transacciones_limpias WHERE fecha_venta BETWEEN '2026-10-01' AND '2026-10-16' AND (es_outlier_cantidad=1 OR es_outlier_monto=1)")[0]
    assert r["atipicas"]["transacciones"] == n and r["atipicas"]["importe"] == pytest.approx(imp, abs=0.05)
    assert r["atipicas"]["sin_atipicas"]["variacion_pct"] is not None
    assert "atipicas" in {m["id"] for m in r["diagnostico"]["mensajes"]}                 # con los datos oficiales pesan más del 20 %


def test_filtros_reales_de_canal_y_estados(real):
    c, con = real
    web = c.get("/api/comercial/resumen", params={"canal": "ONLINE"}).json()
    assert web["actual"]["importe"] == sql(con, "SELECT ROUND(SUM(monto_total_mxn), 2) FROM transacciones_limpias WHERE origen='ONLINE' AND fecha_venta BETWEEN '2026-10-01' AND '2026-10-16'")[0][0]
    ef = c.get("/api/comercial/resumen", params={"estados": "efectivas"}).json()
    assert ef["actual"]["transacciones"] == sql(con, "SELECT COUNT(*) FROM transacciones_limpias WHERE fecha_venta BETWEEN '2026-10-01' AND '2026-10-16' AND (estado_pedido IS NULL OR estado_pedido NOT IN ('CANCELADO','DEVUELTO'))")[0][0]
    assert ef["actual"]["transacciones"] < c.get("/api/comercial/resumen").json()["actual"]["transacciones"]


def test_septiembre_completo_no_tiene_periodo_anterior_en_los_datos(real):
    c, _ = real
    r = c.get("/api/comercial/resumen", params={"mes": "2026-09"}).json()
    assert r["periodo"]["parcial"] is False and r["anterior"]["cobertura"] == 0 and r["variaciones"]["importe_pct"] is None
    assert r["diagnostico"]["estado"] == "sin_comparacion"


def test_tendencia_y_productos_reales(real):
    c, con = real
    t = c.get("/api/comercial/tendencia").json()
    assert len(t["dias"]) == 16 and t["dias"][-1]["acumulado"] == c.get("/api/comercial/resumen").json()["actual"]["importe"]
    p = c.get("/api/comercial/productos", params={"limite": 5}).json()
    assert len(p["productos"]) == 5 and p["productos"][0]["importe"] >= p["productos"][1]["importe"]
    top = sql(con, "SELECT id_producto FROM transacciones_limpias WHERE fecha_venta BETWEEN '2026-10-01' AND '2026-10-16' GROUP BY id_producto ORDER BY SUM(monto_total_mxn) DESC LIMIT 1")[0][0]
    assert p["productos"][0]["id_producto"] == top and sum(x["participacion_pct"] for x in p["categorias"]) == pytest.approx(100, abs=0.05)


@pytest.mark.parametrize("ruta, params", [
    ("resumen", {"mes": "2026-13"}), ("resumen", {"mes": "octubre"}), ("resumen", {"mes": "2026-10-01"}), ("resumen", {"mes": "'; DROP TABLE x;--"}),
    ("resumen", {"mes": "2026-10", "desde": "2026-10-01", "hasta": "2026-10-05"}), ("resumen", {"desde": "2026-10-01"}),
    ("resumen", {"desde": "2026-10-09", "hasta": "2026-10-01"}), ("resumen", {"desde": "2026-02-30", "hasta": "2026-03-01"}),
    ("resumen", {"desde": "ayer", "hasta": "hoy"}), ("resumen", {"desde": "2020-01-01", "hasta": "2026-12-31"}), ("resumen", {"mes": "2026-07"}),
    ("resumen", {"canal": "TIENDA"}), ("resumen", {"comparacion": "otro"}), ("resumen", {"estados": "algunas"}),
    ("resumen", {"desde": "2026-10-01", "hasta": "2026-10-05", "comparacion": "mes_anterior_completo"}),
    ("tendencia", {"canal": "x"}), ("canales", {"mes": "xx"}), ("productos", {"limite": 0}), ("productos", {"limite": 51}), ("productos", {"orden": "precio"}),
])
def test_parametros_invalidos_son_422_con_mensaje(real, ruta, params):
    r = real[0].get(f"/api/comercial/{ruta}", params=params)
    assert r.status_code == 422 and r.json()["codigo"] in ("PARAMETRO_INVALIDO", "MES_SIN_DATOS") and r.json()["mensaje"]


def test_endpoints_comerciales_sin_base_o_sin_ventas(tmp_path):
    aj = Ajustes(ruta_bd=tmp_path / "x.db", dir_salida=tmp_path / "s", raiz_salidas=RUTA_SALIDAS, dist_frontend=tmp_path / "d")
    cli = TestClient(crear_app(aj))
    for ruta in ("opciones", "resumen", "tendencia", "canales", "productos"):
        r = cli.get(f"/api/comercial/{ruta}")
        assert r.status_code == 503 and r.json()["codigo"] == "BD_NO_ENCONTRADA"
    con = sqlite3.connect(str(aj.ruta_bd))
    con.executescript((Path(__file__).resolve().parent.parent / "src" / "persistencia" / "esquema.sql").read_text(encoding="utf-8"))
    con.commit(); con.close()
    r = cli.get("/api/comercial/resumen")
    assert r.status_code == 404 and r.json()["codigo"] == "SIN_VENTAS"
    assert cli.get("/api/comercial/opciones").json() == {**cli.get("/api/comercial/opciones").json(), "hay_datos": False, "mes_por_defecto": None}


def test_criterios_configurables_llegan_a_la_api(real, tmp_path):
    c, _ = real
    assert c.get("/api/comercial/resumen").json()["criterios"]["umbral_crecimiento_pct"] == 5.0
    aj = Ajustes(ruta_bd=Path(c.app.state.ajustes.ruta_bd), dir_salida=tmp_path, raiz_salidas=RUTA_SALIDAS, criterios_comerciales=co.Criterios(umbral_crecimiento_pct=200.0))
    r = TestClient(crear_app(aj)).get("/api/comercial/resumen").json()
    assert r["criterios"]["umbral_crecimiento_pct"] == 200.0 and r["diagnostico"]["estado"] == "estable"      # +74 % ya no supera el umbral


def test_los_endpoints_comerciales_son_de_solo_lectura(real):
    c, con = real
    antes = Path(c.app.state.ajustes.ruta_bd).stat().st_mtime_ns
    for ruta in ("opciones", "resumen", "tendencia", "canales", "productos"):
        assert c.get(f"/api/comercial/{ruta}").status_code == 200
    assert Path(c.app.state.ajustes.ruta_bd).stat().st_mtime_ns == antes
    assert c.post("/api/comercial/resumen").status_code == 405


# ----------------------------------------------------------------------------- monedas originales
def test_usd_originales_se_conservan_y_se_presentan_separados(real):
    c, con = real
    usd = sql(con, "SELECT id_transaccion FROM transacciones_limpias WHERE moneda_original='USD'")
    assert len(usd) == 174 and sql(con, "SELECT COUNT(*) FROM transacciones_limpias WHERE moneda_original='USD' AND (precio_unitario_original IS NULL OR monto_total_origen IS NULL)")[0][0] == 0
    assert sql(con, "SELECT COUNT(*) FROM transacciones_limpias WHERE moneda_original='USD' AND tipo_cambio_aplicado <> 19.5")[0][0] == 0
    m = c.get("/api/transacciones/WEB-00002").json()["moneda"]
    assert m == {**m, "moneda_original": "USD", "es_usd": True, "tipo_cambio": 19.5, "precio_original": 169.59, "importe_original": 169.59,
                 "precio_mxn": 3307.01, "importe_mxn": 3307.01, "capping_aplicado": False, "importe_original_corregido": False}
    assert "19.5" in m["formula"]
    for (id_,) in usd[:25]:                                                          # nunca se pierde el valor original ni se mezcla con el convertido
        mm = c.get(f"/api/transacciones/{id_}").json()["moneda"]
        assert mm["precio_original"] is not None and mm["importe_original"] is not None and mm["precio_mxn"] == pytest.approx(round(mm["precio_original"] * 19.5 + 1e-9, 2), abs=0.011)


def test_usd_con_importe_original_inconsistente_conserva_el_valor_reportado(real):
    m = real[0].get("/api/transacciones/WEB-00237").json()["moneda"]
    assert m["importe_original"] == 17304.8 and m["importe_original_corregido"] is True and m["importe_original_coherente"] == 216.31
    assert m["importe_mxn"] == 4218.05


def test_una_venta_en_mxn_no_muestra_conversion(real):
    m = real[0].get("/api/transacciones/WEB-00003").json()["moneda"]
    assert m["es_usd"] is False and m["tipo_cambio"] is None and m["formula"] is None and m["importe_original_coherente"] is None
    assert m["precio_original"] == m["precio_mxn"] == 1228.72


def test_el_importe_original_mxn_inflado_se_conserva_y_no_se_presenta_como_conversion(real):
    m = real[0].get("/api/transacciones/WEB-00508").json()["moneda"]
    assert m["es_usd"] is False and m["importe_original"] == 826360.8 and m["importe_mxn"] == 10329.51


def test_el_tipo_de_cambio_oficial_no_cambio():
    from decimal import Decimal
    from src.config import PARIDAD_USD_MXN
    assert PARIDAD_USD_MXN == Decimal("19.50")
