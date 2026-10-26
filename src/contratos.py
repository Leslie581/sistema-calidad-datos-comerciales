"""
Contratos entre módulos: nombres de columnas por etapa y códigos de corrección/alerta.

Archivo COMPARTIDO (GUIA_GENERAL_PROYECTO.md §9). Cambiar un nombre aquí obliga a
avisar a los tres integrantes, porque cada etapa verifica su entrada con
`verificar_columnas()` y falla con un mensaje claro si falta algo.
"""
from __future__ import annotations

import pandas as pd

# ----------------------------------------------------------------------------- columnas de origen
COLUMNAS_FISICA = ["id_ticket", "fecha_venta", "sucursal", "id_producto", "cantidad",
                   "precio_unitario", "monto_total_mxn", "id_cliente", "metodo_pago"]
COLUMNAS_ONLINE = ["order_id", "order_timestamp", "product_id", "units", "currency", "unit_price",
                   "total_amount", "customer_email", "shipping_address", "order_status", "payment_gateway"]
COLUMNAS_CATALOGO = ["id_producto", "nombre_producto", "categoria", "precio_base_mxn",
                     "stock_minimo", "proveedor"]

# Columnas técnicas que agrega la extracción a cada fuente de ventas
COLUMNAS_TECNICAS_EXTRACCION = ["id_fila_origen", "registro_original"]

# ----------------------------------------------------------------------------- mapeo a esquema unificado
# None = la columna no existe en ese canal ("no aplica", R3.9). Las constantes se asignan en homologación.
MAPEO_FISICA = {
    "id_transaccion": "id_ticket", "fecha_cruda": "fecha_venta", "punto_venta": "sucursal",
    "id_producto": "id_producto", "cantidad": "cantidad", "precio_unitario": "precio_unitario",
    "monto_total": "monto_total_mxn", "moneda": None, "id_cliente": "id_cliente", "email_cliente": None,
    "direccion_envio": None, "metodo_pago": "metodo_pago", "estado_pedido": None,
}
MAPEO_ONLINE = {
    "id_transaccion": "order_id", "fecha_cruda": "order_timestamp", "punto_venta": None,
    "id_producto": "product_id", "cantidad": "units", "precio_unitario": "unit_price",
    "monto_total": "total_amount", "moneda": "currency", "id_cliente": None,
    "email_cliente": "customer_email", "direccion_envio": "shipping_address",
    "metodo_pago": "payment_gateway", "estado_pedido": "order_status",
}

# ----------------------------------------------------------------------------- columnas por etapa
COLUMNAS_HOMOLOGADAS = [
    "id_transaccion", "origen", "id_fila_origen", "fecha_cruda", "punto_venta", "id_producto",
    "cantidad", "precio_unitario", "monto_total", "moneda", "id_cliente", "email_cliente",
    "direccion_envio", "metodo_pago", "estado_pedido", "registro_original", "alertas", "correcciones",
]
# F2 · Leslie (limpiar_registros)
COLUMNAS_AGREGA_LIMPIEZA = ["es_duplicado", "es_id_conflicto", "cantidad_origen", "monto_total_origen"]
# F4 · Yerik (versión mínima usada por Leslie para el IQR en MXN)
COLUMNAS_AGREGA_IMPORTES_MXN = ["moneda_original", "tipo_cambio_aplicado", "precio_unitario_mxn", "monto_total_mxn"]
COLUMNAS_AGREGA_CATALOGO = ["nombre_producto", "categoria", "precio_catalogo_mxn", "en_catalogo",
                            "dif_precio_catalogo"]
COLUMNAS_AGREGA_FECHAS = ["fecha_venta"]                                              # F4 · Yerik (fechas.py)
# F5 · Yerik (transformacion.py). `monto_minmax` y `segmento_importe` son lo que valida Nono;
# `minmax_recortado` es informativa (el monto quedó fuera de [min, max] de la base y se acotó a [0, 1]).
COLUMNAS_AGREGA_TRANSFORMACION = ["monto_minmax", "segmento_importe", "minmax_recortado"]
# F3 · Leslie (tratar_outliers)
COLUMNAS_AGREGA_OUTLIERS = ["es_base_estadistica", "cantidad_cap", "es_outlier_cantidad",
                            "monto_cantidad_cap_mxn", "monto_total_mxn_cap", "es_outlier_monto"]

# Entradas requeridas por cada función de etapa
REQUERIDAS_LIMPIEZA = COLUMNAS_HOMOLOGADAS
REQUERIDAS_OUTLIERS = (COLUMNAS_HOMOLOGADAS + COLUMNAS_AGREGA_LIMPIEZA
                       + COLUMNAS_AGREGA_IMPORTES_MXN + ["en_catalogo"])
