"""
Cruce con el catálogo maestro y detección de huérfanos (responsable: Yerik).

Reglas: [PROF] Fase 4 merge + huérfanos · [EQUIPO] R9.2 LEFT JOIN con bandera en_catalogo.
- LEFT JOIN: ninguna venta desaparece. Un producto huérfano queda con `en_catalogo = False` y sin
  nombre/categoría/precio de catálogo; Nono lo manda a cuarentena (REFERENCIA_HUERFANA).
- `validate="many_to_one"`: un id repetido en el catálogo falla en lugar de multiplicar ventas en silencio.
- Los ids del catálogo se normalizan igual que los de las ventas (strip + mayúsculas) para que el cruce
  no falle por espacios o minúsculas.
"""
from __future__ import annotations

import pandas as pd

from ..contratos import ALERTA_PRECIO_DIFIERE_CATALOGO

UMBRAL_DIF_PRECIO = 0.50   # MXN; por encima solo se emite una alerta informativa (no rechaza)


def huerfanos(df: pd.DataFrame) -> pd.DataFrame:
    """Filas cuyo producto no existe en el catálogo maestro."""
    return df[~df["en_catalogo"].astype(bool)]


def cruzar_catalogo(df: pd.DataFrame, catalogo: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN por id_producto: ninguna venta desaparece; los huérfanos quedan con en_catalogo=False."""
    cat = (catalogo[["id_producto", "nombre_producto", "categoria", "precio_base_mxn"]]
           .rename(columns={"precio_base_mxn": "precio_catalogo_mxn"}).copy())
    cat["id_producto"] = cat["id_producto"].astype(str).str.strip().str.upper()
    out = df.merge(cat, on="id_producto", how="left", validate="many_to_one", indicator=True)
    out["en_catalogo"] = out["_merge"].eq("both")
    out["dif_precio_catalogo"] = (out["precio_unitario_mxn"] - out["precio_catalogo_mxn"]).abs()
    out = out.drop(columns="_merge")
    out.index = df.index
    for col in ("nombre_producto", "categoria"):
        out[col] = out[col].astype(object).where(out[col].notna(), None)
    difiere = out["dif_precio_catalogo"] > UMBRAL_DIF_PRECIO
    out["alertas"] = [list(a) + [ALERTA_PRECIO_DIFIERE_CATALOGO] if d else list(a)
                      for a, d in zip(out["alertas"], difiere)]
    assert len(out) == len(df), "El cruce con el catálogo no debe cambiar el número de filas"
    return out
