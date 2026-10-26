"""
Homologación de columnas y tipos (responsable: Yerik · versión mínima para alimentar a Leslie).

Convierte las dos fuentes de ventas al esquema unificado de `contratos.COLUMNAS_HOMOLOGADAS`.
NO interpreta fechas (eso es F4) y NO elimina filas.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..config import ORIGEN_FISICA, ORIGEN_ONLINE, PUNTO_VENTA_ONLINE
from ..contratos import (ALERTA_CANTIDAD_NO_NUMERICA, ALERTA_MONTO_NO_NUMERICO, ALERTA_PRECIO_INVALIDO,
                         COLUMNAS_HOMOLOGADAS, MAPEO_FISICA, MAPEO_ONLINE)

COLUMNAS_NUMERICAS = {
    "cantidad": ALERTA_CANTIDAD_NO_NUMERICA,
    "precio_unitario": ALERTA_PRECIO_INVALIDO,
    "monto_total": ALERTA_MONTO_NO_NUMERICO,
}
COLUMNAS_MAYUSCULAS = ["metodo_pago", "estado_pedido", "moneda", "id_producto"]


def es_faltante(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    return isinstance(valor, str) and valor.strip() == ""


def a_numero(valor) -> float | None:
    """'3' → 3.0 · 2 → 2.0 · ''/None/NaN → None · 'dos'/True/inf → ValueError."""
    if es_faltante(valor):
        return None
    if isinstance(valor, bool):
        raise ValueError(f"booleano no es numérico: {valor!r}")
    numero = float(str(valor).strip()) if isinstance(valor, str) else float(valor)
    if math.isinf(numero) or math.isnan(numero):
        raise ValueError(f"valor no finito: {valor!r}")
    return numero


def _texto(valor, mayusculas: bool = False, minusculas: bool = False):
    if es_faltante(valor):
        return None
    t = str(valor).strip()
    return t.upper() if mayusculas else t.lower() if minusculas else t


def _homologar_fuente(df: pd.DataFrame, mapeo: dict, origen: str) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for destino, fuente in mapeo.items():
        out[destino] = df[fuente] if fuente is not None else None
    out["origen"] = origen
    out["id_fila_origen"] = df["id_fila_origen"].astype(int)
    out["registro_original"] = df["registro_original"]
    if origen == ORIGEN_FISICA:
        out["moneda"] = "MXN"
    else:
        out["punto_venta"] = PUNTO_VENTA_ONLINE
    return out.astype(object)


def homologar_columnas(fuentes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Concatena física + online con el esquema unificado (1 fila de salida por fila de entrada)."""
    partes = [_homologar_fuente(fuentes["fisica"], MAPEO_FISICA, ORIGEN_FISICA),
              _homologar_fuente(fuentes["online"], MAPEO_ONLINE, ORIGEN_ONLINE)]
    df = pd.concat(partes, ignore_index=True)

    alertas: list[list[str]] = [[] for _ in range(len(df))]
    for col, alerta in COLUMNAS_NUMERICAS.items():
        valores = []
        for i, v in enumerate(df[col]):
            try:
                valores.append(a_numero(v))
            except (TypeError, ValueError):
                valores.append(None)
                alertas[i].append(alerta)
        df[col] = pd.Series(valores, index=df.index, dtype="float64")

    for col in ["id_transaccion", "fecha_cruda", "punto_venta", "id_cliente", "direccion_envio"]:
        df[col] = df[col].map(_texto)
    for col in COLUMNAS_MAYUSCULAS:
        df[col] = df[col].map(lambda v: _texto(v, mayusculas=True))
    df["email_cliente"] = df["email_cliente"].map(lambda v: _texto(v, minusculas=True))

    df["alertas"] = alertas
    df["correcciones"] = [[] for _ in range(len(df))]
    # Columnas de texto como object con None (no NaN) para que Pydantic/sqlite las entiendan
    texto = [c for c in COLUMNAS_HOMOLOGADAS if c not in COLUMNAS_NUMERICAS and c not in ("alertas", "correcciones")]
    df[texto] = df[texto].astype(object).where(df[texto].notna(), None)
    df["id_fila_origen"] = df["id_fila_origen"].astype(np.int64)
    return df[COLUMNAS_HOMOLOGADAS]
