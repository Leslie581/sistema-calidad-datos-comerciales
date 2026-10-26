"""
F6 · Modelo Pydantic de la transacción limpia (responsable: Nono).

Un solo modelo para los dos canales (la tabla final es una). Las diferencias por canal viven en los
validadores. Cada mensaje de error empieza con un CÓDIGO (`PRODUCTO_HUERFANO: …`) para poder filtrar y
contar la cuarentena. Los códigos están en `contratos.py`; los marcados [PROPUESTA] no están en
REGLAS_DE_NEGOCIO.md y esperan aprobación del equipo.

Decisiones de diseño
- `strict=True`: un texto donde se espera un número (o un número donde se espera un booleano) es un error
  de tipo, no se convierte en silencio. `extra="ignore"`: las columnas auxiliares no hacen fallar el modelo.
- Pydantic acumula TODOS los errores de un registro (R13.2).
- El orden de los campos importa: un validador solo ve (en `info.data`) los campos declarados antes.
- Valores ORIGINALES y TRATADOS conviven (R5.5): `cantidad_origen → cantidad → cantidad_cap`,
  `precio_unitario_original → precio_unitario_mxn`, `monto_total_origen → monto_total_mxn →
  monto_cantidad_cap_mxn → monto_total_mxn_cap`, `fecha_cruda → fecha_venta`, `registro_original`.
  El modelo valida el tratado y conserva el original: el capping nunca borra evidencia.
- La fecha límite (R8.5: «posterior a la fecha de ejecución») se toma de `context={"hoy": date}`; por omisión,
  `date.today()`.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from ..config import ESTADOS_PEDIDO_VALIDOS, ORIGEN_FISICA, ORIGEN_ONLINE, PARIDAD_USD_MXN, TOLERANCIA_MONTO, redondear
from ..contratos import (RECH_CANTIDAD, RECH_DUPLICADO, RECH_EMAIL, RECH_ESCALA, RECH_ESTADO, RECH_FECHA,
                         RECH_HUERFANO, RECH_ID_CONFLICTO, RECH_ID_FORMATO, RECH_ID_ORIGEN, RECH_MONEDA,
                         RECH_MONTO_INCONSISTENTE, RECH_MONTO_INVALIDO, RECH_OBLIGATORIO, RECH_PRECIO_FALTANTE,
                         RECH_PRECIO_INVALIDO, RECH_TIPO_CAMBIO, ALERTA_PRECIO_INVALIDO, ALERTA_CANTIDAD_NO_NUMERICA)

RE_ID = re.compile(r"POS-[0-9]{4}-[0-9]{4}|WEB-[0-9]{5}")                                   # R2.2
RE_FECHA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")                                    # R8.1
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")  # R10.2
ETIQUETA_SIN_CORREO = "SIN_CORREO"                                                          # R3.8
TIPO_CAMBIO_ESPERADO = {"MXN": 1.0, "USD": float(PARIDAD_USD_MXN)}


def _rechazo(codigo: str, mensaje: str) -> ValueError:
    return ValueError(f"{codigo}: {mensaje}")


def _vacio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class TransaccionLimpia(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    # ---- control de fases previas (se validan, no se guardan como columnas de negocio) ----
    es_duplicado: bool
    es_id_conflicto: bool
    alertas: list[str] = Field(default_factory=list)
    # ---- identidad y trazabilidad ----
    origen: Literal["FISICA", "ONLINE"]
    id_transaccion: str
    id_fila_origen: int
    registro_original: str
    # ---- fecha ----
    fecha_cruda: Optional[str] = None
    fecha_venta: Optional[str]
    punto_venta: Optional[str]
    # ---- producto ----
    id_producto: Optional[str]
    en_catalogo: bool
    nombre_producto: Optional[str] = None
    categoria: Optional[str] = None
    # ---- cantidades: original → tratada → con capping ----
    cantidad_origen: Optional[float] = None
    cantidad: Optional[float]
    cantidad_cap: Optional[float]
    # ---- importes: original → convertido → con capping ----
    moneda_original: Optional[str]
    tipo_cambio_aplicado: Optional[float] = None
    precio_unitario_original: Optional[float] = None
    precio_unitario_mxn: Optional[float]
    monto_total_origen: Optional[float] = None
    monto_total_mxn: Optional[float]
    monto_cantidad_cap_mxn: Optional[float] = None
    monto_total_mxn_cap: float = Field(allow_inf_nan=False)
    # ---- transformación (Yerik) ----
    monto_minmax: float = Field(allow_inf_nan=False)
    segmento_importe: Literal["Bajo", "Medio", "Alto"]
    # ---- cliente / venta ----
    id_cliente: Optional[str] = None
    email_cliente: Optional[str] = None
    direccion_envio: Optional[str] = None
    metodo_pago: Optional[str]
    estado_pedido: Optional[str] = None
    es_outlier_cantidad: bool
    es_outlier_monto: bool
    correcciones: list[str] = Field(default_factory=list)

    # ------------------------------------------------------------------ fases previas
    @field_validator("es_duplicado")
    @classmethod
    def v_duplicado(cls, v):
        if v:
            raise _rechazo(RECH_DUPLICADO, "repite exactamente una fila anterior del mismo archivo (R2.3)")
        return v

    @field_validator("es_id_conflicto")
    @classmethod
    def v_conflicto(cls, v):
        if v:
            raise _rechazo(RECH_ID_CONFLICTO, "el identificador aparece con contenido distinto (R2.4)")
        return v

    # ------------------------------------------------------------------ identidad
    @field_validator("id_transaccion")
    @classmethod
    def v_id(cls, v, info: ValidationInfo):
        if not RE_ID.fullmatch(v):
            raise _rechazo(RECH_ID_FORMATO, f"{v!r} no cumple POS-AAAA-NNNN ni WEB-NNNNN (R2.2)")
        esperado = {ORIGEN_FISICA: "POS-", ORIGEN_ONLINE: "WEB-"}.get(info.data.get("origen"))
        if esperado and not v.startswith(esperado):                                       # [PROPUESTA]
            raise _rechazo(RECH_ID_ORIGEN, f"{v!r} no corresponde al canal {info.data['origen']}")
        return v

    @field_validator("id_fila_origen")
    @classmethod
    def v_fila(cls, v):
        if v < 1:
            raise _rechazo(RECH_OBLIGATORIO, f"id_fila_origen={v} debe ser ≥ 1 (trazabilidad)")
        return v

    @field_validator("registro_original")
    @classmethod
    def v_original(cls, v):
        if _vacio(v):
            raise _rechazo(RECH_OBLIGATORIO, "registro_original vacío: no habría evidencia del dato crudo")
        return v

    # ------------------------------------------------------------------ fecha
    @field_validator("fecha_venta")
    @classmethod
    def v_fecha(cls, v, info: ValidationInfo):
        crudo = info.data.get("fecha_cruda")
        if v is None:
            raise _rechazo(RECH_FECHA, f"fecha_cruda={crudo!r} no tiene un formato reconocido o no existe en el calendario")
        if not RE_FECHA_ISO.fullmatch(v):
            raise _rechazo(RECH_FECHA, f"{v!r} no es YYYY-MM-DD")
        try:
            f = date.fromisoformat(v)
        except ValueError:
            raise _rechazo(RECH_FECHA, f"{v!r} no existe en el calendario") from None
        hoy = (info.context or {}).get("hoy") or date.today()
        if f > hoy:
            raise _rechazo(RECH_FECHA, f"{v} es posterior a la fecha de ejecución ({hoy.isoformat()}) (R8.5)")
        return v

    @field_validator("punto_venta", "metodo_pago")
    @classmethod
    def v_obligatorio_texto(cls, v, info: ValidationInfo):
        if _vacio(v):
            raise _rechazo(RECH_OBLIGATORIO, f"{info.field_name} es obligatorio")
        return v

    # ------------------------------------------------------------------ producto
    @field_validator("en_catalogo")
    @classmethod
    def v_catalogo(cls, v, info: ValidationInfo):
        if not v:
            raise _rechazo(RECH_HUERFANO, f"{info.data.get('id_producto')!r} no existe en el catálogo maestro (R9)")
        return v

    @field_validator("nombre_producto", "categoria")
    @classmethod
    def v_datos_catalogo(cls, v, info: ValidationInfo):
        if info.data.get("en_catalogo") and _vacio(v):
            raise _rechazo(RECH_OBLIGATORIO, f"{info.field_name} debe venir del catálogo maestro (R9.3)")
        return v

    # ------------------------------------------------------------------ cantidades
    @field_validator("cantidad", "cantidad_cap", mode="before")
    @classmethod
    def v_cantidad(cls, v, info: ValidationInfo):
        previo = ""
        if ALERTA_CANTIDAD_NO_NUMERICA in (info.data.get("alertas") or []):
            previo = f" (alerta previa {ALERTA_CANTIDAD_NO_NUMERICA})"
        if not _es_numero(v):
            raise _rechazo(RECH_CANTIDAD, f"{info.field_name}={v!r} no es un número{previo}")
        if not float(v).is_integer() or v <= 0:
            raise _rechazo(RECH_CANTIDAD, f"{info.field_name}={v!r}; debe ser un entero mayor que 0 (R4)")
        return float(v)

    # ------------------------------------------------------------------ moneda e importes
    @field_validator("moneda_original")
    @classmethod
    def v_moneda(cls, v):
        if v not in TIPO_CAMBIO_ESPERADO:
            raise _rechazo(RECH_MONEDA, f"{v!r} (solo MXN o USD) (R7.5)")
        return v

    @field_validator("tipo_cambio_aplicado")
    @classmethod
    def v_tipo_cambio(cls, v, info: ValidationInfo):
        moneda = info.data.get("moneda_original")
        if moneda in TIPO_CAMBIO_ESPERADO and v != TIPO_CAMBIO_ESPERADO[moneda]:               # [PROPUESTA]
            raise _rechazo(RECH_TIPO_CAMBIO, f"{v!r} ≠ {TIPO_CAMBIO_ESPERADO[moneda]} para {moneda}")
        return v

    @field_validator("precio_unitario_mxn")
    @classmethod
    def v_precio(cls, v, info: ValidationInfo):
        if v is None:
            if ALERTA_PRECIO_INVALIDO in (info.data.get("alertas") or []):
                raise _rechazo(RECH_PRECIO_INVALIDO, "el precio original no es numérico (alerta previa PRECIO_INVALIDO)")
            raise _rechazo(RECH_PRECIO_FALTANTE, "no hay precio unitario en MXN")
        if not math.isfinite(v) or v <= 0:
            raise _rechazo(RECH_PRECIO_INVALIDO, f"{v} debe ser mayor que 0")
        return v

    @field_validator("monto_total_mxn")
    @classmethod
    def v_monto(cls, v, info: ValidationInfo):
        if v is None or not math.isfinite(v) or v <= 0:
            raise _rechazo(RECH_MONTO_INVALIDO, f"monto_total_mxn={v}; debe ser mayor que 0")
        c, p = info.data.get("cantidad"), info.data.get("precio_unitario_mxn")
        if c is not None and p is not None and abs(redondear(c * p) - v) > TOLERANCIA_MONTO:
            raise _rechazo(RECH_MONTO_INCONSISTENTE, f"{v} ≠ {c:g} × {p} (tolerancia {TOLERANCIA_MONTO}) (R6.3)")
        return v

    @field_validator("monto_total_mxn_cap")
    @classmethod
    def v_monto_cap(cls, v):
        if v <= 0:
            raise _rechazo(RECH_MONTO_INVALIDO, f"monto_total_mxn_cap={v}; debe ser mayor que 0")
        return v

    @field_validator("monto_minmax")
    @classmethod
    def v_minmax(cls, v):
        if not 0 <= v <= 1:
            raise _rechazo(RECH_ESCALA, f"monto_minmax={v} fuera de [0, 1] (R12.1)")
        return v

    # ------------------------------------------------------------------ opcionales según el canal
    @field_validator("id_cliente")
    @classmethod
    def v_cliente(cls, v, info: ValidationInfo):
        if info.data.get("origen") == ORIGEN_FISICA and _vacio(v):                         # R3.9 / [PROPUESTA] como rechazo
            raise _rechazo(RECH_OBLIGATORIO, "id_cliente es obligatorio en el canal FISICA (ANONIMO si faltaba)")
        return v

    @field_validator("email_cliente")
    @classmethod
    def v_email(cls, v, info: ValidationInfo):
        if info.data.get("origen") == ORIGEN_ONLINE and v != ETIQUETA_SIN_CORREO:
            if _vacio(v):
                raise _rechazo(RECH_OBLIGATORIO, "email_cliente es obligatorio en el canal ONLINE (SIN_CORREO si faltaba)")
            if not RE_EMAIL.fullmatch(v):
                raise _rechazo(RECH_EMAIL, f"{v!r} no es una dirección de correo válida (R10.2)")
        return v

    @field_validator("direccion_envio")
    @classmethod
    def v_direccion(cls, v, info: ValidationInfo):
        if info.data.get("origen") == ORIGEN_ONLINE and _vacio(v):
            raise _rechazo(RECH_OBLIGATORIO, "direccion_envio es obligatoria en el canal ONLINE (SIN_DIRECCION si faltaba)")
        return v

    @field_validator("estado_pedido")
    @classmethod
    def v_estado(cls, v, info: ValidationInfo):
        origen = info.data.get("origen")
        if origen == ORIGEN_ONLINE and v not in ESTADOS_PEDIDO_VALIDOS:                     # R11 / [PROPUESTA] el rechazo
            raise _rechazo(RECH_ESTADO, f"{v!r} no está entre {', '.join(ESTADOS_PEDIDO_VALIDOS)} (R11)")
        if origen == ORIGEN_FISICA and v is not None:
            raise _rechazo(RECH_ESTADO, f"{v!r}: el canal FISICA no tiene estado de pedido (R3.9)")
        return v
