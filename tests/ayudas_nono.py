"""Ayudas de las pruebas de la etapa de Nono: registros mínimos ya procesados por las etapas 1 y 2."""
from __future__ import annotations

import json
from datetime import date

HOY = date(2026, 10, 25)


def fila_valida(canal: str = "FISICA", **cambios) -> dict:
    """Fila con TODAS las columnas que entrega Yerik (`df_transformado`), válida en su canal."""
    comun = {
        "es_duplicado": False, "es_id_conflicto": False, "alertas": [], "origen": canal, "id_fila_origen": 1,
        "fecha_venta": "2026-09-13", "fecha_cruda": "13-09-2026", "id_producto": "PROD-010", "en_catalogo": True,
        "nombre_producto": "Producto 10", "categoria": "Hogar", "cantidad_origen": 2.0, "cantidad": 2.0, "cantidad_cap": 2.0,
        "moneda_original": "MXN", "tipo_cambio_aplicado": 1.0, "precio_unitario_original": 100.0,
        "precio_unitario_mxn": 100.0, "monto_total_origen": 200.0, "monto_total_mxn": 200.0,
        "monto_cantidad_cap_mxn": 200.0, "monto_total_mxn_cap": 200.0, "monto_minmax": 0.5, "segmento_importe": "Medio",
        "metodo_pago": "EFECTIVO", "es_outlier_cantidad": False, "es_outlier_monto": False, "correcciones": [],
    }
    if canal == "FISICA":
        comun.update(id_transaccion="POS-2026-0001", punto_venta="Colima Centro", id_cliente="CTE-001",
                     email_cliente=None, direccion_envio=None, estado_pedido=None)
    else:
        comun.update(id_transaccion="WEB-00001", punto_venta="TIENDA_ONLINE", id_cliente=None,
                     email_cliente="cliente@correo.com", direccion_envio="Calle 1, Colima", estado_pedido="COMPLETADO")
    comun.update(cambios)
    comun.setdefault("registro_original", json.dumps({"id": comun["id_transaccion"]}))
    return comun


CATALOGO_MINIMO = [{"id_producto": "PROD-010", "nombre_producto": "Producto 10", "categoria": "Hogar",
                    "precio_base_mxn": 100.0, "stock_minimo": 5, "proveedor": "Proveedor-Norte"}]
