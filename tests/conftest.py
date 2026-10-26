"""Fixtures compartidas: los datasets OFICIALES se procesan una sola vez por sesión de pruebas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.calidad.limpieza import limpiar_registros  # noqa: E402
from src.calidad.outliers import tratar_outliers  # noqa: E402
from src.config import RUTA_DIAGNOSTICO  # noqa: E402
from src.extraccion import extraer_fuentes  # noqa: E402
from src.integracion.catalogo import cruzar_catalogo  # noqa: E402
from src.integracion.homologacion import homologar_columnas  # noqa: E402
from src.integracion.moneda import convertir_a_mxn  # noqa: E402


@pytest.fixture(scope="session")
def fuentes():
    return extraer_fuentes()


@pytest.fixture(scope="session")
def df_homologado(fuentes):
    return homologar_columnas(fuentes)


@pytest.fixture(scope="session")
def etapa_limpieza(df_homologado):
    return limpiar_registros(df_homologado)          # (df, bitacora)


@pytest.fixture(scope="session")
def df_mxn(etapa_limpieza, fuentes):
    df, _ = etapa_limpieza
    return cruzar_catalogo(convertir_a_mxn(df), fuentes["catalogo"])


@pytest.fixture(scope="session")
def etapa_outliers(df_mxn):
    return tratar_outliers(df_mxn)                    # (df, limites)


@pytest.fixture(scope="session")
def referencia():
    return json.loads(Path(RUTA_DIAGNOSTICO).read_text(encoding="utf-8"))


def fila(df: pd.DataFrame, id_transaccion: str, ocurrencia: int = 0) -> pd.Series:
    return df[df["id_transaccion"] == id_transaccion].iloc[ocurrencia]


def df_minimo(filas: list[dict]) -> pd.DataFrame:
    """DataFrame homologado mínimo para pruebas sintéticas (valores por omisión del contrato)."""
    base = {"id_transaccion": "POS-2026-9999", "origen": "FISICA", "id_fila_origen": 1, "fecha_cruda": "2026-09-01",
            "punto_venta": "Colima Centro", "id_producto": "PROD-001", "cantidad": 1.0, "precio_unitario": 100.0,
            "monto_total": 100.0, "moneda": "MXN", "id_cliente": "CTE-001", "email_cliente": None,
            "direccion_envio": None, "metodo_pago": "EFECTIVO", "estado_pedido": None}
    registros = []
    for i, f in enumerate(filas, start=1):
        r = {**base, "id_fila_origen": i, **f}
        r.setdefault("registro_original", json.dumps({k: r[k] for k in base}, default=str))
        r.setdefault("alertas", [])
        r.setdefault("correcciones", [])
        registros.append(r)
    df = pd.DataFrame(registros)
    for c in ("cantidad", "precio_unitario", "monto_total"):
        df[c] = df[c].astype("float64")
    return df
