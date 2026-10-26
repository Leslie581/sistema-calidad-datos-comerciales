"""Pruebas de F2 · limpieza e imputación (Leslie)."""
import pandas as pd
import pytest

from src.calidad.limpieza import (imputar_categoricas, imputar_mediana, limpiar_registros, marcar_duplicados,
                                  mediana_entera, recalcular_montos)
from src.contratos import ErrorContrato
from tests.conftest import df_minimo, fila


# ------------------------------------------------------------------ duplicados (R2.3, R2.4)
def test_duplicados_reales(etapa_limpieza):
    df, bitacora = etapa_limpieza
    assert bitacora["duplicados_exactos"] == 20 and bitacora["ids_en_conflicto"] == 0
    dups = df[df["es_duplicado"]]
    assert set(dups["origen"]) == {"FISICA"}
    assert sorted(dups["id_fila_origen"]) == list(range(601, 621))
    primera, copia = fila(df, "POS-2026-0001", 0), fila(df, "POS-2026-0001", 1)
    assert (primera["id_fila_origen"], primera["es_duplicado"]) == (1, False)
    assert (copia["id_fila_origen"], copia["es_duplicado"]) == (613, True)


def test_id_conflicto_sintetico():
    df = df_minimo([{"id_transaccion": "POS-2026-0001", "registro_original": '{"a":1}'},
                    {"id_transaccion": "POS-2026-0001", "registro_original": '{"a":2}'},
                    {"id_transaccion": "POS-2026-0002", "registro_original": '{"b":1}'},
                    {"id_transaccion": "POS-2026-0002", "registro_original": '{"b":1}'}])
    out = marcar_duplicados(df)
    assert out["es_id_conflicto"].tolist() == [True, True, False, False]
    assert out["es_duplicado"].tolist() == [False, False, False, True]


# ------------------------------------------------------------------ importes (R6)
def test_recalculo_nulos_reales(etapa_limpieza):
    df, b = etapa_limpieza
    assert b["reconstruccion_montos"]["recalculados_nulo"] == 32
    r = fila(df, "POS-2026-0082")
    assert pd.isna(r["monto_total_origen"]) and r["monto_total"] == 6613.98
    assert "MONTO_RECALCULADO_NULO" in r["correcciones"]


def test_recalculo_x80_real_conserva_original(etapa_limpieza):
    df, b = etapa_limpieza
    assert b["reconstruccion_montos"]["recalculados_inconsistente"] == 12
    assert b["reconstruccion_montos"]["factores_inconsistencia"] == {"80.0": 12}
    r = fila(df, "WEB-00508")
    assert (r["monto_total_origen"], r["monto_total"]) == (826360.8, 10329.51)
    r = fila(df, "WEB-00237")                                  # USD: se corrige en moneda original
    assert (r["monto_total_origen"], r["monto_total"]) == (17304.8, 216.31)


def test_no_recalcula_cantidades_imposibles(etapa_limpieza):
    r = fila(etapa_limpieza[0], "POS-2026-0216")
    assert r["monto_total"] == -934.83 and r["correcciones"] == []


def test_recalculo_respeta_tolerancia():
    df = df_minimo([{"cantidad": 3.0, "precio_unitario": 0.1, "monto_total": 0.3},       # float: 0.30000000000000004
                    {"cantidad": 2.0, "precio_unitario": 10.0, "monto_total": 20.02}])   # > 0.01 → corrige
    out, b = recalcular_montos(df)
    assert out["monto_total"].tolist() == [0.3, 20.0]
    assert b["recalculados_inconsistente"] == 1


# ------------------------------------------------------------------ categóricas (R3.7–R3.9)
def test_categoricas_reales(etapa_limpieza):
    df, b = etapa_limpieza
    assert b["imputacion_categoricas"] == {"FISICA.id_cliente→ANONIMO": 127, "ONLINE.email_cliente→SIN_CORREO": 20,
                                           "ONLINE.direccion_envio→SIN_DIRECCION": 77}
    assert fila(df, "POS-2026-0005")["id_cliente"] == "ANONIMO"
    assert fila(df, "WEB-00040")["email_cliente"] == "SIN_CORREO"
    assert fila(df, "WEB-00003")["direccion_envio"] == "SIN_DIRECCION"


