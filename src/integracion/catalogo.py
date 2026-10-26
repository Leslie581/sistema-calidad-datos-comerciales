"""
Cruce con el catálogo maestro y detección de huérfanos (responsable: Yerik).

VERSIÓN MÍNIMA incorporada en la etapa de Leslie porque la base estadística del IQR
excluye productos huérfanos (R5.6). Yerik la revisa y la completa.
Reglas: [PROF] Fase 4 merge + huérfanos · [EQUIPO] R9.2 LEFT JOIN con bandera en_catalogo.
"""
from __future__ import annotations

import pandas as pd


def cruzar_catalogo(df: pd.DataFrame, catalogo: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN por id_producto: ninguna venta desaparece; los huérfanos quedan con en_catalogo=False."""
    cat = (catalogo[["id_producto", "nombre_producto", "categoria", "precio_base_mxn"]]
           .rename(columns={"precio_base_mxn": "precio_catalogo_mxn"}))
    out = df.merge(cat, on="id_producto", how="left", validate="many_to_one", indicator=True)
    out["en_catalogo"] = out["_merge"].eq("both")
    out["dif_precio_catalogo"] = (out["precio_unitario_mxn"] - out["precio_catalogo_mxn"]).abs()
    out = out.drop(columns="_merge")
    out.index = df.index
    for col in ("nombre_producto", "categoria"):
        out[col] = out[col].astype(object).where(out[col].notna(), None)
    assert len(out) == len(df), "El cruce con el catálogo no debe cambiar el número de filas"
    return out
