"""
F2 · Faltantes, imputación y reconstrucción de importes (responsable: Leslie).

Reglas aplicadas (REGLAS_DE_NEGOCIO.md): R2.3, R2.4 (duplicados), R3.3–R3.9 (imputación),
R6.1–R6.4 (reconstrucción de importes).

Principios:
- NO se eliminan filas: se corrige y se MARCA. Nono decide la cuarentena (R1.3).
- Toda corrección queda en la lista `correcciones` de la fila.
- Los valores originales se conservan: `cantidad_origen` y `monto_total_origen`.
- Todas las funciones son puras: devuelven una copia y no modifican su entrada.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from ..config import ETIQUETAS_CONTROLADAS, TOLERANCIA_MONTO, redondear
from ..contratos import (ALERTA_CANTIDAD_NO_NUMERICA, CORR_MEDIANA_CANTIDAD, CORR_MONTO_INCONSISTENTE,
                         CORR_MONTO_NULO, REQUERIDAS_LIMPIEZA, corr_imputado, verificar_columnas)
from .perfilado import es_vacio


# ----------------------------------------------------------------------------- utilidades
def agregar_codigo(df: pd.DataFrame, mascara: pd.Series, codigo: str, columna: str = "correcciones") -> None:
    """Agrega `codigo` a la lista de la columna en las filas indicadas (crea listas nuevas, sin aliasing)."""
    mascara = mascara.fillna(False).astype(bool)
    df[columna] = [lista + [codigo] if marcar else list(lista)
                   for lista, marcar in zip(df[columna], mascara)]


def contar_codigos(df: pd.DataFrame, columna: str = "correcciones") -> dict[str, int]:
    conteo: dict[str, int] = {}
    for lista in df[columna]:
        for codigo in lista:
            conteo[codigo] = conteo.get(codigo, 0) + 1
    return dict(sorted(conteo.items()))


def tiene_alerta(df: pd.DataFrame, alerta: str) -> pd.Series:
    return df["alertas"].map(lambda lista: alerta in lista).astype(bool)


# ----------------------------------------------------------------------------- R2.3 / R2.4 duplicados
def marcar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """es_duplicado: fila idéntica a una anterior del mismo canal (se conserva la primera).
    es_id_conflicto: mismo id_transaccion con contenido distinto (se marcan TODAS sus filas)."""
    df = df.copy()
    df["es_duplicado"] = df.duplicated(subset=["origen", "registro_original"], keep="first")
    unicos = df[~df["es_duplicado"]]
    contenidos = unicos.groupby(["origen", "id_transaccion"])["registro_original"].nunique()
    conflictos = set(contenidos[contenidos > 1].index)
    df["es_id_conflicto"] = [(o, i) in conflictos and not dup
                             for o, i, dup in zip(df["origen"], df["id_transaccion"], df["es_duplicado"])]
    return df


# ----------------------------------------------------------------------------- R3.5 mediana
def mediana_entera(serie: pd.Series) -> float | None:
    """Mediana redondeada al entero (ROUND_HALF_UP), porque la cantidad es discreta."""
    s = pd.to_numeric(serie, errors="coerce").dropna()
    if s.empty:
        return None
    return float(Decimal(str(s.median())).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def imputar_mediana(df: pd.DataFrame, columna: str = "cantidad") -> tuple[pd.DataFrame, dict]:
    """Imputa faltantes de `columna` con la mediana POR CANAL.

    Base de la mediana: filas no duplicadas con valor > 0 (en F2 aún no existe el cruce con
    el catálogo). NO imputa valores no numéricos (alerta CANTIDAD_NO_NUMERICA): son datos
    corruptos, no faltantes, y Nono los rechaza.
    """
    df = df.copy()
    if f"{columna}_origen" not in df:
        df[f"{columna}_origen"] = df[columna]
    valores = pd.to_numeric(df[columna], errors="coerce")
    no_duplicado = ~df["es_duplicado"] if "es_duplicado" in df else pd.Series(True, index=df.index)
    base = no_duplicado & (valores > 0)
    medianas = {origen: mediana_entera(valores[base & (df["origen"] == origen)])
                for origen in sorted(df["origen"].unique())}
    corrupto = tiene_alerta(df, ALERTA_CANTIDAD_NO_NUMERICA) if columna == "cantidad" else False
    faltante = valores.isna() & ~corrupto
    imputable = faltante & df["origen"].map(lambda o: medianas.get(o) is not None)
    df.loc[imputable, columna] = df.loc[imputable, "origen"].map(medianas).astype(float)
    agregar_codigo(df, imputable, CORR_MEDIANA_CANTIDAD if columna == "cantidad" else f"IMPUTADO_MEDIANA_{columna.upper()}")
    return df, {"medianas_por_canal": medianas, "imputados": int(imputable.sum()),
                "faltantes_no_imputables": int((faltante & ~imputable).sum()),
                "no_numericos_no_imputados": int(pd.Series(corrupto, index=df.index).sum())}


# ----------------------------------------------------------------------------- R6 importes
def recalcular_montos(df: pd.DataFrame, tolerancia: float = TOLERANCIA_MONTO) -> tuple[pd.DataFrame, dict]:
    """monto_total = cantidad × precio_unitario (en la MONEDA ORIGINAL; Yerik convierte después).

    - nulo y recalculable            → MONTO_RECALCULADO_NULO
    - |monto − cantidad×precio| > tol → MONTO_RECALCULADO_INCONSISTENTE
    Solo se recalcula si cantidad > 0 y precio > 0: con valores imposibles no hay nada que
    reconstruir y el registro irá a cuarentena. `monto_total_origen` conserva el dato crudo.
    """
    df = df.copy()
    if "monto_total_origen" not in df:
        df["monto_total_origen"] = df["monto_total"]
    cant = pd.to_numeric(df["cantidad"], errors="coerce")
    precio = pd.to_numeric(df["precio_unitario"], errors="coerce")
    monto = pd.to_numeric(df["monto_total"], errors="coerce")
    se_puede = cant.notna() & precio.notna() & (cant > 0) & (precio > 0)
    calculado = pd.Series([redondear(c * p) if ok else math.nan for c, p, ok in zip(cant, precio, se_puede)],
                          index=df.index, dtype="float64")
    nulo = monto.isna() & se_puede
    inconsistente = monto.notna() & se_puede & ((monto - calculado).abs() > tolerancia)
    corregir = nulo | inconsistente
    df["monto_total"] = monto.where(~corregir, calculado)
    agregar_codigo(df, nulo, CORR_MONTO_NULO)
    agregar_codigo(df, inconsistente, CORR_MONTO_INCONSISTENTE)
    factores = (monto[inconsistente] / calculado[inconsistente]).round(4).value_counts().to_dict()
    return df, {"recalculados_nulo": int(nulo.sum()), "recalculados_inconsistente": int(inconsistente.sum()),
                "factores_inconsistencia": {str(k): int(v) for k, v in factores.items()},
                "nulos_no_recalculables": int((monto.isna() & ~se_puede).sum())}


# ----------------------------------------------------------------------------- R3.7 / R3.8 categóricas
def imputar_categoricas(df: pd.DataFrame, etiquetas: dict = ETIQUETAS_CONTROLADAS) -> tuple[pd.DataFrame, dict]:
    """Etiquetas controladas SOLO en el canal donde la columna existe (R3.9)."""
    df = df.copy()
    conteo = {}
    for (origen, columna), etiqueta in etiquetas.items():
        mascara = (df["origen"] == origen) & es_vacio(df[columna])
        df.loc[mascara, columna] = etiqueta
        agregar_codigo(df, mascara, corr_imputado(columna))
        conteo[f"{origen}.{columna}→{etiqueta}"] = int(mascara.sum())
    return df, conteo


# ----------------------------------------------------------------------------- etapa F2
def limpiar_registros(df_homologado: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Función de etapa F2 (la llama el orquestador). Entrada y salida: mismas filas."""
    verificar_columnas(df_homologado, REQUERIDAS_LIMPIEZA, "F2 limpiar_registros")
    df = marcar_duplicados(df_homologado)
    df, b_mediana = imputar_mediana(df, "cantidad")
    df, b_montos = recalcular_montos(df)
    df, b_categoricas = imputar_categoricas(df)
    assert len(df) == len(df_homologado), "F2 no debe cambiar el número de filas"
    bitacora = {
        "filas": len(df),
        "duplicados_exactos": int(df["es_duplicado"].sum()),
        "ids_en_conflicto": int(df["es_id_conflicto"].sum()),
        "imputacion_mediana": b_mediana,
        "reconstruccion_montos": b_montos,
        "imputacion_categoricas": b_categoricas,
        "conteo_correcciones": contar_codigos(df),
    }
    return df, bitacora
