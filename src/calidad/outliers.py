"""
F3 · Outliers con IQR y capping / winsorizing (responsable: Leslie).

Reglas: [PROF] IQR = Q3 − Q1, factor 1.5, capping en lugar de eliminar, eliminar solo
cantidades <= 0 · [EQUIPO] R5.3–R5.7.

Diseño:
- Los límites se calculan SOLO con la base estadística (R5.6): no duplicado, sin conflicto
  de ID, cantidad > 0, producto en catálogo y precio en MXN válido.
- El recorte se aplica a las filas con cantidad > 0. Las filas con valores imposibles
  (cantidad <= 0 o nula) pasan sin cambio: no son atípicas sino inválidas, y Nono las rechaza.
- NO se sobrescriben columnas: `cantidad` y `monto_total_mxn` conservan el valor real;
  el tratamiento va en `cantidad_cap`, `monto_cantidad_cap_mxn` y `monto_total_mxn_cap` (R5.5).
- Se ejecuta DESPUÉS de convertir USD→MXN (ambigüedad A2).
"""
from __future__ import annotations

import math

import pandas as pd

from ..config import FACTOR_IQR, redondear
from ..contratos import (CORR_CAPPING_CANTIDAD, CORR_CAPPING_MONTO, REQUERIDAS_OUTLIERS,
                         verificar_columnas)
from .limpieza import agregar_codigo


def calcular_limites_iqr(serie: pd.Series, factor: float = FACTOR_IQR) -> dict:
    """Q1, Q3 (interpolación lineal de pandas), IQR, LI, LS y conteo de valores fuera de límites."""
    s = pd.to_numeric(serie, errors="coerce").dropna()
    if s.empty:
        return {"n": 0, "Q1": None, "Q3": None, "IQR": None, "LI": None, "LS": None,
                "outliers_inferiores": 0, "outliers_superiores": 0, "factor": factor}
    q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
    iqr = q3 - q1
    li, ls = q1 - factor * iqr, q3 + factor * iqr
    return {"n": int(len(s)), "Q1": q1, "Q3": q3, "IQR": iqr, "LI": li, "LS": ls,
            "outliers_inferiores": int((s < li).sum()), "outliers_superiores": int((s > ls).sum()),
            "min": float(s.min()), "max": float(s.max()), "media": float(s.mean()),
            "mediana": float(s.median()), "asimetria": float(s.skew()) if len(s) > 2 else None,
            "factor": factor}


def mascara_base_estadistica(df: pd.DataFrame) -> pd.Series:
    """R5.6: registros sin defecto estructural ya detectado (la usa también Yerik en F5)."""
    cant = pd.to_numeric(df["cantidad"], errors="coerce")
    precio = pd.to_numeric(df["precio_unitario_mxn"], errors="coerce")
    return (~df["es_duplicado"].astype(bool) & ~df["es_id_conflicto"].astype(bool)
            & (cant > 0) & df["en_catalogo"].astype(bool) & (precio > 0))


def aplicar_capping_cantidad(df: pd.DataFrame, factor: float = FACTOR_IQR) -> tuple[pd.DataFrame, dict]:
    """Capping de la cantidad POR CANAL. Tope = floor(LS) y piso = max(ceil(LI), 1): enteros."""
    df = df.copy()
    base = df["es_base_estadistica"] if "es_base_estadistica" in df else mascara_base_estadistica(df)
    cant = pd.to_numeric(df["cantidad"], errors="coerce")
    valida = cant > 0
    df["cantidad_cap"] = cant.astype("float64")
    df["es_outlier_cantidad"] = False
    limites = {}
    for origen in sorted(df["origen"].unique()):
        del_canal = df["origen"] == origen
        lim = calcular_limites_iqr(cant[base & del_canal], factor)
        if lim["n"] == 0:
            lim["nota"] = "sin base estadística: no se aplica capping"
            limites[origen] = lim
            continue
        tope = math.floor(lim["LS"])
        piso = max(math.ceil(lim["LI"]), 1)
        lim.update(tope_entero=tope, piso_entero=piso)
        aplicar = del_canal & valida
        df.loc[aplicar, "cantidad_cap"] = cant[aplicar].clip(lower=piso, upper=tope)
        df.loc[aplicar, "es_outlier_cantidad"] = (cant[aplicar] > lim["LS"]) | (cant[aplicar] < lim["LI"])
        lim["recortados"] = int((aplicar & (df["cantidad_cap"] != cant)).sum())
        limites[origen] = lim
    agregar_codigo(df, valida & (df["cantidad_cap"] != cant), CORR_CAPPING_CANTIDAD)
    df["es_outlier_cantidad"] = df["es_outlier_cantidad"].astype(bool)
    return df, limites


