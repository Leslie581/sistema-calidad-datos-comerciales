"""
F1 · Diagnóstico de calidad (responsable: Leslie).

Funciones reutilizables para medir la calidad ANTES (archivos crudos) y DESPUÉS
(salida de cada etapa): completitud, unicidad, tipos, faltantes MCAR/MAR y
métricas de negocio (montos inconsistentes, cantidades imposibles, asimetría).
Ninguna función modifica su entrada.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

try:
    from scipy.stats import chi2_contingency
except ImportError:  # scipy es opcional: sin ella se reportan solo los porcentajes
    chi2_contingency = None

from ..config import TOLERANCIA_MONTO

COLUMNAS_TECNICAS = {"id_fila_origen", "registro_original", "alertas", "correcciones"}
ALFA = 0.05


# ----------------------------------------------------------------------------- utilidades
def es_vacio(serie: pd.Series) -> pd.Series:
    """True si el valor es nulo, NaN, o texto vacío / solo espacios."""
    texto = serie.astype(object).map(lambda v: isinstance(v, str) and v.strip() == "")
    return serie.isna() | texto


def inferir_tipo(serie: pd.Series) -> str:
    """Tipo lógico de los valores no vacíos: entero, decimal, texto, mixto(...) o vacío."""
    valores = serie[~es_vacio(serie)]
    if valores.empty:
        return "vacío"
    tipos_python = sorted({type(v).__name__ for v in valores})
    if len(tipos_python) > 1 and not set(tipos_python) <= {"int", "float"}:
        return f"mixto({', '.join(tipos_python)})"
    numeros = pd.to_numeric(valores.astype(str).str.strip(), errors="coerce")
    if numeros.notna().all():
        return "entero" if (numeros % 1 == 0).all() else "decimal"
    if numeros.notna().any():
        return "texto con valores numéricos"
    return "texto"


def _redondear(x, n=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(float(x), n)


# ----------------------------------------------------------------------------- perfil por archivo
def perfilar_dataframe(df: pd.DataFrame, nombre: str) -> dict:
    """Completitud, unicidad y tipos de un DataFrame (sin contar columnas técnicas)."""
    columnas = [c for c in df.columns if c not in COLUMNAS_TECNICAS]
    datos = df[columnas]
    filas = len(datos)
    nulos = {c: int(es_vacio(datos[c]).sum()) for c in columnas}
    celdas = filas * len(columnas)
    hashable = datos.astype(str)
    return {
        "fuente": nombre,
        "filas": filas,
        "columnas": len(columnas),
        "tipos": {c: inferir_tipo(datos[c]) for c in columnas},
        "dtypes_pandas": {c: str(t) for c, t in datos.dtypes.items()},
        "nulos": nulos,
        "pct_nulos": {c: _redondear(v / filas * 100) if filas else 0.0 for c, v in nulos.items()},
        "completitud_pct": {c: _redondear((1 - v / filas) * 100) if filas else 100.0 for c, v in nulos.items()},
        "completitud_global_pct": _redondear((1 - sum(nulos.values()) / celdas) * 100) if celdas else 100.0,
        "duplicados_exactos": int(hashable.duplicated().sum()),
        "valores_distintos": {c: int(hashable.loc[~es_vacio(datos[c]), c].nunique()) for c in columnas},
    }


def perfilar_fuentes(fuentes: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Perfil 'ANTES' de cada archivo tal como se extrajo."""
    return {nombre: perfilar_dataframe(df, nombre) for nombre, df in fuentes.items()}


def perfil_a_tabla(perfil: dict) -> pd.DataFrame:
    """Tabla columna | tipo | dtype | nulos | % nulos | completitud % | distintos (para el reporte)."""
    return pd.DataFrame({
        "columna": list(perfil["nulos"].keys()),
        "tipo_inferido": [perfil["tipos"][c] for c in perfil["nulos"]],
        "dtype_pandas": [perfil["dtypes_pandas"][c] for c in perfil["nulos"]],
        "nulos": list(perfil["nulos"].values()),
        "pct_nulos": list(perfil["pct_nulos"].values()),
        "completitud_pct": list(perfil["completitud_pct"].values()),
        "valores_distintos": [perfil["valores_distintos"][c] for c in perfil["nulos"]],
    })


