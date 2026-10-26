"""
Extracción de las tres fuentes (responsable: Yerik · versión mínima para alimentar a Leslie).

Principios:
- Los archivos originales solo se LEEN (nunca se escriben).
- Las ventas se leen como TEXTO (CSV) o con su tipo Python original (JSON): ninguna
  conversión silenciosa. Cada etapa decide y registra sus conversiones.
- Cada fila recibe `id_fila_origen` (1 = primera fila de datos) y `registro_original`
  (JSON de la fila cruda) para trazabilidad y cuarentena.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .config import HUELLAS_SHA256, RUTAS_FUENTES
from .contratos import COLUMNAS_CATALOGO, COLUMNAS_FISICA, COLUMNAS_ONLINE


class ErrorExtraccion(Exception):
    """Un ARCHIVO no se puede leer (no un registro): el orquestador lo reporta como fallo controlado."""


def calcular_sha256(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def verificar_integridad(rutas: dict[str, Path] | None = None) -> dict[str, bool]:
    """Compara la huella de cada archivo con la registrada en el diagnóstico inicial."""
    rutas = rutas or RUTAS_FUENTES
    return {Path(r).name: calcular_sha256(r) == HUELLAS_SHA256.get(Path(r).name) for r in rutas.values()}


def _agregar_trazabilidad(df: pd.DataFrame, registros: list[dict]) -> pd.DataFrame:
    df = df.copy()
    df.insert(0, "id_fila_origen", range(1, len(df) + 1))
    df["registro_original"] = [json.dumps(r, ensure_ascii=False) for r in registros]
    return df


def leer_csv_ventas(ruta: Path, columnas_esperadas: list[str]) -> pd.DataFrame:
    if not Path(ruta).exists():
        raise ErrorExtraccion(f"No existe el archivo {ruta}")
    try:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False, encoding="utf-8")
    except Exception as e:  # CSV ilegible
        raise ErrorExtraccion(f"No se pudo leer {Path(ruta).name}: {e}") from e
    faltan = [c for c in columnas_esperadas if c not in df.columns]
    if faltan:
        raise ErrorExtraccion(f"{Path(ruta).name}: faltan columnas {faltan}")
    df = df.astype(object)
    registros = df.to_dict(orient="records")
    return _agregar_trazabilidad(df, registros)


def leer_json_ventas(ruta: Path, columnas_esperadas: list[str]) -> pd.DataFrame:
    if not Path(ruta).exists():
        raise ErrorExtraccion(f"No existe el archivo {ruta}")
    try:
        registros = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErrorExtraccion(f"{Path(ruta).name} no es un JSON válido: {e}") from e
    if not isinstance(registros, list) or not all(isinstance(r, dict) for r in registros):
        raise ErrorExtraccion(f"{Path(ruta).name}: se esperaba una lista de objetos")
    # Columnas ausentes en un registro quedan como None (faltante); columnas extra se conservan.
    columnas = list(dict.fromkeys(columnas_esperadas + [k for r in registros for k in r]))
    df = pd.DataFrame([{c: r.get(c) for c in columnas} for r in registros], columns=columnas, dtype=object)
    return _agregar_trazabilidad(df, registros)


def leer_catalogo(ruta: Path) -> pd.DataFrame:
    if not Path(ruta).exists():
        raise ErrorExtraccion(f"No existe el archivo {ruta}")
    df = pd.read_csv(ruta, encoding="utf-8", dtype={"id_producto": str})
    faltan = [c for c in COLUMNAS_CATALOGO if c not in df.columns]
    if faltan:
        raise ErrorExtraccion(f"{Path(ruta).name}: faltan columnas {faltan}")
    if df["id_producto"].duplicated().any():
        raise ErrorExtraccion("El catálogo maestro tiene id_producto repetidos")
    return df


def extraer_fuentes(rutas: dict[str, Path] | None = None) -> dict[str, pd.DataFrame]:
    """Devuelve {'catalogo', 'fisica', 'online'} sin interpretar valores de ventas."""
    rutas = rutas or RUTAS_FUENTES
    return {
        "catalogo": leer_catalogo(rutas["catalogo"]),
        "fisica": leer_csv_ventas(rutas["fisica"], COLUMNAS_FISICA),
        "online": leer_json_ventas(rutas["online"], COLUMNAS_ONLINE),
    }