REQUERIDAS_INTEGRACION = COLUMNAS_HOMOLOGADAS + COLUMNAS_AGREGA_LIMPIEZA
REQUERIDAS_TRANSFORMACION = (REQUERIDAS_OUTLIERS + COLUMNAS_AGREGA_OUTLIERS + COLUMNAS_AGREGA_FECHAS
                             + ["es_base_estadistica"])

# ----------------------------------------------------------------------------- códigos
# Alertas: problemas de tipo detectados antes de validar (Nono las convierte en rechazo)
ALERTA_CANTIDAD_NO_NUMERICA = "CANTIDAD_NO_NUMERICA"
ALERTA_PRECIO_INVALIDO = "PRECIO_INVALIDO"
ALERTA_MONTO_NO_NUMERICO = "MONTO_NO_NUMERICO"
ALERTA_MONEDA_NO_SOPORTADA = "MONEDA_NO_SOPORTADA"
ALERTA_FECHA_NO_INTERPRETABLE = "FECHA_NO_INTERPRETABLE"
ALERTA_PRECIO_DIFIERE_CATALOGO = "PRECIO_DIFIERE_CATALOGO"   # informativa: no rechaza (guía Yerik §5)

# Rechazos (cuarentena): códigos que Nono escribe en `codigos_error` (REGLAS_DE_NEGOCIO.md §13).
# [EQUIPO] = catálogo documentado · [PROPUESTA] = regla añadida en la etapa 3, pendiente de aprobación del equipo.
RECH_DUPLICADO = "DUPLICADO_EXACTO"                      # R2.3
RECH_ID_CONFLICTO = "ID_REPETIDO_CONFLICTO"              # R2.4
RECH_ID_FORMATO = "ID_FORMATO_INVALIDO"                  # R2.2
RECH_CANTIDAD = "CANTIDAD_INVALIDA"                      # R4
RECH_PRECIO_FALTANTE = "PRECIO_FALTANTE"                 # R3.6
RECH_PRECIO_INVALIDO = "PRECIO_INVALIDO"                 # R3.6
RECH_MONTO_INVALIDO = "MONTO_INVALIDO"                   # R6
RECH_MONTO_INCONSISTENTE = "MONTO_INCONSISTENTE"         # R6.3
RECH_HUERFANO = "PRODUCTO_HUERFANO"                      # R9
RECH_EMAIL = "EMAIL_MALFORMADO"                          # R10
RECH_FECHA = "FECHA_INVALIDA"                            # R8.5
RECH_MONEDA = "MONEDA_NO_SOPORTADA"                      # R7.5
RECH_ESCALA = "ESCALA_FUERA_DE_RANGO"                    # R12 (guía de Nono)
RECH_TIPO = "TIPO_INVALIDO"                              # error nativo de Pydantic (tipo, campo requerido, Literal…)
RECH_INESPERADO = "ERROR_INESPERADO"                     # R13.4
RECH_ID_ORIGEN = "ID_ORIGEN_INCONSISTENTE"               # [PROPUESTA] prefijo POS-/WEB- distinto del canal
RECH_OBLIGATORIO = "CAMPO_OBLIGATORIO_FALTANTE"          # [PROPUESTA] campo requerido por canal ausente
RECH_ESTADO = "ESTADO_INVALIDO"                          # [PROPUESTA] estado fuera de R11 (o presente en canal físico)
RECH_TIPO_CAMBIO = "TIPO_CAMBIO_INCONSISTENTE"           # [PROPUESTA] tipo de cambio ≠ el de la moneda original
CODIGOS_RECHAZO_PROPUESTOS = (RECH_ID_ORIGEN, RECH_OBLIGATORIO, RECH_ESTADO, RECH_TIPO_CAMBIO)

# Correcciones: bitácora por fila de lo que se cambió (trazabilidad)
CORR_MONTO_NULO = "MONTO_RECALCULADO_NULO"
CORR_MONTO_INCONSISTENTE = "MONTO_RECALCULADO_INCONSISTENTE"
CORR_MEDIANA_CANTIDAD = "IMPUTADO_MEDIANA_CANTIDAD"
CORR_CONVERTIDO_USD = "CONVERTIDO_USD_MXN"
CORR_CAPPING_CANTIDAD = "CAPPING_IQR_CANTIDAD"
CORR_CAPPING_MONTO = "CAPPING_IQR_MONTO"


def corr_imputado(columna: str) -> str:
    return f"IMPUTADO_{columna.upper()}"


def corr_fecha(formato: str) -> str:
    """Formato de origen de la fecha, p. ej. FECHA_DESDE_DD/MM/YYYY o FECHA_DESDE_EPOCH."""
    return f"FECHA_DESDE_{formato}"


class ErrorContrato(Exception):
    """La entrada de una etapa no tiene las columnas acordadas."""


def verificar_columnas(df: pd.DataFrame, requeridas: list[str], etapa: str) -> None:
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise ErrorContrato(f"[{etapa}] faltan columnas del contrato: {faltan}")