def aplicar_capping_monto(df: pd.DataFrame, factor: float = FACTOR_IQR) -> tuple[pd.DataFrame, dict]:
    """Capping del importe UNIFICADO en MXN sobre monto_cantidad_cap_mxn = cantidad_cap × precio_unitario_mxn."""
    df = df.copy()
    base = df["es_base_estadistica"] if "es_base_estadistica" in df else mascara_base_estadistica(df)
    cant_cap = pd.to_numeric(df["cantidad_cap"], errors="coerce")
    precio = pd.to_numeric(df["precio_unitario_mxn"], errors="coerce")
    df["monto_cantidad_cap_mxn"] = pd.Series(
        [redondear(c * p) if pd.notna(c) and pd.notna(p) else m
         for c, p, m in zip(cant_cap, precio, df["monto_total_mxn"])], index=df.index, dtype="float64")
    lim = calcular_limites_iqr(df.loc[base, "monto_cantidad_cap_mxn"], factor)
    valida = pd.to_numeric(df["cantidad"], errors="coerce") > 0
    monto = df["monto_cantidad_cap_mxn"]
    df["monto_total_mxn_cap"] = monto
    df["es_outlier_monto"] = False
    if lim["n"] > 0:
        piso = max(lim["LI"], 0.0)
        lim.update(piso_aplicado=piso, techo_aplicado=lim["LS"])
        aplicar = valida & monto.notna()
        recortado = monto[aplicar].clip(lower=piso, upper=lim["LS"]).map(redondear)
        df.loc[aplicar, "monto_total_mxn_cap"] = recortado
        df.loc[aplicar, "es_outlier_monto"] = (monto[aplicar] > lim["LS"]) | (monto[aplicar] < lim["LI"])
        cambio = aplicar & ((df["monto_total_mxn_cap"] - monto).abs() > 0.005)
        lim["recortados"] = int(cambio.sum())
        agregar_codigo(df, cambio, CORR_CAPPING_MONTO)
    df["es_outlier_monto"] = df["es_outlier_monto"].astype(bool)
    return df, lim


def tratar_outliers(df_integrado: pd.DataFrame, factor: float = FACTOR_IQR) -> tuple[pd.DataFrame, dict]:
    """Función de etapa F3. Entrada: salida de F4 (con precio en MXN y en_catalogo). Mismas filas."""
    verificar_columnas(df_integrado, REQUERIDAS_OUTLIERS, "F3 tratar_outliers")
    df = df_integrado.copy()
    df["es_base_estadistica"] = mascara_base_estadistica(df)
    df, lim_cantidad = aplicar_capping_cantidad(df, factor)
    df, lim_monto = aplicar_capping_monto(df, factor)
    assert len(df) == len(df_integrado), "F3 no debe cambiar el número de filas"
    base = df["es_base_estadistica"]
    return df, {
        "base_estadistica": {"total": int(base.sum()),
                             "por_canal": {str(k): int(v) for k, v in df.loc[base, "origen"].value_counts().items()}},
        "cantidad": lim_cantidad,
        "monto_mxn": lim_monto,
    }
