"""
Conversión USD → MXN (responsable: Yerik).

Reglas: [PROF] paridad 19.50 · [EQUIPO] R7.2 precio y monto, R6.4 ROUND_HALF_UP, R7.5 moneda soportada.

Las multiplicaciones se hacen en `Decimal` (no en float) para que el redondeo financiero no dependa
de la representación binaria: p. ej. 169.59 × 19.50 = 3307.005 exacto → 3307.01.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from ..config import MONEDAS_SOPORTADAS, PARIDAD_USD_MXN
from ..contratos import ALERTA_MONEDA_NO_SOPORTADA, CORR_CONVERTIDO_USD

_CENTAVO = Decimal("0.01")


def _producto(a: float, b) -> float:
    """a × b en Decimal con redondeo a centavos HALF_UP."""
    return float((Decimal(str(a)) * Decimal(str(b))).quantize(_CENTAVO, rounding=ROUND_HALF_UP))


def tipo_cambio(moneda, paridad: Decimal = PARIDAD_USD_MXN) -> float | None:
    if moneda == "MXN":
        return 1.0
    if moneda == "USD":
        return float(paridad)
    return None


def convertir_a_mxn(df: pd.DataFrame, paridad: Decimal = PARIDAD_USD_MXN) -> pd.DataFrame:
    """Agrega moneda_original, tipo_cambio_aplicado, precio_unitario_mxn y monto_total_mxn.

    precio_unitario_mxn = redondear(precio_unitario × tc)
    monto_total_mxn     = redondear(cantidad × precio_unitario_mxn)   (si hay cantidad y precio)
                        = redondear(monto_total × tc)                 (si solo hay monto)
    Se calcula desde el precio convertido para que monto = cantidad × precio sea exacto en MXN
    (convertir el total directo difiere en centavos en 55 pedidos reales).
    Moneda ∉ {MXN, USD} → alerta MONEDA_NO_SOPORTADA y columnas MXN en NaN (no se inventa un tipo de cambio).
    Las columnas originales (`moneda`, `precio_unitario`, `monto_total`) no se modifican.
    """
    df = df.copy()
    tcs = df["moneda"].map(lambda m: tipo_cambio(m, paridad))
    precios, montos = [], []
    for c, p, m, tc in zip(df["cantidad"], df["precio_unitario"], df["monto_total"], tcs):
        if tc is None or (isinstance(tc, float) and math.isnan(tc)):
            precios.append(math.nan)
            montos.append(math.nan)
            continue
        p_mxn = _producto(p, tc) if pd.notna(p) else math.nan
        precios.append(p_mxn)
        if pd.notna(c) and pd.notna(p_mxn):
            montos.append(_producto(c, p_mxn))
        elif pd.notna(m):
            montos.append(_producto(m, tc))
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
