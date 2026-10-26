"""
F5 · Escalamiento Min-Max y discretización del importe (responsable: Yerik).

Reglas: [PROF] R12.1 Min-Max a [0, 1] · R12.3 tres segmentos · [EQUIPO] R12.2 variable = `monto_total_mxn_cap`,
R12.4 terciles.

POBLACIÓN ESTADÍSTICA
    min, max y los cortes de los terciles se calculan SOLO con la base estadística de Leslie
    (`es_base_estadistica`: no duplicado, sin conflicto de ID, cantidad > 0, en catálogo y precio válido).
    Justificación: los duplicados repetirían ventas, y los registros de cuarentena (cantidad ≤ 0, huérfanos)
    no representan ventas reales; dejarlos entrar movería min/max y los cortes. Sobre la variable CON capping,
    porque sin él un solo bot (2.1 M) comprimiría al 99 % de las ventas cerca de 0.

REGISTROS FUERA DE LA BASE
    Se escalan con los parámetros de la base y se acotan a [0, 1] (`clip`), para que Nono no los rechace por
    un motivo falso (ESCALA_FUERA_DE_RANGO) además del motivo real. `minmax_recortado` marca esos casos.
    Si el importe es NaN (no hay nada que escalar) → `monto_minmax` y `segmento_importe` quedan en None.

DIVISIÓN POR CERO
    Si max == min (todos los importes de la base iguales, o un solo registro) el escalamiento no está definido:
    se asigna 0.0 y el resumen marca `constante: True`. Base vacía: min/max None y todo en None.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..contratos import REQUERIDAS_TRANSFORMACION, verificar_columnas

COLUMNA_IMPORTE = "monto_total_mxn_cap"
ETIQUETAS_SEGMENTO = ("Bajo", "Medio", "Alto")
DECIMALES_MINMAX = 6


def _referencia(df: pd.DataFrame, columna: str, base: pd.Series | None) -> pd.Series:
    valores = pd.to_numeric(df[columna], errors="coerce")
    if base is not None:
        valores = valores[base.reindex(df.index, fill_value=False).astype(bool)]
    return valores.replace([np.inf, -np.inf], np.nan).dropna()


def escalar_min_max(df: pd.DataFrame, columna: str = COLUMNA_IMPORTE,
                    base: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """x' = (x − min) / (max − min), con min y max de la base. Agrega `monto_minmax` y `minmax_recortado`."""
    ref = _referencia(df, columna, base)
    valores = pd.to_numeric(df[columna], errors="coerce").replace([np.inf, -np.inf], np.nan)
    df = df.copy()
    if ref.empty:
        df["monto_minmax"] = pd.Series([None] * len(df), index=df.index, dtype=object)
        df["minmax_recortado"] = False
        return df, {"columna": columna, "n_base": 0, "min": None, "max": None, "constante": False,
                    "fuera_de_base_recortados": 0}
    mn, mx = float(ref.min()), float(ref.max())
    constante = mx == mn
    escalado = pd.Series(0.0, index=df.index) if constante else (valores - mn) / (mx - mn)
    escalado = escalado.where(valores.notna())
    recortado = (escalado < 0) | (escalado > 1)
    df["monto_minmax"] = escalado.clip(0, 1).round(DECIMALES_MINMAX).astype(object).where(valores.notna(), None)
    df["minmax_recortado"] = recortado.fillna(False).astype(bool)
    return df, {"columna": columna, "n_base": int(len(ref)), "min": mn, "max": mx, "constante": bool(constante),
                "fuera_de_base_recortados": int(df["minmax_recortado"].sum())}


def discretizar_importe(df: pd.DataFrame, columna: str = COLUMNA_IMPORTE,
                        base: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """Bajo / Medio / Alto por terciles de la base: x ≤ c1 → Bajo · c1 < x ≤ c2 → Medio · x > c2 → Alto.

    Se asigna con comparaciones (no `pd.cut`) para tolerar cortes repetidos cuando hay muchos valores iguales.
    """
    ref = _referencia(df, columna, base)
    valores = pd.to_numeric(df[columna], errors="coerce").replace([np.inf, -np.inf], np.nan)
    df = df.copy()
    if ref.empty:
        df["segmento_importe"] = pd.Series([None] * len(df), index=df.index, dtype=object)
        return df, {"columna": columna, "n_base": 0, "corte_bajo_medio": None, "corte_medio_alto": None,
                    "conteo_base": {}}
    c1, c2 = (float(q) for q in ref.quantile([1 / 3, 2 / 3]))
    seg = pd.Series(np.select([valores <= c1, valores <= c2], ["Bajo", "Medio"], default="Alto"),
                    index=df.index, dtype=object)
    df["segmento_importe"] = seg.where(valores.notna(), None)
    en_base = df.loc[ref.index, "segmento_importe"].value_counts()
    return df, {"columna": columna, "n_base": int(len(ref)), "corte_bajo_medio": c1, "corte_medio_alto": c2,
                "conteo_base": {e: int(en_base.get(e, 0)) for e in ETIQUETAS_SEGMENTO}}


def transformar(df_outliers: pd.DataFrame, base: pd.Series | None = None) -> tuple[pd.DataFrame, dict]:
    """Función de etapa F5. Entrada: salida de `tratar_outliers` (+ `fecha_venta`). Mismas filas.

    `base` por omisión = `es_base_estadistica` de Leslie.
    """
    verificar_columnas(df_outliers, REQUERIDAS_TRANSFORMACION, "F5 transformar")
    if base is None:
        base = df_outliers["es_base_estadistica"].astype(bool)
    df, escala = escalar_min_max(df_outliers, base=base)
    df, cortes = discretizar_importe(df, base=base)
    assert len(df) == len(df_outliers), "F5 no debe cambiar el número de filas"
    return df, {"minmax": escala, "segmentos": cortes}
