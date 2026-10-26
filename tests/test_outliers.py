"""Pruebas de F3 · IQR y capping (Leslie) y de las funciones mínimas de Yerik que usa."""
import pandas as pd
import pytest

from src.calidad.outliers import calcular_limites_iqr, mascara_base_estadistica, tratar_outliers
from src.contratos import ErrorContrato
from src.integracion.moneda import convertir_a_mxn
from tests.conftest import df_minimo, fila


# ------------------------------------------------------------------ IQR
def test_iqr_conocido():
    lim = calcular_limites_iqr(pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100]))
    assert (lim["Q1"], lim["Q3"], lim["IQR"], lim["LS"], lim["outliers_superiores"]) == (3.25, 7.75, 4.5, 14.5, 1)


def test_iqr_vacio():
    assert calcular_limites_iqr(pd.Series([], dtype="float64"))["n"] == 0


# ------------------------------------------------------------------ Yerik mínimo: USD→MXN y catálogo
def test_conversion_usd_real(df_mxn):
    r = fila(df_mxn, "WEB-00002")
    assert (r["precio_unitario_mxn"], r["monto_total_mxn"], r["tipo_cambio_aplicado"]) == (3307.01, 3307.01, 19.5)
    assert fila(df_mxn, "WEB-00237")["monto_total_mxn"] == 4218.05          # ×80 ya corregido
    assert (df_mxn["moneda_original"] == "USD").sum() == 193


def test_usd_coincide_con_catalogo(df_mxn):
    usd = df_mxn[(df_mxn["moneda_original"] == "USD") & df_mxn["en_catalogo"]]
    assert len(usd) == 180 and usd["dif_precio_catalogo"].max() <= 0.10 + 1e-9


def test_huerfanos(df_mxn):
    h = df_mxn[~df_mxn["en_catalogo"]]
    assert h.groupby("origen").size().to_dict() == {"FISICA": 29, "ONLINE": 33}


def test_moneda_no_soportada():
    df = df_minimo([{"moneda": "EUR"}])
    out = convertir_a_mxn(df)
    assert "MONEDA_NO_SOPORTADA" in out.loc[0, "alertas"] and pd.isna(out.loc[0, "precio_unitario_mxn"])


# ------------------------------------------------------------------ capping real
def test_base_estadistica(etapa_outliers):
    lim = etapa_outliers[1]["base_estadistica"]
    assert lim["total"] == 1129 and lim["por_canal"] == {"ONLINE": 567, "FISICA": 562}


def test_capping_cantidad_fisica(etapa_outliers):
    lim = etapa_outliers[1]["cantidad"]["FISICA"]
    assert (lim["Q1"], lim["Q3"], lim["LS"], lim["tope_entero"], lim["outliers_superiores"]) == (1, 4, 8.5, 8, 13)
    assert lim["recortados"] == 13


def test_capping_cantidad_online_sin_outliers(etapa_outliers):
    lim = etapa_outliers[1]["cantidad"]["ONLINE"]
    assert (lim["LS"], lim["outliers_superiores"], lim["recortados"]) == (3.5, 0, 0)


def test_capping_monto(etapa_outliers):
    lim = etapa_outliers[1]["monto_mxn"]
    assert lim["LS"] == pytest.approx(12032.68, abs=0.005)
    assert (lim["Q1"], lim["Q3"]) == (pytest.approx(1563.78), pytest.approx(5751.34))
    assert lim["outliers_superiores"] == 80 and lim["outliers_inferiores"] == 0


def test_ejemplos_reales(etapa_outliers):
    df = etapa_outliers[0]
    r = fila(df, "POS-2026-0031")
    assert (r["cantidad"], r["cantidad_cap"], r["monto_total_mxn"], r["monto_total_mxn_cap"]) == (500, 8, 512990.0, 8207.84)
    assert r["es_outlier_cantidad"] and not r["es_outlier_monto"]
    r = fila(df, "POS-2026-0021")
    assert (r["cantidad_cap"], r["monto_cantidad_cap_mxn"], r["monto_total_mxn_cap"]) == (8, 16856.48, 12032.68)
    assert r["es_outlier_cantidad"] and r["es_outlier_monto"]
    r = fila(df, "WEB-00508")
    assert r["monto_total_mxn_cap"] == 10329.51 and not r["es_outlier_monto"]


def test_invalidos_pasan_sin_cambio(etapa_outliers):
    r = fila(etapa_outliers[0], "POS-2026-0216")
    assert (r["cantidad_cap"], r["monto_total_mxn_cap"], r["es_outlier_cantidad"]) == (-1, -934.83, False)


def test_capping_no_borra_ni_sobrescribe(df_mxn, etapa_outliers):
    df = etapa_outliers[0]
    assert len(df) == len(df_mxn) == 1220
    for col in ("cantidad", "cantidad_origen", "monto_total_origen", "monto_total", "monto_total_mxn"):
        pd.testing.assert_series_equal(df[col], df_mxn[col])


def test_limites_respetados(etapa_outliers):
    df, lim = etapa_outliers
    validas = df["cantidad"] > 0
    assert df.loc[validas & (df["origen"] == "FISICA"), "cantidad_cap"].max() == 8
    assert df.loc[validas, "monto_total_mxn_cap"].max() <= round(lim["monto_mxn"]["LS"], 2)


def test_mascara_base_excluye_defectos(etapa_outliers):
    df = etapa_outliers[0]
    base = mascara_base_estadistica(df)
    assert not (base & df["es_duplicado"]).any()
    assert not (base & ~df["en_catalogo"]).any()
    assert not (base & (df["cantidad"] <= 0)).any()


def test_contrato_outliers():
    with pytest.raises(ErrorContrato):
        tratar_outliers(pd.DataFrame({"cantidad": [1]}))