def test_etiquetas_solo_en_su_canal(etapa_limpieza):
    df = etapa_limpieza[0]
    assert df.loc[df["origen"] == "ONLINE", "id_cliente"].isna().all()
    assert df.loc[df["origen"] == "FISICA", "email_cliente"].isna().all()


def test_correo_malformado_no_se_imputa(etapa_limpieza):
    assert fila(etapa_limpieza[0], "WEB-00083")["email_cliente"] == "sin_arroba_dominio.org"


# ------------------------------------------------------------------ mediana (R3.3–R3.5)
def test_mediana_por_canal_sintetica():
    df = df_minimo([{"origen": "FISICA", "cantidad": v} for v in (1, 2, 2, 5, None)]
                   + [{"origen": "ONLINE", "cantidad": v} for v in (1, 1, 3, None)])
    out, b = imputar_mediana(df, "cantidad")
    assert b["medianas_por_canal"] == {"FISICA": 2.0, "ONLINE": 1.0}
    assert out["cantidad"].tolist() == [1, 2, 2, 5, 2, 1, 1, 3, 1]
    assert out["cantidad_origen"].isna().sum() == 2                       # original conservado
    assert b["imputados"] == 2


@pytest.mark.parametrize("valores, esperado", [([1, 2], 2.0), ([1, 2, 3, 4], 3.0), ([5], 5.0), ([], None)])
def test_mediana_entera(valores, esperado):
    assert mediana_entera(pd.Series(valores, dtype="float64")) == esperado


def test_mediana_excluye_invalidos_y_duplicados():
    df = df_minimo([{"cantidad": v} for v in (-1, 0, 0, 1, 3, None)])
    df["es_duplicado"] = [False, False, False, False, False, False]
    _, b = imputar_mediana(df)
    assert b["medianas_por_canal"]["FISICA"] == 2.0                        # mediana de [1, 3]


def test_no_imputa_cantidad_no_numerica():
    df = df_minimo([{"cantidad": None, "alertas": ["CANTIDAD_NO_NUMERICA"]}, {"cantidad": 2.0}])
    out, b = imputar_mediana(df)
    assert pd.isna(out.loc[0, "cantidad"]) and b["no_numericos_no_imputados"] == 1


def test_mediana_real_sin_casos(etapa_limpieza):
    b = etapa_limpieza[1]["imputacion_mediana"]
    assert b["medianas_por_canal"] == {"FISICA": 2.0, "ONLINE": 1.0} and b["imputados"] == 0


def test_imputacion_y_recalculo_encadenados():
    df = df_minimo([{"cantidad": None, "monto_total": None, "precio_unitario": 50.0}, {"cantidad": 3.0}])
    out, _ = limpiar_registros(df)
    assert (out.loc[0, "cantidad"], out.loc[0, "monto_total"]) == (3.0, 150.0)
    assert out.loc[0, "correcciones"][:2] == ["IMPUTADO_MEDIANA_CANTIDAD", "MONTO_RECALCULADO_NULO"]


# ------------------------------------------------------------------ propiedades
def test_funciones_puras(df_homologado):
    copia = df_homologado.copy(deep=True)
    limpiar_registros(df_homologado)
    pd.testing.assert_frame_equal(df_homologado, copia)


def test_conserva_filas_y_originales(df_homologado, etapa_limpieza):
    df = etapa_limpieza[0]
    assert len(df) == len(df_homologado) == 1220
    pd.testing.assert_series_equal(df["monto_total_origen"], df_homologado["monto_total"], check_names=False)
    pd.testing.assert_series_equal(df["cantidad_origen"], df_homologado["cantidad"], check_names=False)


def test_contrato_incompleto():
    with pytest.raises(ErrorContrato):
        limpiar_registros(pd.DataFrame({"id_transaccion": ["x"]}))


def test_listas_sin_aliasing(etapa_limpieza):
    df = etapa_limpieza[0]
    ids = [id(lst) for lst in df["correcciones"]]
    assert len(set(ids)) == len(ids)