# ----------------------------------------------------------------------------- MCAR / MAR
def clasificar_faltantes(df: pd.DataFrame, col_faltante: str, cols_grupo: list[str]) -> dict:
    """Prueba χ² del indicador 'falta' contra cada variable categórica observada.

    p >= 0.05 en todas → MCAR (no hay evidencia de dependencia).
    p <  0.05 en alguna → MAR respecto a esa(s) variable(s).
    MNAR no puede probarse con datos observados (se declara como supuesto).
    """
    falta = es_vacio(df[col_faltante])
    resultado = {"columna": col_faltante, "faltantes": int(falta.sum()),
                 "pct_faltantes": _redondear(falta.mean() * 100), "pruebas": []}
    dependientes = []
    for grupo in cols_grupo:
        g = df[grupo].astype(object).where(df[grupo].notna(), "(nulo)")
        prueba = {"vs": grupo,
                  "pct_faltante_por_grupo": {str(k): _redondear(v * 100, 1)
                                             for k, v in falta.groupby(g).mean().items()}}
        tabla = pd.crosstab(g, falta)
        if chi2_contingency is not None and tabla.shape == (tabla.shape[0], 2) and tabla.shape[0] > 1:
            chi2, p, gl, esperados = chi2_contingency(tabla)
            prueba.update({"chi2": _redondear(chi2, 4), "gl": int(gl), "p_valor": _redondear(p, 4),
                           "esperados_menores_5": int((esperados < 5).sum())})
            if p < ALFA:
                dependientes.append(grupo)
        else:
            prueba["nota"] = "sin prueba χ² (scipy ausente o sin variación)"
        resultado["pruebas"].append(prueba)
    con_p = [p for p in resultado["pruebas"] if "p_valor" in p]
    if resultado["faltantes"] == 0:
        resultado["clasificacion"] = "SIN_FALTANTES"
    elif not con_p:
        resultado["clasificacion"] = "NO_DETERMINADA"
    else:
        resultado["clasificacion"] = f"MAR({', '.join(dependientes)})" if dependientes else "MCAR"
    return resultado


def clasificar_faltantes_por_canal(df_homologado: pd.DataFrame) -> list[dict]:
    """Aplica clasificar_faltantes a las columnas con ausencias reales de cada canal."""
    plan = {
        "FISICA": {"id_cliente": ["punto_venta", "metodo_pago"],
                   "monto_total": ["punto_venta", "metodo_pago"]},
        "ONLINE": {"email_cliente": ["metodo_pago", "moneda"],
                   "direccion_envio": ["estado_pedido", "metodo_pago"]},
    }
    salida = []
    for origen, columnas in plan.items():
        sub = df_homologado[df_homologado["origen"] == origen]
        for col, grupos in columnas.items():
            r = clasificar_faltantes(sub, col, grupos)
            r["origen"] = origen
            salida.append(r)
    return salida


# ----------------------------------------------------------------------------- métricas de negocio
def asimetria(serie: pd.Series) -> float | None:
    s = pd.to_numeric(serie, errors="coerce").dropna()
    return _redondear(s.skew(), 4) if len(s) > 2 else None


def metricas_calidad(df: pd.DataFrame, columna_cantidad: str = "cantidad",
                     columna_monto: str = "monto_total") -> dict:
    """Métricas comparables antes/después sobre un DataFrame con esquema unificado."""
    cant = pd.to_numeric(df[columna_cantidad], errors="coerce")
    precio = pd.to_numeric(df["precio_unitario"], errors="coerce") if "precio_unitario" in df else None
    monto = pd.to_numeric(df[columna_monto], errors="coerce")
    m = {
        "filas": len(df),
        "duplicados_exactos": int(df["registro_original"].duplicated().sum()) if "registro_original" in df else None,
        "cantidad_nula": int(cant.isna().sum()),
        "cantidad_menor_igual_0": int((cant <= 0).sum()),
        "cantidad_max": _redondear(cant.max()),
        "cantidad_media": _redondear(cant.mean(), 4),
        "cantidad_mediana": _redondear(cant.median(), 4),
        "cantidad_asimetria": asimetria(cant),
        f"{columna_monto}_nulo": int(monto.isna().sum()),
        f"{columna_monto}_media": _redondear(monto.mean()),
        f"{columna_monto}_mediana": _redondear(monto.median()),
        f"{columna_monto}_max": _redondear(monto.max()),
        f"{columna_monto}_asimetria": asimetria(monto),
    }
    if precio is not None and columna_monto == "monto_total":
        valido = cant.notna() & precio.notna() & monto.notna()
        m["monto_inconsistente"] = int(((monto - cant * precio).abs() > TOLERANCIA_MONTO)[valido].sum())
    for col in ("id_cliente", "email_cliente", "direccion_envio"):
        if col in df:
            m[f"{col}_nulo"] = int(es_vacio(df[col]).sum())
    return m


def comparar_metricas(antes: dict, despues: dict, etiqueta_despues: str = "despues") -> pd.DataFrame:
    """Tabla métrica | antes | después | cambio."""
    filas = []
    for k in dict.fromkeys(list(antes) + list(despues)):
        a, d = antes.get(k), despues.get(k)
        cambio = None
        if isinstance(a, (int, float)) and isinstance(d, (int, float)):
            cambio = _redondear(d - a, 4)
        filas.append({"metrica": k, "antes": a, etiqueta_despues: d, "cambio": cambio})
    return pd.DataFrame(filas)
