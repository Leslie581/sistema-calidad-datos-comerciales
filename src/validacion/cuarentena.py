"""
F6 · Segregación de registros: conformes vs. zona de cuarentena (responsable: Nono).

Regla de oro (R1.3, R1.4): ningún registro se pierde. Cada fila de entrada termina en EXACTAMENTE uno de dos
lugares: `validos` (→ transacciones_limpias) o `cuarentena` (→ cuarentena_errores), con todos sus motivos
y el registro crudo. `validar_lote` comprueba la conservación y falla en voz alta si no cuadra.

Origen de los rechazos de un registro (columna `etapa_deteccion`):
- FASE_PREVIA: defectos que Leslie/Yerik MARCARON con banderas o alertas y que no son una excepción de
  Pydantic por sí mismos (duplicado exacto, ID en conflicto, producto huérfano, alertas de tipo).
- PYDANTIC: `ValidationError` de `TransaccionLimpia` (formato, rango, coherencia, obligatorios por canal).
- ERROR_INESPERADO: cualquier otra excepción sobre ese registro (R13.4). Se registra con el tipo y el mensaje
  en `detalle_error` y en el log; el lote continúa. No se oculta: queda auditable.

Si un mismo código lo detectan la fase previa y Pydantic, se cuenta una vez (se conserva la fase previa).
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from pydantic import ValidationError

from ..contratos import (ErrorContrato, ALERTA_CANTIDAD_NO_NUMERICA, ALERTA_FECHA_NO_INTERPRETABLE, ALERTA_MONEDA_NO_SOPORTADA,
                         ALERTA_PRECIO_INVALIDO, RECH_CANTIDAD, RECH_DUPLICADO, RECH_FECHA, RECH_HUERFANO,
                         RECH_ID_CONFLICTO, RECH_INESPERADO, RECH_MONEDA, RECH_PRECIO_INVALIDO, RECH_TIPO)
from .esquemas import TransaccionLimpia

log = logging.getLogger(__name__)

ETAPA_FASE_PREVIA, ETAPA_PYDANTIC, ETAPA_INESPERADO = "FASE_PREVIA", "PYDANTIC", "ERROR_INESPERADO"
RE_CODIGO = re.compile(r"^([A-Z][A-Z_]+): ")
COLUMNAS_LIMPIAS = [
    "id_transaccion", "origen", "id_fila_origen", "fecha_cruda", "fecha_venta", "punto_venta", "id_producto",
    "nombre_producto", "categoria", "cantidad_origen", "cantidad", "cantidad_cap", "moneda_original", "moneda",
    "tipo_cambio_aplicado", "precio_unitario_original", "precio_unitario_mxn", "monto_total_origen",
    "monto_total_mxn", "monto_cantidad_cap_mxn", "monto_total_mxn_cap", "monto_minmax", "segmento_importe",
    "id_cliente", "email_cliente", "direccion_envio", "metodo_pago", "estado_pedido", "es_outlier_cantidad",
    "es_outlier_monto", "alertas", "correcciones", "registro_original",
]


# Campo del modelo → columna que entrega Yerik/Leslie cuando se llaman distinto (el modelo usa el nombre de la BD).
ALIAS_ENTRADA = {"precio_unitario_original": "precio_unitario"}


class ErrorConservacion(Exception):
    """Falla GLOBAL: validos + cuarentena no cuadra con la entrada (R1.4). Interrumpe la ejecución."""


@dataclass
class ResultadoValidacion:
    validos: list[dict] = field(default_factory=list)
    cuarentena: list[dict] = field(default_factory=list)
    conteo_por_codigo: dict[str, int] = field(default_factory=dict)       # registros que contienen el código
    conteo_por_etapa: dict[str, int] = field(default_factory=dict)
    errores_inesperados: int = 0

    @property
    def total(self) -> int:
        return len(self.validos) + len(self.cuarentena)


# ----------------------------------------------------------------------------- utilidades
def a_nativo(v):
    """NaN/NaT/NA → None y tipos numpy → tipos Python (Pydantic y sqlite3 no entienden NaN como nulo)."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [a_nativo(x) for x in v]
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _resumir(valor, n: int = 120) -> str | None:
    if valor is None:
        return None
    t = repr(valor)
    return t if len(t) <= n else t[: n - 1] + "…"


