"""Pruebas de F1 · perfilado (Leslie)."""
import pandas as pd
import pytest

from src.calidad.perfilado import (clasificar_faltantes, clasificar_faltantes_por_canal, es_vacio,
                                   inferir_tipo, metricas_calidad, perfil_a_tabla, perfilar_dataframe,
                                   perfilar_fuentes)


def test_es_vacio():
    s = pd.Series([None, "", "  ", "x", float("nan"), 0])
    assert es_vacio(s).tolist() == [True, True, True, False, True, False]


@pytest.mark.parametrize("valores, tipo", [(["1", "2"], "entero"), (["1.5", "2"], "decimal"),
                                           (["a", "b"], "texto"), ([1, "x"], "mixto(int, str)"),
                                           (["", None], "vacío")])
def test_inferir_tipo(valores, tipo):
    assert inferir_tipo(pd.Series(valores, dtype=object)) == tipo


def test_perfil_fisica_real(fuentes):
    p = perfilar_dataframe(fuentes["fisica"], "fisica")
    assert (p["filas"], p["columnas"]) == (620, 9)
    assert p["nulos"]["monto_total_mxn"] == 32 and p["nulos"]["id_cliente"] == 127
    assert p["pct_nulos"]["id_cliente"] == 20.48
    assert p["completitud_global_pct"] == 97.15
    assert p["duplicados_exactos"] == 20
    assert p["tipos"]["cantidad"] == "entero" and p["tipos"]["monto_total_mxn"] == "decimal"


def test_perfil_online_real(fuentes):
    p = perfilar_dataframe(fuentes["online"], "online")
    assert (p["filas"], p["columnas"]) == (600, 11)
    assert p["nulos"]["customer_email"] == 20          # null + "" (detalle técnico de la guía §1.1)
    assert p["nulos"]["shipping_address"] == 77
    assert p["completitud_global_pct"] == 98.53
    assert p["duplicados_exactos"] == 0
    assert p["tipos"]["order_timestamp"] == "mixto(int, str)"


def test_perfil_catalogo_real(fuentes):
    p = perfilar_fuentes(fuentes)["catalogo"]
    assert p["completitud_global_pct"] == 100.0 and p["duplicados_exactos"] == 0


def test_perfil_a_tabla(fuentes):
    t = perfil_a_tabla(perfilar_dataframe(fuentes["fisica"], "fisica"))
    assert len(t) == 9 and {"columna", "nulos", "pct_nulos", "tipo_inferido"} <= set(t.columns)


def test_mcar_reales_coinciden_con_diagnostico(df_homologado):
    esperado = {("FISICA", "id_cliente"): [0.7143, 0.5713], ("FISICA", "monto_total"): [0.4786, 0.5685],
                ("ONLINE", "email_cliente"): [0.7786, 0.3143], ("ONLINE", "direccion_envio"): [0.28, 0.5321]}
    for r in clasificar_faltantes_por_canal(df_homologado):
        assert r["clasificacion"] == "MCAR"
        assert [p["p_valor"] for p in r["pruebas"]] == pytest.approx(esperado[(r["origen"], r["columna"])], abs=1e-4)


def test_mar_sintetico_detectado():
    grupo = ["A"] * 100 + ["B"] * 100
    valor = [None] * 60 + ["x"] * 40 + ["x"] * 100            # faltan solo en el grupo A
    r = clasificar_faltantes(pd.DataFrame({"g": grupo, "v": valor}), "v", ["g"])
    assert r["clasificacion"] == "MAR(g)"


def test_sin_faltantes():
    r = clasificar_faltantes(pd.DataFrame({"g": ["A", "B"], "v": ["x", "y"]}), "v", ["g"])
    assert r["clasificacion"] == "SIN_FALTANTES"


def test_metricas_calidad_antes(df_homologado):
    fis = metricas_calidad(df_homologado[df_homologado["origen"] == "FISICA"])
    assert fis["duplicados_exactos"] == 20 and fis["cantidad_menor_igual_0"] == 11
    assert fis["monto_total_media"] == 16586.74 and fis["monto_total_mediana"] == 3506.37
    assert fis["monto_total_asimetria"] == pytest.approx(14.0766, abs=1e-4)
    onl = metricas_calidad(df_homologado[df_homologado["origen"] == "ONLINE"])
    assert onl["monto_inconsistente"] == 12
