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
# F3 · Leslie (tratar_outliers)
COLUMNAS_AGREGA_OUTLIERS = ["es_base_estadistica", "cantidad_cap", "es_outlier_cantidad",
                            "monto_cantidad_cap_mxn", "monto_total_mxn_cap", "es_outlier_monto"]

# Entradas requeridas por cada función de etapa
REQUERIDAS_LIMPIEZA = COLUMNAS_HOMOLOGADAS
REQUERIDAS_OUTLIERS = (COLUMNAS_HOMOLOGADAS + COLUMNAS_AGREGA_LIMPIEZA
                       + COLUMNAS_AGREGA_IMPORTES_MXN + ["en_catalogo"])

# ----------------------------------------------------------------------------- códigos
# Alertas: problemas de tipo detectados antes de validar (Nono las convierte en rechazo)
ALERTA_CANTIDAD_NO_NUMERICA = "CANTIDAD_NO_NUMERICA"
ALERTA_PRECIO_INVALIDO = "PRECIO_INVALIDO"
ALERTA_MONTO_NO_NUMERICO = "MONTO_NO_NUMERICO"
ALERTA_MONEDA_NO_SOPORTADA = "MONEDA_NO_SOPORTADA"

# Correcciones: bitácora por fila de lo que se cambió (trazabilidad)
CORR_MONTO_NULO = "MONTO_RECALCULADO_NULO"
CORR_MONTO_INCONSISTENTE = "MONTO_RECALCULADO_INCONSISTENTE"
CORR_MEDIANA_CANTIDAD = "IMPUTADO_MEDIANA_CANTIDAD"
CORR_CONVERTIDO_USD = "CONVERTIDO_USD_MXN"
CORR_CAPPING_CANTIDAD = "CAPPING_IQR_CANTIDAD"
CORR_CAPPING_MONTO = "CAPPING_IQR_MONTO"


def corr_imputado(columna: str) -> str:
    return f"IMPUTADO_{columna.upper()}"


class ErrorContrato(Exception):
    """La entrada de una etapa no tiene las columnas acordadas."""


def verificar_columnas(df: pd.DataFrame, requeridas: list[str], etapa: str) -> None:
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise ErrorContrato(f"[{etapa}] faltan columnas del contrato: {faltan}")