def formatear_errores(e: ValidationError) -> list[dict]:
    """Cada error de Pydantic → {campo, codigo, mensaje, entrada}. Los nativos (tipo, requerido, Literal) → TIPO_INVALIDO."""
    out = []
    for err in e.errors():
        msg = err["msg"].removeprefix("Value error, ")
        campo = ".".join(map(str, err["loc"]))
        m = RE_CODIGO.match(msg)
        if m:
            codigo, texto = m.group(1), msg
        else:
            codigo, texto = RECH_TIPO, f"{RECH_TIPO}: {campo} → {msg}"
        out.append({"campo": campo, "codigo": codigo, "mensaje": texto, "etapa": ETAPA_PYDANTIC,
                    "entrada": _resumir(err.get("input"))})
    return out


def errores_fases_previas(fila: dict) -> list[dict]:
    """Defectos ya detectados por las fases 1-5 (banderas y alertas). No requieren que Pydantic lance nada."""
    out = []

    def agregar(codigo, campo, mensaje):
        out.append({"campo": campo, "codigo": codigo, "mensaje": f"{codigo}: {mensaje}", "etapa": ETAPA_FASE_PREVIA,
                    "entrada": None})

    if fila.get("es_duplicado"):
        agregar(RECH_DUPLICADO, "es_duplicado", "repite exactamente una fila anterior del mismo archivo (R2.3)")
    if fila.get("es_id_conflicto"):
        agregar(RECH_ID_CONFLICTO, "es_id_conflicto", "el identificador aparece con contenido distinto (R2.4)")
    if fila.get("en_catalogo") is False:
        agregar(RECH_HUERFANO, "en_catalogo", f"{fila.get('id_producto')!r} no existe en el catálogo maestro (R9)")
    alertas = fila.get("alertas") or []
    if ALERTA_CANTIDAD_NO_NUMERICA in alertas:
        agregar(RECH_CANTIDAD, "cantidad", "la cantidad original no es numérica (alerta de homologación)")
    if ALERTA_PRECIO_INVALIDO in alertas:
        agregar(RECH_PRECIO_INVALIDO, "precio_unitario", "el precio original no es numérico (alerta de homologación)")
    if ALERTA_MONEDA_NO_SOPORTADA in alertas:
        agregar(RECH_MONEDA, "moneda", f"{fila.get('moneda_original')!r} no es MXN ni USD (alerta de conversión) (R7.5)")
    if ALERTA_FECHA_NO_INTERPRETABLE in alertas:
        agregar(RECH_FECHA, "fecha_venta", f"fecha_cruda={fila.get('fecha_cruda')!r} no se pudo interpretar (alerta de fechas)")
    return out


def _registro_cuarentena(fila: dict, lote_id: str, ahora: str, detalle: list[dict]) -> dict:
    vistos, unicos = set(), []
    for d in detalle:                                    # primero la fase previa, luego Pydantic; un código = un motivo
        if d["codigo"] not in vistos:
            vistos.add(d["codigo"])
            unicos.append(d)
    codigos = sorted(vistos)
    original = fila.get("registro_original") or json.dumps(fila, default=str, ensure_ascii=False)
    return {"lote_id": lote_id, "id_registro": None if fila.get("id_transaccion") is None else str(fila["id_transaccion"]),
            "origen": fila.get("origen"), "id_fila_origen": fila.get("id_fila_origen"),
            "etapa_deteccion": ";".join(sorted({d["etapa"] for d in unicos})),
            "codigos_error": ";".join(codigos), "num_motivos": len(codigos),
            "motivo_rechazo_cuarentena": " | ".join(d["mensaje"] for d in unicos),
            "detalle_error": json.dumps(unicos, ensure_ascii=False), "registro_original": original,
            "fecha_cuarentena": ahora}


