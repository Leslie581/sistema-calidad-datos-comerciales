"""
F4 · Normalización de fechas a YYYY-MM-DD (responsable: Yerik).

Reglas: [PROF] R8.1 formato ISO · [EQUIPO] R8.2 parseo EXPLÍCITO por patrón (prohibido
`pd.to_datetime(format="mixed", dayfirst=True)`: lee mal 104 fechas) · R8.3 epoch · R8.4 ISO con hora · R8.5.

Formatos reconocidos (cada uno con su patrón; nada se "adivina"):
    YYYY-MM-DD · DD/MM/YYYY · DD-MM-YYYY · YYYY-MM-DDTHH:MM:SS · epoch Unix en segundos.

Zona horaria del epoch (ambigüedad A8, pendiente de confirmar con el docente):
    el epoch es, por definición, segundos desde 1970-01-01 00:00:00 UTC. El negocio opera en Colima
    (UTC−6, sin horario de verano desde 2022), así que el instante se convierte a `America/Mexico_City`
    ANTES de tomar la fecha. Cambia la fecha de 49 pedidos al día anterior respecto a usar UTC.
    Las fechas ISO con hora y las de solo fecha ya vienen en hora local: solo se descarta la hora (R8.4).
    Para usar UTC basta `normalizar_fechas(df, zona_epoch=ZONA_UTC)`.

Una fecha ilegible o imposible (31/02/2026) NO elimina la fila: queda `fecha_venta = None` y la alerta
`FECHA_NO_INTERPRETABLE`; Nono la manda a cuarentena con FECHA_INVALIDA.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from ..contratos import ALERTA_FECHA_NO_INTERPRETABLE, corr_fecha

ZONA_UTC = timezone.utc
try:
    ZONA_NEGOCIO: tzinfo = ZoneInfo("America/Mexico_City")
except ZoneInfoNotFoundError:   # Windows sin el paquete `tzdata`
    # Respaldo explícito: México central usa UTC−6 todo el año desde 2022 (válido para las fechas del dataset).
    ZONA_NEGOCIO = timezone(timedelta(hours=-6), "America/Mexico_City (UTC-6 fijo)")

# (nombre del formato, patrón estricto, formato strptime). `fullmatch` evita aceptar texto sobrante.
PATRONES = [
    ("YYYY-MM-DD", re.compile(r"\d{4}-\d{2}-\d{2}"), "%Y-%m-%d"),
    ("DD/MM/YYYY", re.compile(r"\d{2}/\d{2}/\d{4}"), "%d/%m/%Y"),
    ("DD-MM-YYYY", re.compile(r"\d{2}-\d{2}-\d{4}"), "%d-%m-%Y"),
    ("ISO_DATETIME", re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"), "%Y-%m-%dT%H:%M:%S"),
]
RE_EPOCH = re.compile(r"\d{9,11}(\.\d+)?")   # segundos (9–11 dígitos ≈ años 1973–5138); ms de 13 dígitos NO se aceptan
FORMATO_EPOCH = "EPOCH"


def _es_nulo(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def interpretar_fecha(valor, zona_epoch: tzinfo = ZONA_NEGOCIO) -> tuple[str | None, str | None]:
    """Devuelve (fecha ISO 'YYYY-MM-DD' | None, nombre del formato detectado | None)."""
    if _es_nulo(valor) or isinstance(valor, bool):
        return None, None
    texto = str(valor).strip()
    if RE_EPOCH.fullmatch(texto):
        try:
            instante = datetime.fromtimestamp(float(texto), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None, None
        return instante.astimezone(zona_epoch).date().isoformat(), FORMATO_EPOCH
    for nombre, patron, formato in PATRONES:
        if patron.fullmatch(texto):
            try:
                return datetime.strptime(texto, formato).date().isoformat(), nombre
            except ValueError:          # p. ej. 31/02/2026 o mes 13
                return None, None
    return None, None


def normalizar_fecha(valor, zona_epoch: tzinfo = ZONA_NEGOCIO) -> str | None:
    return interpretar_fecha(valor, zona_epoch)[0]


def normalizar_fechas(df: pd.DataFrame, zona_epoch: tzinfo = ZONA_NEGOCIO) -> pd.DataFrame:
    """Agrega `fecha_venta` (ISO o None) a partir de `fecha_cruda`, que se conserva intacta.

    Registra en `correcciones` el formato de origen (FECHA_DESDE_<formato>) y, si no se pudo
    interpretar, la alerta FECHA_NO_INTERPRETABLE. No cambia el número de filas.
    """
    df = df.copy()
    resultados = [interpretar_fecha(v, zona_epoch) for v in df["fecha_cruda"]]
    df["fecha_venta"] = pd.Series([r[0] for r in resultados], index=df.index, dtype=object)
    df["fecha_venta"] = df["fecha_venta"].astype(object).where(df["fecha_venta"].notna(), None)
    df["correcciones"] = [list(c) + [corr_fecha(fmt)] if fmt else list(c)
                          for c, (_, fmt) in zip(df["correcciones"], resultados)]
    df["alertas"] = [list(a) + [ALERTA_FECHA_NO_INTERPRETABLE] if iso is None else list(a)
                     for a, (iso, _) in zip(df["alertas"], resultados)]
    return df


def diagnostico_formatos(df: pd.DataFrame, zona_epoch: tzinfo = ZONA_NEGOCIO) -> pd.DataFrame:
    """Tabla (origen, formato, registros, fecha mínima, fecha máxima) para el reporte."""
    filas = []
    for origen, grupo in df.groupby("origen"):
        res = [interpretar_fecha(v, zona_epoch) for v in grupo["fecha_cruda"]]
        tmp = pd.DataFrame(res, columns=["fecha", "formato"]).fillna({"formato": "NO_INTERPRETABLE"})
        for formato, g in tmp.groupby("formato"):
            fechas = g["fecha"].dropna()
            filas.append({"origen": origen, "formato": formato, "registros": len(g),
                          "fecha_min": fechas.min() if len(fechas) else None,
                          "fecha_max": fechas.max() if len(fechas) else None})
    return pd.DataFrame(filas)
