"""Pruebas de la etapa de Yerik: fechas, USD→MXN, catálogo/huérfanos, Min-Max y discretización."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src.contratos import (ALERTA_FECHA_NO_INTERPRETABLE, ALERTA_MONEDA_NO_SOPORTADA,
                           ALERTA_PRECIO_DIFIERE_CATALOGO, COLUMNAS_AGREGA_CATALOGO, COLUMNAS_AGREGA_FECHAS,
                           COLUMNAS_AGREGA_IMPORTES_MXN, COLUMNAS_AGREGA_OUTLIERS, COLUMNAS_AGREGA_TRANSFORMACION,
                           COLUMNAS_HOMOLOGADAS, ErrorContrato)
from src.extraccion import ErrorExtraccion, leer_catalogo, leer_csv_ventas
from src.integracion import integrar
from src.integracion.catalogo import cruzar_catalogo, huerfanos
from src.integracion.fechas import ZONA_UTC, interpretar_fecha, normalizar_fecha, normalizar_fechas
from src.integracion.moneda import convertir_a_mxn
from src.integracion.transformacion import discretizar_importe, escalar_min_max, transformar
from tests.conftest import df_minimo, fila


# ----------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def df_integrado(etapa_limpieza, fuentes):
    return integrar(etapa_limpieza[0], fuentes["catalogo"])


@pytest.fixture(scope="session")
def etapa_transformada(df_integrado):
    from src.calidad.outliers import tratar_outliers
    df_o, _ = tratar_outliers(df_integrado)
    return transformar(df_o)           # (df, parametros)


# ----------------------------------------------------------------------------- integración general
def test_integrar_conserva_1220_filas_y_contrato(df_integrado, etapa_limpieza):
    assert len(df_integrado) == 1220
    assert df_integrado.groupby("origen").size().to_dict() == {"FISICA": 620, "ONLINE": 600}
    esperadas = (COLUMNAS_HOMOLOGADAS + COLUMNAS_AGREGA_FECHAS + COLUMNAS_AGREGA_IMPORTES_MXN
                 + COLUMNAS_AGREGA_CATALOGO)
    assert set(esperadas) <= set(df_integrado.columns)


def test_integrar_no_altera_valores_originales(df_integrado, etapa_limpieza):
    limpio = etapa_limpieza[0]
    for col in ["registro_original", "fecha_cruda", "id_transaccion", "precio_unitario", "monto_total",
                "cantidad_origen", "monto_total_origen", "moneda"]:
        pd.testing.assert_series_equal(df_integrado[col], limpio[col], check_names=False)


def test_integrar_exige_columnas_de_limpieza(df_homologado, fuentes):
    with pytest.raises(ErrorContrato):
        integrar(df_homologado, fuentes["catalogo"])        # le faltan es_duplicado, cantidad_origen, ...


# ----------------------------------------------------------------------------- fechas
@pytest.mark.parametrize("entrada, esperado, formato", [
    ("13-09-2026", "2026-09-13", "DD-MM-YYYY"),
    ("26/09/2026", "2026-09-26", "DD/MM/YYYY"),
    ("2026-09-13", "2026-09-13", "YYYY-MM-DD"),
    ("2026-10-12T02:23:00", "2026-10-12", "ISO_DATETIME"),
    ("1789105020", "2026-09-10", "EPOCH"),
    (1789105020, "2026-09-10", "EPOCH"),
    (1789105020.0, "2026-09-10", "EPOCH"),
    ("  01/09/2026 ", "2026-09-01", "DD/MM/YYYY"),
])
def test_fechas_formatos_validos(entrada, esperado, formato):
    assert interpretar_fecha(entrada) == (esperado, formato)


@pytest.mark.parametrize("entrada", ["31/02/2026", "ayer", "2026/09/01", "13/13/2026", "01-09-26", "", None,
                                     float("nan"), True, "1789105020000", "2026-09-01 10:00:00"])
def test_fechas_invalidas_dan_none(entrada):
    assert normalizar_fecha(entrada) is None


def test_fecha_dia_primero_no_se_confunde_con_mes():
    """01/09/2026 es 1 de septiembre (día primero), y 2026-09-01 no se invierte a 9 de enero."""
    assert normalizar_fecha("01/09/2026") == "2026-09-01"
    assert normalizar_fecha("2026-09-01") == "2026-09-01"


def test_epoch_zona_horaria_mexico_vs_utc():
    # 1789105020 = 2026-09-11 05:37 UTC = 2026-09-10 23:37 en Ciudad de México (UTC−6)
    assert normalizar_fecha(1789105020) == "2026-09-10"
    assert normalizar_fecha(1789105020, ZONA_UTC) == "2026-09-11"


def test_fechas_iso_con_hora_no_se_convierten_de_zona():
    assert normalizar_fecha("2026-10-12T23:59:59") == "2026-10-12"        # R8.4: ya es hora local


def test_normalizar_fechas_alertas_y_correcciones():
    df = df_minimo([{"fecha_cruda": "26/09/2026"}, {"fecha_cruda": "31/02/2026"}, {"fecha_cruda": None}])
    out = normalizar_fechas(df)
    assert out["fecha_venta"].tolist() == ["2026-09-26", None, None]
    assert out.loc[0, "correcciones"] == ["FECHA_DESDE_DD/MM/YYYY"] and out.loc[0, "alertas"] == []
    assert out.loc[1, "alertas"] == [ALERTA_FECHA_NO_INTERPRETABLE] and out.loc[1, "correcciones"] == []
    assert len(out) == 3 and out["fecha_cruda"].tolist()[:2] == ["26/09/2026", "31/02/2026"] and pd.isna(out.loc[2, "fecha_cruda"])
    assert df["correcciones"].map(len).sum() == 0                          # la entrada no se modifica


def test_normalizar_fechas_no_altera_fecha_cruda_ni_su_faltante():
    """`fecha_cruda` sale idéntica a la entrada (con pandas 3 el helper la crea como `str` con NaN; con pandas 2,
    como object con None) y `fecha_venta` usa None en ambos casos."""
    df = df_minimo([{"fecha_cruda": "26/09/2026"}, {"fecha_cruda": None}])
    out = normalizar_fechas(df)
    assert out["fecha_cruda"].equals(df["fecha_cruda"])
    assert out["fecha_venta"].tolist() == ["2026-09-26", None]


def test_homologacion_real_representa_faltantes_con_none(df_homologado):
    """Camino real: la homologación fuerza object/None, sin importar la versión de pandas."""
    assert df_homologado["fecha_cruda"].dtype == object
    assert df_homologado["fecha_cruda"].map(lambda v: v is None or isinstance(v, str)).all()


def test_todas_las_fechas_reales_se_interpretan(df_integrado):
    assert df_integrado["fecha_venta"].isna().sum() == 0
    assert df_integrado["fecha_venta"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()


def test_rangos_reales_no_usan_mixed(df_integrado):
    """El parseo `mixed`+dayfirst daría 2026-01-09 … 2026-12-10; el explícito, septiembre–octubre."""
    f = df_integrado[df_integrado["origen"] == "FISICA"]["fecha_venta"]
    o = df_integrado[df_integrado["origen"] == "ONLINE"]["fecha_venta"]
    assert (f.min(), f.max()) == ("2026-09-01", "2026-10-15")
    assert (o.min(), o.max()) == ("2026-09-01", "2026-10-16")


def test_cinco_formatos_reales(df_integrado):
    formatos = df_integrado["correcciones"].explode().loc[lambda s: s.fillna("").str.startswith("FECHA_DESDE_")]
    assert formatos.value_counts().to_dict() == {"FECHA_DESDE_DD/MM/YYYY": 208, "FECHA_DESDE_YYYY-MM-DD": 207,
                                                 "FECHA_DESDE_DD-MM-YYYY": 205, "FECHA_DESDE_ISO_DATETIME": 392,
                                                 "FECHA_DESDE_EPOCH": 208}


def test_epoch_utc_vs_mexico_cambia_49_fechas(etapa_limpieza):
    mx = normalizar_fechas(etapa_limpieza[0])["fecha_venta"]
    utc = normalizar_fechas(etapa_limpieza[0], ZONA_UTC)["fecha_venta"]
    assert (mx != utc).sum() == 49


def test_fecha_web_00005_y_web_00002(df_integrado):
    assert fila(df_integrado, "WEB-00005")["fecha_venta"] == "2026-09-10"
    assert fila(df_integrado, "WEB-00002")["fecha_venta"] == "2026-10-12"
    assert fila(df_integrado, "POS-2026-0001")["fecha_venta"] == "2026-09-13"
    assert fila(df_integrado, "POS-2026-0003")["fecha_venta"] == "2026-09-26"


# ----------------------------------------------------------------------------- moneda
def test_conversion_usd_ejemplos_reales(df_integrado):
    r = fila(df_integrado, "WEB-00002")
    assert (r["moneda_original"], r["precio_unitario_mxn"], r["tipo_cambio_aplicado"]) == ("USD", 3307.01, 19.5)
    assert fila(df_integrado, "WEB-00237")["precio_unitario_mxn"] == 4218.05
    r = fila(df_integrado, "WEB-00003")
    assert (r["moneda_original"], r["precio_unitario_mxn"], r["tipo_cambio_aplicado"]) == ("MXN", 1228.72, 1.0)


def test_usd_vs_catalogo(df_integrado):
    usd = df_integrado[(df_integrado["moneda_original"] == "USD") & df_integrado["en_catalogo"]]
    assert len(usd) == 180 and usd["dif_precio_catalogo"].max() <= 0.10 + 1e-9
    mxn = df_integrado[(df_integrado["moneda_original"] == "MXN") & df_integrado["en_catalogo"]]
    assert mxn["dif_precio_catalogo"].max() < 1e-9


def test_193_conversiones_y_originales_intactos(df_integrado):
    usd = df_integrado[df_integrado["moneda_original"] == "USD"]
    assert len(usd) == 193
    assert usd["correcciones"].map(lambda c: "CONVERTIDO_USD_MXN" in c).all()
    assert (usd["moneda"] == "USD").all()                  # `moneda` y `precio_unitario` siguen en origen
    assert fila(df_integrado, "WEB-00002")["precio_unitario"] == 169.59


@pytest.mark.parametrize("precio, cantidad, esperado_precio, esperado_monto", [
    (169.59, 2, 3307.01, 6614.02),      # 3307.005 exacto → HALF_UP (con float puro podría dar 3307.00)
    (1.005, 1, 19.60, 19.60),           # 1.005 × 19.5 = 19.5975
    (0.01, 3, 0.20, 0.60),              # 0.195 → 0.20
])
def test_usd_redondeo_decimal_half_up(precio, cantidad, esperado_precio, esperado_monto):
    df = df_minimo([{"moneda": "USD", "precio_unitario": precio, "cantidad": float(cantidad),
                     "monto_total": precio * cantidad}])
    out = convertir_a_mxn(df)
    assert (out.loc[0, "precio_unitario_mxn"], out.loc[0, "monto_total_mxn"]) == (esperado_precio, esperado_monto)


def test_monto_desde_precio_convertido_no_desde_total():
    df = df_minimo([{"moneda": "USD", "precio_unitario": 169.59, "cantidad": 2.0, "monto_total": 339.18}])
    assert convertir_a_mxn(df).loc[0, "monto_total_mxn"] == 6614.02       # no 6614.01


def test_monto_solo_con_total_y_sin_cantidad():
    df = df_minimo([{"moneda": "USD", "precio_unitario": float("nan"), "cantidad": float("nan"), "monto_total": 10.0}])
    out = convertir_a_mxn(df)
    assert out.loc[0, "monto_total_mxn"] == 195.0 and pd.isna(out.loc[0, "precio_unitario_mxn"])


def test_moneda_desconocida_alerta_y_sin_inventar_tipo_de_cambio():
    out = convertir_a_mxn(df_minimo([{"moneda": "EUR"}, {"moneda": "MXN"}]))
    assert out.loc[0, "alertas"] == [ALERTA_MONEDA_NO_SOPORTADA]
    assert pd.isna(out.loc[0, "tipo_cambio_aplicado"]) and pd.isna(out.loc[0, "monto_total_mxn"])
    assert out.loc[1, "alertas"] == []


def test_paridad_parametrizable():
    from decimal import Decimal
    out = convertir_a_mxn(df_minimo([{"moneda": "USD", "precio_unitario": 10.0}]), paridad=Decimal("20"))
    assert out.loc[0, "precio_unitario_mxn"] == 200.0


# ----------------------------------------------------------------------------- catálogo
def test_huerfanos_por_canal(df_integrado):
    h = huerfanos(df_integrado)
    assert h["origen"].value_counts().to_dict() == {"ONLINE": 33, "FISICA": 29}
    assert h["nombre_producto"].isna().all() and h["precio_catalogo_mxn"].isna().all()
    assert h.loc[h["origen"] == "FISICA", "id_producto"].str.startswith("PROD-9").all()
    assert h.loc[h["origen"] == "ONLINE", "id_producto"].str.startswith("PROD-8").all()
    assert not fila(df_integrado, "POS-2026-0017")["en_catalogo"]


def test_producto_en_catalogo_trae_nombre_y_categoria(df_integrado):
    r = fila(df_integrado, "WEB-00002")
    assert r["en_catalogo"] and r["id_producto"] == "PROD-041" and r["nombre_producto"] and r["categoria"]


def test_merge_no_duplica_filas(etapa_limpieza, fuentes):
    antes = convertir_a_mxn(etapa_limpieza[0])
    assert len(cruzar_catalogo(antes, fuentes["catalogo"])) == len(antes) == 1220


def test_catalogo_con_id_repetido_falla_en_lugar_de_duplicar(etapa_limpieza, fuentes):
    cat = pd.concat([fuentes["catalogo"], fuentes["catalogo"].iloc[[0]]], ignore_index=True)
    with pytest.raises(pd.errors.MergeError):
        cruzar_catalogo(convertir_a_mxn(etapa_limpieza[0]), cat)


def test_catalogo_normaliza_ids_con_espacios_y_minusculas():
    df = convertir_a_mxn(df_minimo([{"id_producto": "PROD-001"}]))
    cat = pd.DataFrame({"id_producto": [" prod-001 "], "nombre_producto": ["X"], "categoria": ["C"],
                        "precio_base_mxn": [100.0]})
    assert cruzar_catalogo(df, cat).loc[0, "en_catalogo"]


def test_alerta_si_precio_difiere_mas_de_50_centavos():
    df = convertir_a_mxn(df_minimo([{"precio_unitario": 100.0}, {"precio_unitario": 100.3}]))
    cat = pd.DataFrame({"id_producto": ["PROD-001"], "nombre_producto": ["X"], "categoria": ["C"],
                        "precio_base_mxn": [99.0]})
    out = cruzar_catalogo(df, cat)
    assert out.loc[0, "alertas"] == [ALERTA_PRECIO_DIFIERE_CATALOGO]
    assert out.loc[1, "alertas"] == [ALERTA_PRECIO_DIFIERE_CATALOGO]
    assert cruzar_catalogo(df, cat.assign(precio_base_mxn=100.1)).loc[0, "alertas"] == []


# ----------------------------------------------------------------------------- Min-Max
def test_minmax_rango_y_extremos_de_la_base(etapa_transformada):
    df, par = etapa_transformada
    mm = df["monto_minmax"].astype(float)
    assert mm.between(0, 1).all() and len(df) == 1220
    en_base = df["es_base_estadistica"]
    assert mm[en_base].min() == 0.0 and mm[en_base].max() == 1.0
    assert (par["minmax"]["min"], par["minmax"]["max"]) == (332.67, 12032.68)
    assert par["minmax"]["n_base"] == 1129


def test_minmax_ejemplos_de_referencia(etapa_transformada):
    df, _ = etapa_transformada
    esperado = {"POS-2026-0001": 0.0764, "WEB-00002": 0.2542, "WEB-00237": 0.3321, "POS-2026-0031": 0.6731,
                "WEB-00508": 0.8544, "POS-2026-0021": 1.0}
    for id_, valor in esperado.items():
        assert round(float(fila(df, id_)["monto_minmax"]), 4) == valor, id_


def test_minmax_registros_invalidos_acotados_y_marcados(etapa_transformada):
    df, _ = etapa_transformada
    invalidos = df[pd.to_numeric(df["cantidad"], errors="coerce") <= 0]
    assert len(invalidos) == 11
    assert invalidos["monto_minmax"].astype(float).between(0, 1).all()
    assert invalidos["minmax_recortado"].any()
    assert df["minmax_recortado"].sum() == 11 and not df.loc[df["es_base_estadistica"], "minmax_recortado"].any()


def test_minmax_no_usa_duplicados_ni_huerfanos_para_min_max(etapa_transformada):
    df, par = etapa_transformada
    todos = df["monto_total_mxn_cap"]
    assert todos.min() < par["minmax"]["min"]            # hay valores fuera de la base (inválidos), no mueven el mínimo


def test_minmax_matematica_basica():
    df = pd.DataFrame({"monto_total_mxn_cap": [10.0, 20.0, 30.0, 40.0, 100.0, -5.0, None]})
    base = pd.Series([True, True, True, True, False, False, False])
    out, par = escalar_min_max(df, base=base)
    assert out["monto_minmax"].iloc[:4].tolist() == [0.0, round(1 / 3, 6), round(2 / 3, 6), 1.0]
    assert out["monto_minmax"].iloc[4] == 1.0 and out["monto_minmax"].iloc[5] == 0.0   # acotados
    assert out["monto_minmax"].iloc[6] is None                                          # sin importe → None
    assert out["minmax_recortado"].tolist() == [False] * 4 + [True, True, False]
    assert (par["min"], par["max"]) == (10.0, 40.0)


def test_minmax_constante_no_divide_entre_cero():
    df = pd.DataFrame({"monto_total_mxn_cap": [50.0, 50.0, 50.0]})
    out, par = escalar_min_max(df)
    assert out["monto_minmax"].tolist() == [0.0, 0.0, 0.0] and par["constante"] is True


def test_minmax_un_solo_registro_en_la_base():
    df = pd.DataFrame({"monto_total_mxn_cap": [50.0, 80.0]})
    out, par = escalar_min_max(df, base=pd.Series([True, False]))
    assert par["constante"] and out["monto_minmax"].tolist() == [0.0, 0.0]


def test_minmax_base_vacia_deja_none():
    df = pd.DataFrame({"monto_total_mxn_cap": [50.0, 80.0]})
    out, par = escalar_min_max(df, base=pd.Series([False, False]))
    assert par["min"] is None and out["monto_minmax"].tolist() == [None, None]


def test_minmax_ignora_infinitos():
    df = pd.DataFrame({"monto_total_mxn_cap": [1.0, 3.0, float("inf")]})
    out, par = escalar_min_max(df)
    assert par["max"] == 3.0 and out["monto_minmax"].iloc[2] is None


# ----------------------------------------------------------------------------- discretización
def test_segmentos_reales(etapa_transformada):
    df, par = etapa_transformada
    seg = par["segmentos"]
    assert round(seg["corte_bajo_medio"], 2) == 2069.07 and round(seg["corte_medio_alto"], 2) == 4183.67
    assert seg["conteo_base"] == {"Bajo": 380, "Medio": 374, "Alto": 375}
    assert set(df["segmento_importe"].unique()) == {"Bajo", "Medio", "Alto"}
    assert df["segmento_importe"].notna().all()


def test_segmentos_ejemplos(etapa_transformada):
    df, _ = etapa_transformada
    assert fila(df, "POS-2026-0001")["segmento_importe"] == "Bajo"
    assert fila(df, "WEB-00002")["segmento_importe"] == "Medio"
    assert fila(df, "WEB-00237")["segmento_importe"] == "Alto"


def test_segmentos_respetan_limites_inclusivos():
    df = pd.DataFrame({"monto_total_mxn_cap": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    out, par = discretizar_importe(df)
    assert par["corte_bajo_medio"] == pytest.approx(8 / 3) and par["corte_medio_alto"] == pytest.approx(13 / 3)
    assert out["segmento_importe"].tolist() == ["Bajo", "Bajo", "Medio", "Medio", "Alto", "Alto"]
    # un valor exactamente igual al corte pertenece al segmento inferior (límite superior inclusivo)
    cortes = pd.DataFrame({"monto_total_mxn_cap": [10.0, 20.0, 30.0]})
    out, par = discretizar_importe(cortes)
    assert par["corte_bajo_medio"] == pytest.approx(16.6666667) and par["corte_medio_alto"] == pytest.approx(23.3333333)
    exacto = pd.DataFrame({"monto_total_mxn_cap": [par["corte_bajo_medio"], par["corte_medio_alto"]]})
    assert discretizar_importe(exacto, base=pd.Series([False, False]))[0]["segmento_importe"].isna().all()
    ref = pd.concat([cortes, exacto], ignore_index=True)
    res, _ = discretizar_importe(ref, base=pd.Series([True] * 3 + [False] * 2))
    assert res["segmento_importe"].iloc[3:].tolist() == ["Bajo", "Medio"]


def test_segmentos_con_valores_repetidos_no_fallan():
    df = pd.DataFrame({"monto_total_mxn_cap": [10.0] * 9})
    out, par = discretizar_importe(df)
    assert par["corte_bajo_medio"] == par["corte_medio_alto"] == 10.0
    assert set(out["segmento_importe"]) == {"Bajo"}


def test_segmentos_nan_y_base_vacia():
    df = pd.DataFrame({"monto_total_mxn_cap": [1.0, 2.0, 3.0, None]})
    out, _ = discretizar_importe(df)
    assert out["segmento_importe"].iloc[3] is None
    vacio, par = discretizar_importe(df, base=pd.Series([False] * 4))
    assert vacio["segmento_importe"].tolist() == [None] * 4 and par["corte_bajo_medio"] is None


# ----------------------------------------------------------------------------- etapa F5 completa y trazabilidad
def test_transformar_conserva_filas_y_columnas_de_leslie(etapa_transformada, etapa_outliers):
    df, _ = etapa_transformada
    leslie, _ = etapa_outliers
    assert len(df) == 1220
    assert set(COLUMNAS_AGREGA_OUTLIERS + COLUMNAS_AGREGA_TRANSFORMACION + COLUMNAS_AGREGA_FECHAS) <= set(df.columns)
    for col in ["cantidad_origen", "monto_total_origen", "monto_cantidad_cap_mxn", "monto_total_mxn_cap",
                "cantidad_cap", "es_base_estadistica", "registro_original"]:
        pd.testing.assert_series_equal(df[col], leslie[col], check_names=False)


def test_valores_originales_trazables(etapa_transformada):
    df, _ = etapa_transformada
    r = fila(df, "POS-2026-0031")
    assert (r["cantidad_origen"], r["cantidad_cap"]) == (500.0, 8.0)
    assert json.loads(r["registro_original"])["cantidad"] == "500"
    r = fila(df, "WEB-00508")
    assert r["monto_total_origen"] == 826360.8 and r["monto_total_mxn_cap"] == 10329.51


def test_cuarentena_no_pierde_registros(etapa_transformada):
    """Duplicados, cantidad ≤ 0 y huérfanos siguen presentes y marcados para Nono."""
    df, _ = etapa_transformada
    assert df["es_duplicado"].sum() == 20
    assert (pd.to_numeric(df["cantidad"]) <= 0).sum() == 11
    assert (~df["en_catalogo"]).sum() == 62


def test_transformar_exige_columnas(df_homologado):
    with pytest.raises(ErrorContrato):
        transformar(df_homologado)


# ----------------------------------------------------------------------------- extracción robusta
def test_csv_con_bom_se_lee(tmp_path):
    ruta = tmp_path / "v.csv"
    ruta.write_bytes(("\ufeffid_ticket,cantidad\nT1,2\n").encode("utf-8"))
    df = leer_csv_ventas(ruta, ["id_ticket", "cantidad"])
    assert "id_ticket" in df.columns and df.loc[0, "id_ticket"] == "T1" and df.loc[0, "cantidad"] == "2"


def test_csv_vacio_y_csv_sin_columnas_son_error_controlado(tmp_path):
    vacio = tmp_path / "vacio.csv"
    vacio.write_text("", encoding="utf-8")
    with pytest.raises(ErrorExtraccion):
        leer_csv_ventas(vacio, ["id_ticket"])
    parcial = tmp_path / "parcial.csv"
    parcial.write_text("id_ticket\nT1\n", encoding="utf-8")
    with pytest.raises(ErrorExtraccion, match="faltan columnas"):
        leer_csv_ventas(parcial, ["id_ticket", "cantidad"])


def test_archivo_inexistente_es_error_controlado(tmp_path):
    with pytest.raises(ErrorExtraccion, match="No existe"):
        leer_csv_ventas(tmp_path / "no.csv", ["a"])
    with pytest.raises(ErrorExtraccion, match="No existe"):
        leer_catalogo(tmp_path / "no.csv")


def test_catalogo_ilegible_o_con_ids_repetidos(tmp_path):
    malo = tmp_path / "cat.csv"
    malo.write_text("id_producto,nombre_producto,categoria,precio_base_mxn,stock_minimo,proveedor\n"
                    "P1,a,c,1,1,x\n p1 ,b,c,1,1,x\n", encoding="utf-8")
    with pytest.raises(ErrorExtraccion, match="repetidos"):
        leer_catalogo(malo)
    vacio = tmp_path / "v.csv"
    vacio.write_text("", encoding="utf-8")
    with pytest.raises(ErrorExtraccion):
        leer_catalogo(vacio)


def test_json_con_bom_y_objeto_no_lista(tmp_path):
    from src.extraccion import leer_json_ventas
    bom = tmp_path / "b.json"
    bom.write_bytes("﻿[{\"order_id\": \"W1\"}]".encode("utf-8"))
    assert leer_json_ventas(bom, ["order_id"]).loc[0, "order_id"] == "W1"
    objeto = tmp_path / "o.json"
    objeto.write_text('{"order_id": "W1"}', encoding="utf-8")
    with pytest.raises(ErrorExtraccion, match="lista de objetos"):
        leer_json_ventas(objeto, ["order_id"])


# ----------------------------------------------------------------------------- R8.2: por qué NO se usa lectura genérica
def test_lectura_generica_dayfirst_leeria_mal_104_fechas(df_integrado):
    """Evidencia de R8.2: dateutil con dayfirst=True invierte día y mes en las fechas ISO (104 de 620)."""
    from dateutil import parser
    fis = df_integrado[df_integrado["origen"] == "FISICA"]
    generico = fis["fecha_cruda"].map(lambda t: parser.parse(t, dayfirst=True).strftime("%Y-%m-%d"))
    assert (generico != fis["fecha_venta"]).sum() == 104
    assert (generico.min(), generico.max()) == ("2026-01-09", "2026-12-10")


def test_codigo_fuente_no_llama_a_to_datetime():
    """R8.2 por análisis del código (AST): ninguna llamada a to_datetime; los docstrings no cuentan."""
    import ast
    from pathlib import Path
    for ruta in (Path(__file__).resolve().parent.parent / "src").rglob("*.py"):
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call):
                nombre = getattr(nodo.func, "attr", getattr(nodo.func, "id", ""))
                assert nombre != "to_datetime", f"{ruta.name}:{nodo.lineno} llama a to_datetime (R8.2)"