def _fila_limpia(m: TransaccionLimpia) -> dict:
    d = m.model_dump()
    d["moneda"] = "MXN"      # todos los importes *_mxn están en pesos; la moneda original se conserva en moneda_original
    d["alertas"] = json.dumps(d["alertas"], ensure_ascii=False)
    d["correcciones"] = json.dumps(d["correcciones"], ensure_ascii=False)
    for c in ("cantidad", "cantidad_cap"):
        d[c] = int(d[c])
    for c in ("es_outlier_cantidad", "es_outlier_monto"):
        d[c] = int(d[c])
    return {c: d[c] for c in COLUMNAS_LIMPIAS}


# ----------------------------------------------------------------------------- clasificación
def clasificar_registro(fila: dict, lote_id: str, ahora: str, hoy: date):
    """Devuelve ('VALIDO', fila_para_sql) o ('RECHAZADO', registro_de_cuarentena). Nunca lanza por datos del registro."""
    fila = {k: a_nativo(v) for k, v in fila.items()}
    for campo, columna in ALIAS_ENTRADA.items():
        if campo not in fila and columna in fila:
            fila[campo] = fila[columna]
    previos = errores_fases_previas(fila)
    detalle = list(previos)
    modelo = None
    try:
        modelo = TransaccionLimpia.model_validate(fila, context={"hoy": hoy})
    except ValidationError as e:
        detalle += formatear_errores(e)
    except Exception as e:  # noqa: BLE001 — registro imposible de validar: se aísla, se registra y el lote continúa (R13.4)
        log.error("Error inesperado validando %s fila %s: %s: %s", fila.get("id_transaccion"),
                  fila.get("id_fila_origen"), type(e).__name__, e, exc_info=True)
        detalle.append({"campo": None, "codigo": RECH_INESPERADO, "etapa": ETAPA_INESPERADO, "entrada": None,
                        "mensaje": f"{RECH_INESPERADO}: {type(e).__name__}: {e}"})
    if modelo is not None and not previos:
        return "VALIDO", _fila_limpia(modelo)
    # Una fase previa marcó el registro aunque Pydantic lo aceptara (R1.3): se rechaza igual, con su motivo.
    return "RECHAZADO", _registro_cuarentena(fila, lote_id, ahora, detalle)


def validar_lote(df: pd.DataFrame, lote_id: str, hoy: date | None = None, ahora: str | None = None) -> ResultadoValidacion:
    """Valida registro por registro (el try/except está DENTRO del ciclo: un registro malo no detiene a los demás)."""
    faltan = [c for c in TransaccionLimpia.model_fields
              if c not in df.columns and ALIAS_ENTRADA.get(c) not in df.columns]
    if faltan:      # un campo del modelo sin columna se guardaría como NULL en silencio: es un contrato roto (falla global)
        raise ErrorContrato(f"[F6 validar_lote] faltan columnas que el modelo necesita: {faltan}")
    hoy = hoy or date.today()
    ahora = ahora or datetime.now().isoformat(timespec="seconds")
    res = ResultadoValidacion()
    esperados = set(zip(df["origen"], df["id_fila_origen"].astype(int)))
    for fila in df.to_dict(orient="records"):
        estado, reg = clasificar_registro(fila, lote_id, ahora, hoy)
        if estado == "VALIDO":
            res.validos.append(reg)
            continue
        res.cuarentena.append(reg)
        for codigo in reg["codigos_error"].split(";"):
            res.conteo_por_codigo[codigo] = res.conteo_por_codigo.get(codigo, 0) + 1
        for etapa in reg["etapa_deteccion"].split(";"):
            res.conteo_por_etapa[etapa] = res.conteo_por_etapa.get(etapa, 0) + 1
        if RECH_INESPERADO in reg["codigos_error"]:
            res.errores_inesperados += 1
    clasificados = [(r["origen"], r["id_fila_origen"]) for r in res.validos + res.cuarentena]
    if len(clasificados) != len(df) or set(clasificados) != esperados or len(set(clasificados)) != len(clasificados):
        raise ErrorConservacion(
            f"Conservación violada: entrada={len(df)}, válidos={len(res.validos)}, cuarentena={len(res.cuarentena)}, "
            f"filas distintas clasificadas={len(set(clasificados))}")
    res.conteo_por_codigo = dict(sorted(res.conteo_por_codigo.items(), key=lambda kv: (-kv[1], kv[0])))
    return res
