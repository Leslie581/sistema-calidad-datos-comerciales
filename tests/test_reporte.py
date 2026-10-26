"""Pruebas del reporte antes/después y de las diferencias documentadas frente a la referencia."""
import pandas as pd

from src.calidad.reporte import comparar_con_referencia, tabla_antes_despues


def _valor(tabla, metrica, columna):
    return tabla.loc[tabla["metrica"] == metrica, columna].iloc[0]


def test_tabla_antes_despues(df_homologado, etapa_outliers):
    t = tabla_antes_despues(df_homologado, etapa_outliers[0])
    esperado = {"Filas": (1220, 1220), "Montos nulos": (32, 0), "Montos ≠ cantidad × precio": (12, 0),
                "id_cliente faltante (física)": (127, 0), "Correo faltante (online)": (20, 0),
                "Dirección faltante (online)": (77, 0), "Cantidades ≤ 0": (11, 11),
                "Cantidad máxima (física)": (500, 8), "Importe MXN · máximo": (2109055.0, 12032.68)}
    for metrica, (antes, despues) in esperado.items():
        assert (_valor(t, metrica, "antes"), _valor(t, metrica, "despues")) == (antes, despues), metrica


def test_asimetria_baja_tras_capping(df_homologado, etapa_outliers):
    t = tabla_antes_despues(df_homologado, etapa_outliers[0])
    assert _valor(t, "Importe MXN · asimetría", "despues") < 2 < _valor(t, "Importe MXN · asimetría", "antes")


def test_diferencias_con_referencia_son_solo_las_documentadas(etapa_outliers, df_mxn, referencia):
    df, lim = etapa_outliers
    usd = df_mxn[(df_mxn["moneda_original"] == "USD") & df_mxn["en_catalogo"]]
    resultados = {"monto_recortados": lim["monto_mxn"]["recortados"],
                  "monto_outliers_base": lim["monto_mxn"]["outliers_superiores"],
                  "usd_dif_max_catalogo": round(float(usd["dif_precio_catalogo"].max()), 4),
                  "monto_ls": lim["monto_mxn"]["LS"]}
    t = comparar_con_referencia(resultados, referencia)
    t = t[t["obtenido"].notna()]
    difieren = set(t.loc[~t["coincide"], "metrica"])
    assert difieren == {"Montos recortados", "Diferencia máx. USD×19.50 vs catálogo"}
    assert (t.loc[~t["coincide"], "explicacion"].str.len() > 50).all()


def test_recortes_extra_son_duplicados(etapa_outliers):
    df = etapa_outliers[0]
    extra = df[df["correcciones"].map(lambda c: "CAPPING_IQR_MONTO" in c) & ~df["es_base_estadistica"]]
    assert len(extra) == 2 and extra["es_duplicado"].all()
    assert sorted(extra["id_fila_origen"]) == [608, 609]
    assert pd.Series(sorted(extra["id_transaccion"])).tolist() == ["POS-2026-0257", "POS-2026-0457"]
