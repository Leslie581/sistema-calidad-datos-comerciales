"""
Conversión USD → MXN (responsable: Yerik).

VERSIÓN MÍNIMA incorporada en la etapa de Leslie únicamente porque el IQR del importe
debe calcularse en una sola moneda (ambigüedad A2). Yerik la revisa y la completa
(fechas y transformación quedan fuera de esta etapa).

Reglas: [PROF] paridad 19.50 · [EQUIPO] R7.2 precio y monto, R6.4 ROUND_HALF_UP, R7.5 moneda soportada.
"""
from __future__ import annotations

import math

import pandas as pd

from ..config import MONEDAS_SOPORTADAS, PARIDAD_USD_MXN, redondear
from ..contratos import ALERTA_MONEDA_NO_SOPORTADA, CORR_CONVERTIDO_USD


def tipo_cambio(moneda) -> float | None:
    if moneda == "MXN":
        return 1.0
    if moneda == "USD":
        return float(PARIDAD_USD_MXN)
    return None


def convertir_a_mxn(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega moneda_original, tipo_cambio_aplicado, precio_unitario_mxn y monto_total_mxn.

    precio_unitario_mxn = redondear(precio_unitario × tc)
    monto_total_mxn     = redondear(cantidad × precio_unitario_mxn)   (si hay cantidad y precio)
                        = redondear(monto_total × tc)                 (si solo hay monto)
    Se calcula desde el precio convertido para que monto = cantidad × precio sea exacto en MXN
    (convertir el total directo difiere en centavos en 55 pedidos reales).
    """
    df = df.copy()
    tcs = df["moneda"].map(tipo_cambio)
    precios, montos = [], []
    for c, p, m, tc in zip(df["cantidad"], df["precio_unitario"], df["monto_total"], tcs):
        if tc is None or (isinstance(tc, float) and math.isnan(tc)):
            precios.append(math.nan)
            montos.append(math.nan)
            continue
        p_mxn = redondear(p * tc) if pd.notna(p) else math.nan
        precios.append(p_mxn)
        if pd.notna(c) and pd.notna(p_mxn):
            montos.append(redondear(c * p_mxn))
        elif pd.notna(m):
            montos.append(redondear(m * tc))
        else:
            montos.append(math.nan)
    df["moneda_original"] = df["moneda"]
    df["tipo_cambio_aplicado"] = tcs.astype("float64")
    df["precio_unitario_mxn"] = pd.Series(precios, index=df.index, dtype="float64")
    df["monto_total_mxn"] = pd.Series(montos, index=df.index, dtype="float64")
    no_soportada = ~df["moneda"].isin(MONEDAS_SOPORTADAS)
    df["alertas"] = [a + [ALERTA_MONEDA_NO_SOPORTADA] if ns else list(a)
                     for a, ns in zip(df["alertas"], no_soportada)]
    convertido = df["moneda"].eq("USD")
    df["correcciones"] = [c + [CORR_CONVERTIDO_USD] if cv else list(c)
                          for c, cv in zip(df["correcciones"], convertido)]
    return df
