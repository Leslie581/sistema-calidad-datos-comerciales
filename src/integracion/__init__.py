"""Integración y transformación (responsable: Yerik)."""
from __future__ import annotations

import pandas as pd

from ..contratos import REQUERIDAS_INTEGRACION, verificar_columnas
from .catalogo import cruzar_catalogo
from .fechas import normalizar_fechas
from .moneda import convertir_a_mxn


def integrar(df_limpio: pd.DataFrame, catalogo: pd.DataFrame) -> pd.DataFrame:
    """Función de etapa F4: fechas ISO → USD→MXN → cruce con catálogo. Mismas filas que la entrada."""
    verificar_columnas(df_limpio, REQUERIDAS_INTEGRACION, "F4 integrar")
    df = normalizar_fechas(df_limpio)
    df = convertir_a_mxn(df)
    df = cruzar_catalogo(df, catalogo)
    assert len(df) == len(df_limpio), "La integración no debe cambiar el número de filas"
    return df
