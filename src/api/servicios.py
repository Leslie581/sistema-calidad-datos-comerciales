"""
Servicios de consulta de la API de KOVA: leen SQLite (solo lectura) y los reportes que escribió el pipeline.

Principios
- Todo valor numérico sale de la base o de un reporte real. Nada se calcula en el navegador ni se inventa aquí.
- Todas las consultas son parametrizadas. Las columnas de ordenación salen de listas blancas; el usuario nunca aporta SQL.
- Las tablas de SQLite contienen SOLO la última carga completada (snapshot por ejecución); la historia disponible es
  la tabla `ejecuciones` y las bitácoras JSON. No se reconstruyen snapshots anteriores.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
from pathlib import Path
from typing import Any

from ..contratos import MAPEO_FISICA, MAPEO_ONLINE
from .config import CARPETAS_REPORTES, EXTENSIONES_REPORTE, Ajustes
from .db import ErrorApi, escalar, fila, filas, patron_like

RE_LOTE = re.compile(r"^L[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")
CORRECCIONES_REPARACION = ("IMPUTADO_", "MONTO_RECALCULADO_")

# Significado de cada código (tomado de contratos.py / REGLAS_DE_NEGOCIO.md; el cliente solo lo muestra).
GLOSARIO_CORRECCIONES = {
    "IMPUTADO_ID_CLIENTE": "id_cliente faltante → etiqueta controlada ANONIMO (R3.8).",
    "IMPUTADO_EMAIL_CLIENTE": "Correo faltante → etiqueta controlada SIN_CORREO (R3.8). Faltante no es lo mismo que malformado.",
    "IMPUTADO_DIRECCION_ENVIO": "Dirección faltante → etiqueta controlada SIN_DIRECCION (R3.8).",
    "IMPUTADO_MEDIANA_CANTIDAD": "Cantidad faltante → mediana entera del canal (R3.5).",
    "MONTO_RECALCULADO_NULO": "Monto vacío → recalculado como cantidad × precio unitario (R6.2).",
    "MONTO_RECALCULADO_INCONSISTENTE": "Monto distinto de cantidad × precio → recalculado; el original se conserva (R6.3).",
    "CONVERTIDO_USD_MXN": "Importes en USD convertidos a MXN con la paridad oficial de 19.50 (R7).",
    "CAPPING_IQR_CANTIDAD": "Cantidad atípica recortada al tope del IQR en `cantidad_cap`; la cantidad real se conserva (R5).",
    "CAPPING_IQR_MONTO": "Importe atípico recortado al límite superior del IQR en `monto_total_mxn_cap` (R5).",
}
GLOSARIO_RECHAZOS = {
    "DUPLICADO_EXACTO": "Repite exactamente una fila anterior del mismo archivo; la primera se conserva (R2.3).",
    "ID_REPETIDO_CONFLICTO": "El mismo identificador aparece con contenido distinto (R2.4).",
    "ID_FORMATO_INVALIDO": "El identificador no cumple POS-AAAA-NNNN ni WEB-NNNNN (R2.2).",
    "CANTIDAD_INVALIDA": "La cantidad no es un entero mayor que 0 (R4).",
    "PRECIO_FALTANTE": "No hay precio unitario utilizable.",
    "PRECIO_INVALIDO": "El precio no es numérico o no es mayor que 0.",
    "MONTO_INVALIDO": "El monto en MXN no es mayor que 0.",
    "MONTO_INCONSISTENTE": "El monto no coincide con cantidad × precio (R6.3).",
    "PRODUCTO_HUERFANO": "El producto no existe en el catálogo maestro (R9).",
    "EMAIL_MALFORMADO": "El correo no cumple el formato válido (R10.2). No se puede reparar sin inventar datos.",
    "FECHA_INVALIDA": "La fecha no se pudo interpretar, no existe o es posterior a la ejecución (R8.5).",
    "MONEDA_NO_SOPORTADA": "La moneda no es MXN ni USD (R7.5).",
    "ESCALA_FUERA_DE_RANGO": "El valor escalado quedó fuera de [0, 1].",
    "TIPO_INVALIDO": "Tipo de dato incorrecto o campo requerido ausente.",
    "ERROR_INESPERADO": "Excepción no prevista al validar el registro (R13.4).",
    "ID_ORIGEN_INCONSISTENTE": "[Propuesta] El prefijo del ID no corresponde al canal.",
    "CAMPO_OBLIGATORIO_FALTANTE": "[Propuesta] Falta un campo obligatorio para su canal.",
    "ESTADO_INVALIDO": "[Propuesta] Estado de pedido fuera del catálogo de R11.",
    "TIPO_CAMBIO_INCONSISTENTE": "[Propuesta] El tipo de cambio no corresponde a la moneda original.",
}
# Fases oficiales del profesor → etapas internas del pipeline (en el orden en que el pipeline las ejecuta).
FASES = [
    {"numero": 1, "clave": "diagnostico", "nombre": "Diagnóstico inicial", "responsable": "Leslie",
     "etapas": ["1. Extracción", "2. Perfilado inicial y MCAR/MAR (informativo)"]},
    {"numero": 2, "clave": "faltantes", "nombre": "Manejo de faltantes", "responsable": "Leslie",
     "etapas": ["3. Homologación", "4. Limpieza e imputación"]},
    {"numero": 3, "clave": "outliers", "nombre": "Outliers (IQR y capping)", "responsable": "Leslie",
     "etapas": ["6. IQR y capping"], "nota": "Se ejecuta después de la integración: el IQR necesita el importe en MXN."},
    {"numero": 4, "clave": "integracion", "nombre": "Integración", "responsable": "Yerik",
     "etapas": ["5. Integración (fechas, USD→MXN, catálogo)"]},
    {"numero": 5, "clave": "transformacion", "nombre": "Transformación", "responsable": "Yerik",
     "etapas": ["7. Min-Max y discretización"]},
    {"numero": 6, "clave": "validacion", "nombre": "Pydantic y cuarentena", "responsable": "Nono",
     "etapas": ["8. Validación Pydantic y cuarentena"]},
    {"numero": 7, "clave": "carga", "nombre": "Carga transaccional", "responsable": "Nono",
     "etapas": ["9. Carga transaccional SQLite"]},
]
ORDEN_TRANSACCIONES = {"fecha": "fecha_venta", "id": "id_transaccion", "canal": "origen", "producto": "id_producto",
                       "cantidad": "cantidad", "precio": "precio_unitario_mxn", "importe": "monto_total_mxn",
                       "importe_cap": "monto_total_mxn_cap", "segmento": "segmento_importe"}
ORDEN_CUARENTENA = {"id": "id_registro", "canal": "origen", "fila": "id_fila_origen", "motivos": "num_motivos",
                    "codigos": "codigos_error", "fecha": "fecha_cuarentena", "registro": "id_error"}
ORDEN_CATALOGO = {"id": "p.id_producto", "nombre": "p.nombre_producto", "categoria": "p.categoria",
                  "precio": "p.precio_base_mxn", "stock": "p.stock_minimo", "ventas": "ventas", "importe": "importe"}
COLUMNAS_RESUMEN = ("id_transaccion, origen, id_fila_origen, fecha_venta, id_producto, nombre_producto, categoria, cantidad, "
                    "precio_unitario_mxn, monto_total_mxn, monto_total_mxn_cap, segmento_importe, estado_pedido, "
                    "moneda_original, precio_unitario_original, tipo_cambio_aplicado")


# ----------------------------------------------------------------------------- utilidades
def _json(texto, defecto=None):
    try:
        return json.loads(texto)
    except (TypeError, ValueError):
        return defecto


def _redondeo(x, n=2):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), n)


def _pagina(total: int, pagina: int, tam: int) -> dict:
    return {"total": total, "pagina": pagina, "tam": tam, "paginas": max(1, math.ceil(total / tam)) if total else 0}


def bitacora_de(aj: Ajustes, lote_id: str | None) -> dict | None:
    if not lote_id or not RE_LOTE.match(lote_id):
        return None
    ruta = aj.dir_salida / "bitacoras" / f"bitacora_{lote_id}.json"
    return _json(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def ultima_bitacora(aj: Ajustes) -> dict | None:
    carpeta = aj.dir_salida / "bitacoras"
    if not carpeta.is_dir():
        return None
    archivos = sorted(carpeta.glob("bitacora_L*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return _json(archivos[0].read_text(encoding="utf-8")) if archivos else None


def _ejecucion_publica(r: dict, bit: dict | None) -> dict:
    entrada, limpias, cuar = r.get("filas_entrada"), r.get("filas_limpias"), r.get("filas_cuarentena")
    return {
        "lote_id": r["lote_id"], "estado": r["estado"], "inicio": r["inicio"], "fin": r["fin"],
        "filas_entrada": entrada, "filas_limpias": limpias, "filas_cuarentena": cuar,
        "tasa_aceptacion": _redondeo(limpias / entrada, 4) if entrada and limpias is not None else None,
        "duracion_s": bit.get("duracion_s") if bit else None,
        "etapa_fallida": r.get("etapa_fallida"), "error": r.get("error"),
        "tiene_bitacora": bit is not None, "advertencias": (bit or {}).get("advertencias", []),
    }


# ----------------------------------------------------------------------------- dashboard
def _salud_origen(conn, entrada: int, limpias: int) -> dict:
    reparadas = escalar(conn, "SELECT COUNT(*) FROM transacciones_limpias WHERE correcciones LIKE '%\"IMPUTADO_%' "
                              "OR correcciones LIKE '%\"MONTO_RECALCULADO_%'")
    conformes = limpias - reparadas
    cuarentena = entrada - limpias
    return {
        "nombre": "Salud de origen KOVA",
        "es_indicador_compuesto": True,
        "valor": _redondeo(conformes / entrada, 4) if entrada else None,
        "formula": "registros que llegaron sin reparación de valor y sin rechazo ÷ registros de entrada",
        "detalle": ("Reparación de valor = imputación de faltantes (IMPUTADO_*) o recálculo de importes (MONTO_RECALCULADO_*). "
                    "La conversión USD→MXN, la normalización de fechas y el capping estadístico NO cuentan como reparación "
                    "(son normalizaciones o tratamientos que conservan el original). Es un indicador propio de KOVA; "
                    "las métricas oficiales son la entrada, las limpias, la cuarentena y la tasa de aceptación."),
        "conformes": conformes, "reparados": reparadas, "rechazados": cuarentena, "entrada": entrada,
    }


def dashboard(conn, aj: Ajustes) -> dict:
    ult = fila(conn, "SELECT * FROM ejecuciones WHERE estado='COMPLETADO' ORDER BY fin DESC, inicio DESC, rowid DESC LIMIT 1")
    limpias = escalar(conn, "SELECT COUNT(*) FROM transacciones_limpias")
    cuarentena = escalar(conn, "SELECT COUNT(*) FROM cuarentena_errores")
    entrada = ult["filas_entrada"] if ult else limpias + cuarentena
    canales = filas(conn, "SELECT o.origen, COALESCE(l.n, 0) AS limpias, COALESCE(c.n, 0) AS cuarentena, "
                          "COALESCE(l.importe, 0) AS importe_mxn FROM (SELECT 'FISICA' AS origen UNION SELECT 'ONLINE') o "
                          "LEFT JOIN (SELECT origen, COUNT(*) n, SUM(monto_total_mxn_cap) importe FROM transacciones_limpias "
                          "GROUP BY origen) l USING (origen) "
                          "LEFT JOIN (SELECT origen, COUNT(*) n FROM cuarentena_errores GROUP BY origen) c USING (origen) "
                          "ORDER BY o.origen")
    for c in canales:
        c["entrada"] = c["limpias"] + c["cuarentena"]
        c["tasa_aceptacion"] = _redondeo(c["limpias"] / c["entrada"], 4) if c["entrada"] else None
        c["importe_mxn"] = _redondeo(c["importe_mxn"])
    segmentos = filas(conn, "SELECT origen, segmento_importe AS segmento, COUNT(*) AS n, "
                            "ROUND(SUM(monto_total_mxn_cap), 2) AS importe_mxn FROM transacciones_limpias "
                            "GROUP BY origen, segmento_importe")
    motivos = _motivos(conn)
    por_dia = filas(conn, "SELECT fecha_venta AS fecha, origen, COUNT(*) AS n, ROUND(SUM(monto_total_mxn_cap), 2) AS importe_mxn "
                          "FROM transacciones_limpias GROUP BY fecha_venta, origen ORDER BY fecha_venta")
    categorias = filas(conn, "SELECT categoria, COUNT(*) AS n, ROUND(SUM(monto_total_mxn_cap), 2) AS importe_mxn "
                             "FROM transacciones_limpias GROUP BY categoria ORDER BY importe_mxn DESC")
    indicadores = fila(conn, "SELECT COUNT(CASE WHEN moneda_original='USD' THEN 1 END) AS convertidas_usd, "
                             "SUM(es_outlier_cantidad) AS outliers_cantidad, SUM(es_outlier_monto) AS outliers_monto, "
                             "MIN(fecha_venta) AS fecha_min, MAX(fecha_venta) AS fecha_max, "
                             "ROUND(AVG(monto_total_mxn), 2) AS ticket_medio_mxn, "
                             "ROUND(SUM(monto_total_mxn_cap), 2) AS importe_total_mxn FROM transacciones_limpias") or {}
    recientes = filas(conn, "SELECT id_error, id_registro, origen, codigos_error, num_motivos FROM cuarentena_errores "
                            "ORDER BY num_motivos DESC, id_error LIMIT 5")
    historial = [_ejecucion_publica(r, bitacora_de(aj, r["lote_id"])) for r in
                 filas(conn, "SELECT * FROM ejecuciones ORDER BY inicio DESC, rowid DESC LIMIT 5")]
    bit = bitacora_de(aj, ult["lote_id"]) if ult else None
    return {
        "hay_datos": ult is not None,
        "ultima_ejecucion": _ejecucion_publica(ult, bit) if ult else None,
        "totales": {"entrada": entrada, "limpias": limpias, "cuarentena": cuarentena,
                    "tasa_aceptacion": _redondeo(limpias / entrada, 4) if entrada else None,
                    "cuadra": entrada == limpias + cuarentena},
        "salud": _salud_origen(conn, entrada, limpias) if entrada else None,
        "canales": canales, "segmentos": segmentos, "motivos": motivos, "por_dia": por_dia, "categorias": categorias,
        "indicadores": {k: (v if v is not None else 0) if k.startswith(("convert", "outliers")) else v for k, v in indicadores.items()},
        "anomalias": [{**r, "codigos": r["codigos_error"].split(";")} for r in recientes],
        "actividad_reciente": historial,
        "advertencias": (bit or {}).get("advertencias", []),
        "nota_historial": ("Las tablas contienen únicamente la última carga completada (snapshot por ejecución). "
                           "El historial disponible es la lista de ejecuciones."),
    }


def _motivos(conn) -> dict:
    """Por código: registros que lo contienen (una transacción con 2 motivos aparece en ambos). `combinaciones`: registros únicos."""
    combos = filas(conn, "SELECT codigos_error AS codigos, COUNT(*) AS registros FROM cuarentena_errores "
                         "GROUP BY codigos_error ORDER BY registros DESC, codigos_error")
    por_codigo: dict[str, int] = {}
    for c in combos:
        for cod in c["codigos"].split(";"):
            por_codigo[cod] = por_codigo.get(cod, 0) + c["registros"]
    etapas = filas(conn, "SELECT etapa_deteccion AS etapa, COUNT(*) AS registros FROM cuarentena_errores "
                         "GROUP BY etapa_deteccion ORDER BY registros DESC")
    return {
        "por_codigo": [{"codigo": k, "registros": v, "descripcion": GLOSARIO_RECHAZOS.get(k)}
                       for k, v in sorted(por_codigo.items(), key=lambda kv: (-kv[1], kv[0]))],
        "combinaciones": [{"codigos": c["codigos"].split(";"), "registros": c["registros"]} for c in combos],
        "por_etapa": etapas,
        "por_canal": filas(conn, "SELECT origen, COUNT(*) AS registros FROM cuarentena_errores GROUP BY origen"),
        "total_registros": escalar(conn, "SELECT COUNT(*) FROM cuarentena_errores"),
        "con_varios_motivos": escalar(conn, "SELECT COUNT(*) FROM cuarentena_errores WHERE num_motivos > 1"),
    }


# ----------------------------------------------------------------------------- transacciones
def facetas(conn) -> dict:
    return {
        "canales": [r[0] for r in conn.execute("SELECT DISTINCT origen FROM transacciones_limpias ORDER BY 1")],
        "categorias": [r[0] for r in conn.execute("SELECT DISTINCT categoria FROM transacciones_limpias ORDER BY 1")],
        "segmentos": ["Bajo", "Medio", "Alto"],
        "estados": [r[0] for r in conn.execute("SELECT DISTINCT estado_pedido FROM transacciones_limpias "
                                               "WHERE estado_pedido IS NOT NULL ORDER BY 1")],
        "proveedores": [r[0] for r in conn.execute("SELECT DISTINCT proveedor FROM catalogo_productos "
                                                   "WHERE proveedor IS NOT NULL ORDER BY 1")],
        "categorias_catalogo": [r[0] for r in conn.execute("SELECT DISTINCT categoria FROM catalogo_productos ORDER BY 1")],
        "rango_fechas": list(conn.execute("SELECT MIN(fecha_venta), MAX(fecha_venta) FROM transacciones_limpias").fetchone()),
        "codigos_rechazo": sorted({c for (cs,) in conn.execute("SELECT DISTINCT codigos_error FROM cuarentena_errores")
                                   for c in cs.split(";")}),
    }


def listar_transacciones(conn, q, canal, desde, hasta, categoria, segmento, estado, orden, direccion, pagina, tam) -> dict:
    donde, p = [], []
    if q:
        donde.append("id_transaccion LIKE ? ESCAPE '\\'")
        p.append(patron_like(q.strip()))
    for sql, valor in (("origen = ?", canal), ("fecha_venta >= ?", desde), ("fecha_venta <= ?", hasta),
                       ("categoria = ?", categoria), ("segmento_importe = ?", segmento), ("estado_pedido = ?", estado)):
        if valor:
            donde.append(sql)
            p.append(valor)
    cond = (" WHERE " + " AND ".join(donde)) if donde else ""
    total = escalar(conn, f"SELECT COUNT(*) FROM transacciones_limpias{cond}", p)
    col = ORDEN_TRANSACCIONES[orden]
    sentido = "DESC" if direccion == "desc" else "ASC"
    items = filas(conn, f"SELECT {COLUMNAS_RESUMEN} FROM transacciones_limpias{cond} ORDER BY {col} {sentido}, id_transaccion "
                        f"LIMIT ? OFFSET ?", [*p, tam, (pagina - 1) * tam])
    resumen = fila(conn, f"SELECT COUNT(*) AS n, ROUND(SUM(monto_total_mxn_cap), 2) AS importe_mxn FROM transacciones_limpias{cond}", p)
    return {**_pagina(total, pagina, tam), "items": items, "resumen_filtro": resumen}


def _campo(campo, antes=None, despues=None, nota=None) -> dict:
    return {"campo": campo, "antes": antes, "despues": despues, "cambio": antes is not None and str(antes) != str(despues),
            "nota": nota}


def _homologacion(fila_db: dict, crudo: dict) -> list[dict]:
    mapeo = MAPEO_FISICA if fila_db["origen"] == "FISICA" else MAPEO_ONLINE
    final = {"id_transaccion": fila_db["id_transaccion"], "fecha_cruda": fila_db["fecha_venta"],
             "punto_venta": fila_db["punto_venta"], "id_producto": fila_db["id_producto"],
             "cantidad": fila_db["cantidad_origen"], "precio_unitario": fila_db["precio_unitario_original"],
             "monto_total": fila_db["monto_total_origen"], "moneda": fila_db["moneda_original"],
             "id_cliente": fila_db["id_cliente"], "email_cliente": fila_db["email_cliente"],
             "direccion_envio": fila_db["direccion_envio"], "metodo_pago": fila_db["metodo_pago"],
             "estado_pedido": fila_db["estado_pedido"]}
    etiqueta = {"fecha_cruda": "fecha", "punto_venta": "punto de venta", "metodo_pago": "método de pago",
                "estado_pedido": "estado del pedido", "id_producto": "producto", "email_cliente": "correo",
                "direccion_envio": "dirección", "id_cliente": "cliente"}
    out = []
    for destino, fuente in mapeo.items():
        if fuente is None or fuente not in crudo or destino in ("cantidad", "precio_unitario", "monto_total", "id_transaccion"):
            continue
        antes, despues = crudo.get(fuente), final[destino]
        if antes in (None, "") and despues in (None, ""):
            continue
        nota = f"columna de origen: {fuente}" if fuente != destino else None
        out.append(_campo(etiqueta.get(destino, destino), antes, despues, nota))
    return out


def _etapas_limpia(r: dict, crudo: dict) -> list[dict]:
    corr = _json(r["correcciones"], [])
    formato = next((c.removeprefix("FECHA_DESDE_") for c in corr if c.startswith("FECHA_DESDE_")), None)
    reparaciones = [c for c in corr if c.startswith(CORRECCIONES_REPARACION)]
    capping = [c for c in corr if c.startswith("CAPPING_")]
    homo = _homologacion(r, crudo)
    for h in homo:
        if h["campo"] == "fecha" and formato:
            h["nota"] = f"formato detectado: {formato} → ISO 8601 (YYYY-MM-DD)"
    homo += [_campo("precio unitario", r["precio_unitario_original"], r["precio_unitario_mxn"],
                    f"{r['moneda_original']} × {r['tipo_cambio_aplicado']:g} → MXN" if r["moneda_original"] == "USD"
                    else "ya estaba en MXN")]
    reparaciones_campos = []
    if r["cantidad_origen"] is not None and r["cantidad_origen"] != r["cantidad"] or any(c.startswith("IMPUTADO_MEDIANA") for c in reparaciones):
        reparaciones_campos.append(_campo("cantidad", r["cantidad_origen"], r["cantidad"]))
    if any(c.startswith("MONTO_RECALCULADO_") for c in reparaciones):
        reparaciones_campos.append(_campo("monto total (origen → MXN)", r["monto_total_origen"], r["monto_total_mxn"],
                                          "recalculado como cantidad × precio"))
    for c in reparaciones:
        if c.startswith("IMPUTADO_") and not c.startswith("IMPUTADO_MEDIANA"):
            campo = c.removeprefix("IMPUTADO_").lower()
            reparaciones_campos.append(_campo(campo, None, r.get(campo), "etiqueta controlada"))
    return [
        {"clave": "original", "titulo": "Dato original", "estado": "ok",
         "descripcion": f"Registro tal como llegó en {'el CSV de tienda física' if r['origen'] == 'FISICA' else 'el JSON online'} "
                        f"(fila {r['id_fila_origen']}).",
         "campos": [_campo(k, v, None) | {"cambio": False} for k, v in crudo.items()], "codigos": []},
        {"clave": "homologacion", "titulo": "Homologación y normalización", "estado": "ok" if homo else "sin_cambios",
         "descripcion": "Esquema unificado, fechas ISO, texto normalizado y conversión de moneda.",
         "campos": homo, "codigos": [c for c in corr if c.startswith(("FECHA_DESDE_", "CONVERTIDO_"))]},
        {"clave": "correcciones", "titulo": "Correcciones", "estado": "corregido" if reparaciones else "sin_cambios",
         "descripcion": "Faltantes imputados e importes recalculados. El valor original se conserva en la base." if reparaciones
         else "Este registro no necesitó reparaciones de valor.",
         "campos": reparaciones_campos, "codigos": reparaciones},
        {"clave": "capping", "titulo": "Tratamiento estadístico (IQR)", "estado": "tratado" if capping else "sin_cambios",
         "descripcion": "Los valores atípicos se recortan en columnas aparte; el valor real nunca se sobrescribe." if capping
         else "Ningún valor de este registro superó los límites del IQR.",
         "campos": [_campo("cantidad → cantidad con capping", r["cantidad"], r["cantidad_cap"]),
                    _campo("importe MXN → importe con capping", r["monto_total_mxn"], r["monto_total_mxn_cap"])],
         "codigos": capping},
        {"clave": "transformacion", "titulo": "Transformación", "estado": "ok",
         "descripcion": "Escalamiento Min-Max a [0, 1] y segmento por terciles, calculados sobre la base estadística.",
         "campos": [_campo("monto_minmax", None, r["monto_minmax"]), _campo("segmento_importe", None, r["segmento_importe"])],
         "codigos": []},
        {"clave": "validacion", "titulo": "Validación Pydantic", "estado": "aceptado",
         "descripcion": "Cumplió todas las reglas del modelo: se prepara para la tabla final.",
         "campos": [], "codigos": _json(r["alertas"], [])},
        {"clave": "resultado", "titulo": "Resultado", "estado": "aceptado",
         "descripcion": f"Cargada en transacciones_limpias (lote {r['lote_id']}).", "campos": [], "codigos": []},
    ]


def _moneda(r: dict) -> dict:
    """Conceptos monetarios de una transacción, SOLO con campos persistidos. Para MXN no hay conversión que mostrar."""
    usd = r["moneda_original"] == "USD"
    capping = abs((r["monto_total_mxn_cap"] or 0) - (r["monto_total_mxn"] or 0)) > 0.005
    out = {"moneda_original": r["moneda_original"], "es_usd": usd, "tipo_cambio": r["tipo_cambio_aplicado"] if usd else None,
           "precio_original": r["precio_unitario_original"], "importe_original": r["monto_total_origen"],
           "precio_mxn": r["precio_unitario_mxn"], "importe_mxn": r["monto_total_mxn"], "importe_mxn_capping": r["monto_total_mxn_cap"],
           "capping_aplicado": capping,
           "importe_original_coherente": None, "importe_original_corregido": False,
           "formula": None}
    if usd:
        out["importe_original_coherente"] = round((r["cantidad"] or 0) * (r["precio_unitario_original"] or 0), 2)
        corr = _json(r["correcciones"], []) if isinstance(r["correcciones"], str) else r["correcciones"]
        out["importe_original_corregido"] = any(c.startswith("MONTO_RECALCULADO_") for c in corr)
        out["formula"] = (f"precio MXN = redondear(precio USD × {r['tipo_cambio_aplicado']:g}); "
                          "importe MXN = redondear(cantidad × precio MXN)")
    return out


def detalle_transaccion(conn, id_transaccion: str) -> dict:
    r = fila(conn, "SELECT * FROM transacciones_limpias WHERE id_transaccion = ?", (id_transaccion,))
    if r is None:
        raise ErrorApi("TRANSACCION_NO_ENCONTRADA", f"No existe la transacción limpia «{id_transaccion}».", 404)
    crudo = _json(r["registro_original"], {})
    relacionadas = filas(conn, "SELECT id_error, id_registro, origen, id_fila_origen, etapa_deteccion, codigos_error, "
                               "num_motivos, motivo_rechazo_cuarentena, fecha_cuarentena, lote_id FROM cuarentena_errores "
                               "WHERE id_registro = ?", (id_transaccion,))
    r["alertas"], r["correcciones"] = _json(r["alertas"], []), _json(r["correcciones"], [])
    fila_pub = {k: v for k, v in r.items() if k != "registro_original"}
    etapas = _etapas_limpia({**r, "alertas": json.dumps(r["alertas"]), "correcciones": json.dumps(r["correcciones"])}, crudo)
    return {"transaccion": fila_pub, "registro_original": crudo, "trazabilidad": etapas, "moneda": _moneda(r),
            "glosario": {c: GLOSARIO_CORRECCIONES.get(c) or ("Formato de fecha de origen." if c.startswith("FECHA_DESDE_") else None)
                         for c in r["correcciones"]},
            "cuarentena_relacionada": [_cuarentena_publica(x) for x in relacionadas]}


# ----------------------------------------------------------------------------- cuarentena
def _cuarentena_publica(r: dict) -> dict:
    r = dict(r)
    r["codigos"] = r.pop("codigos_error").split(";")
    r["etapas"] = r.pop("etapa_deteccion").split(";")
    r["motivo"] = r.pop("motivo_rechazo_cuarentena")
    return r


def listar_cuarentena(conn, q, canal, codigo, etapa, orden, direccion, pagina, tam) -> dict:
    donde, p = [], []
    if q:
        donde.append("id_registro LIKE ? ESCAPE '\\'")
        p.append(patron_like(q.strip()))
    if canal:
        donde.append("origen = ?")
        p.append(canal)
    if codigo:
        donde.append("(';' || codigos_error || ';') LIKE ?")
        p.append(f"%;{codigo};%")
    if etapa:
        donde.append("(';' || etapa_deteccion || ';') LIKE ?")
        p.append(f"%;{etapa};%")
    cond = (" WHERE " + " AND ".join(donde)) if donde else ""
    total = escalar(conn, f"SELECT COUNT(*) FROM cuarentena_errores{cond}", p)
    sentido = "DESC" if direccion == "desc" else "ASC"
    items = filas(conn, "SELECT id_error, id_registro, origen, id_fila_origen, etapa_deteccion, codigos_error, num_motivos, "
                        f"motivo_rechazo_cuarentena, fecha_cuarentena, lote_id FROM cuarentena_errores{cond} "
                        f"ORDER BY {ORDEN_CUARENTENA[orden]} {sentido}, id_error LIMIT ? OFFSET ?", [*p, tam, (pagina - 1) * tam])
    return {**_pagina(total, pagina, tam), "items": [_cuarentena_publica(i) for i in items]}


def detalle_cuarentena(conn, id_error: int) -> dict:
    r = fila(conn, "SELECT * FROM cuarentena_errores WHERE id_error = ?", (id_error,))
    if r is None:
        raise ErrorApi("CUARENTENA_NO_ENCONTRADA", f"No existe el registro de cuarentena {id_error}.", 404)
    crudo = _json(r["registro_original"], r["registro_original"])
    detalle = _json(r["detalle_error"], [])
    for d in detalle:
        d["descripcion"] = GLOSARIO_RECHAZOS.get(d.get("codigo"))
    base = _cuarentena_publica({k: v for k, v in r.items() if k not in ("registro_original", "detalle_error")})
    hermana = fila(conn, "SELECT id_transaccion FROM transacciones_limpias WHERE id_transaccion = ?", (r["id_registro"],)) \
        if r["id_registro"] else None
    etapas = [
        {"clave": "original", "titulo": "Dato original", "estado": "ok",
         "descripcion": f"Registro tal como llegó (fila {r['id_fila_origen']} de {r['origen']}).",
         "campos": [_campo(k, v, None) | {"cambio": False} for k, v in (crudo.items() if isinstance(crudo, dict) else [])],
         "codigos": []},
        {"clave": "deteccion", "titulo": "Detección", "estado": "rechazado",
         "descripcion": f"{len(detalle)} motivo(s) detectado(s). La transacción se cuenta una sola vez.",
         "campos": [_campo(d.get("campo") or "—", d.get("entrada"), d.get("mensaje")) | {"cambio": False, "nota": d.get("etapa")}
                    for d in detalle], "codigos": base["codigos"]},
        {"clave": "resultado", "titulo": "Resultado", "estado": "rechazado",
         "descripcion": f"Aislado en cuarentena_errores (lote {r['lote_id']}). Esta sección es de solo consulta.",
         "campos": [], "codigos": []},
    ]
    return {"registro": base, "detalle": detalle, "registro_original": crudo, "trazabilidad": etapas,
            "hay_limpia_con_mismo_id": hermana is not None,
            "glosario": {c: GLOSARIO_RECHAZOS.get(c) for c in base["codigos"]}}


# ----------------------------------------------------------------------------- catálogo
def listar_catalogo(conn, q, categoria, proveedor, orden, direccion, pagina, tam) -> dict:
    donde, p = [], []
    if q:
        donde.append("(p.id_producto LIKE ? ESCAPE '\\' OR p.nombre_producto LIKE ? ESCAPE '\\')")
        p += [patron_like(q.strip())] * 2
    if categoria:
        donde.append("p.categoria = ?")
        p.append(categoria)
    if proveedor:
        donde.append("p.proveedor = ?")
        p.append(proveedor)
    cond = (" WHERE " + " AND ".join(donde)) if donde else ""
    total = escalar(conn, f"SELECT COUNT(*) FROM catalogo_productos p{cond}", p)
    sentido = "DESC" if direccion == "desc" else "ASC"
    items = filas(conn, "SELECT p.id_producto, p.nombre_producto, p.categoria, p.precio_base_mxn, p.stock_minimo, p.proveedor, "
                        "COUNT(t.id_transaccion) AS ventas, COALESCE(SUM(t.cantidad), 0) AS unidades, "
                        "ROUND(COALESCE(SUM(t.monto_total_mxn_cap), 0), 2) AS importe "
                        "FROM catalogo_productos p LEFT JOIN transacciones_limpias t USING (id_producto)"
                        f"{cond} GROUP BY p.id_producto ORDER BY {ORDEN_CATALOGO[orden]} {sentido}, p.id_producto "
                        "LIMIT ? OFFSET ?", [*p, tam, (pagina - 1) * tam])
    por_categoria = filas(conn, "SELECT categoria, COUNT(*) AS productos, ROUND(AVG(precio_base_mxn), 2) AS precio_medio "
                                "FROM catalogo_productos GROUP BY categoria ORDER BY productos DESC")
    return {**_pagina(total, pagina, tam), "items": items, "por_categoria": por_categoria,
            "huerfanos": escalar(conn, "SELECT COUNT(*) FROM cuarentena_errores WHERE (';' || codigos_error || ';') "
                                       "LIKE '%;PRODUCTO_HUERFANO;%'")}


# ----------------------------------------------------------------------------- ejecuciones y reportes
def _fases(bit: dict | None, etapa_fallida: str | None = None) -> list[dict]:
    dur = (bit or {}).get("duracion_etapas_s", {})
    estado_corrida = (bit or {}).get("estado")
    fallida = etapa_fallida or (bit or {}).get("etapa_fallida")
    out = []
    for f in FASES:
        presentes = [e for e in f["etapas"] if e in dur]
        if fallida and fallida in f["etapas"]:
            estado = "FALLIDA"
        elif len(presentes) == len(f["etapas"]):
            estado = "COMPLETADA"
        elif presentes:
            estado = "PARCIAL"
        else:
            estado = "NO_EJECUTADA" if bit else "SIN_DATOS"
        out.append({**{k: v for k, v in f.items() if k != "etapas"}, "etapas_internas": f["etapas"], "estado": estado,
                    "duracion_s": round(sum(dur[e] for e in presentes), 3) if presentes else None,
                    "metricas": _metricas_fase(f["clave"], bit) if estado == "COMPLETADA" else {}})
    if estado_corrida == "COMPLETADO":
        for f in out:
            f.setdefault("verificada", True)
    return out


def _metricas_fase(clave: str, bit: dict | None) -> dict:
    if not bit:
        return {}
    lim, iqr, tr, va, ca = (bit.get(k) or {} for k in ("limpieza", "iqr", "transformacion", "validacion", "carga"))
    if clave == "diagnostico":
        return {"filas_fuentes": bit.get("filas_fuentes"), "integridad_originales": bit.get("integridad_originales")}
    if clave == "faltantes":
        return {"duplicados_marcados": lim.get("duplicados_exactos"),
                "montos_recalculados": (lim.get("reconstruccion_montos") or {}).get("recalculados_nulo", 0)
                + (lim.get("reconstruccion_montos") or {}).get("recalculados_inconsistente", 0),
                "etiquetas": lim.get("imputacion_categoricas")}
    if clave == "outliers":
        m = iqr.get("monto_mxn") or {}
        return {"base_estadistica": (iqr.get("base_estadistica") or {}).get("total"), "limite_superior_monto": m.get("LS"),
                "montos_recortados": m.get("recortados")}
    if clave == "integracion":
        return {"filas": bit.get("filas_entrada")}
    if clave == "transformacion":
        return {"min": (tr.get("minmax") or {}).get("min"), "max": (tr.get("minmax") or {}).get("max"),
                "cortes": [(tr.get("segmentos") or {}).get("corte_bajo_medio"), (tr.get("segmentos") or {}).get("corte_medio_alto")]}
    if clave == "validacion":
        return {"validos": va.get("validos"), "cuarentena": va.get("cuarentena"), "errores_inesperados": va.get("errores_inesperados")}
    if clave == "carga":
        return {"estado": ca.get("estado"), "limpias": ca.get("limpias"), "cuarentena": ca.get("cuarentena")}
    return {}


def listar_ejecuciones(conn, aj: Ajustes, estado) -> dict:
    cond, p = ("WHERE estado = ?", [estado]) if estado else ("", [])
    rows = filas(conn, f"SELECT * FROM ejecuciones {cond} ORDER BY inicio DESC, rowid DESC", p)
    items = [_ejecucion_publica(r, bitacora_de(aj, r["lote_id"])) for r in rows]
    for i in items:
        i["tiene_log"] = (aj.dir_salida / "logs" / f"pipeline_{i['lote_id']}.log").is_file()
    return {"items": items, "total": len(items),
            "nota": "Las tablas de datos reflejan solo la última ejecución completada; aquí se muestra el historial registrado."}


def detalle_ejecucion(conn, aj: Ajustes, lote_id: str) -> dict:
    if not RE_LOTE.match(lote_id):
        raise ErrorApi("LOTE_INVALIDO", "Identificador de ejecución inválido.", 422)
    r = fila(conn, "SELECT * FROM ejecuciones WHERE lote_id = ?", (lote_id,))
    if r is None:
        raise ErrorApi("EJECUCION_NO_ENCONTRADA", f"No existe la ejecución «{lote_id}».", 404)
    bit = bitacora_de(aj, lote_id)
    log = aj.dir_salida / "logs" / f"pipeline_{lote_id}.log"
    lineas = log.read_text(encoding="utf-8", errors="replace").splitlines()[-300:] if log.is_file() else None
    return {"ejecucion": _ejecucion_publica(r, bit), "fases": _fases(bit, r.get("etapa_fallida")),
            "entorno": _json(r.get("entorno"), {}), "huellas_entrada": _json(r.get("huellas_entrada"), {}),
            "duracion_etapas_s": (bit or {}).get("duracion_etapas_s", {}), "log": lineas,
            "bitacora_disponible": bit is not None,
            "reportes_ejecucion": {"carpeta": "etapa_nono", "bitacora": f"bitacoras/bitacora_{lote_id}.json" if bit else None}}


def listar_reportes(aj: Ajustes) -> dict:
    grupos = []
    for carpeta in CARPETAS_REPORTES:
        base = aj.raiz_salidas / carpeta if carpeta != "etapa_nono" else aj.dir_salida
        if not base.is_dir():
            continue
        archivos = []
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTENSIONES_REPORTE and p.parent.name not in ("logs",):
                rel = p.relative_to(base).as_posix()
                archivos.append({"ruta": rel, "nombre": p.name, "tipo": p.suffix.lower().lstrip("."),
                                 "bytes": p.stat().st_size, "modificado": p.stat().st_mtime,
                                 "url": f"/api/reportes/{carpeta}/{rel}"})
        grupos.append({"carpeta": carpeta, "archivos": archivos})
    return {"grupos": grupos}


def resolver_reporte(aj: Ajustes, carpeta: str, ruta: str) -> tuple[Path, str]:
    """Resuelve un archivo de reporte SOLO si está dentro de una carpeta permitida y tiene extensión permitida."""
    if carpeta not in CARPETAS_REPORTES:
        raise ErrorApi("REPORTE_NO_ENCONTRADO", "Carpeta de reportes no permitida.", 404)
    base = (aj.raiz_salidas / carpeta if carpeta != "etapa_nono" else aj.dir_salida).resolve()
    destino = (base / ruta).resolve()
    if base not in destino.parents or not destino.is_file() or destino.suffix.lower() not in EXTENSIONES_REPORTE:
        raise ErrorApi("REPORTE_NO_ENCONTRADO", "El reporte solicitado no existe.", 404)
    return destino, EXTENSIONES_REPORTE[destino.suffix.lower()]


# ----------------------------------------------------------------------------- calidad
NOTA_MCAR = ("«MCAR» significa que los faltantes no dependen de las otras variables observadas. Con las pruebas χ² de "
             "independencia realizadas (α = 0.05) no se encontró evidencia de dependencia (p > 0.05), por lo que los faltantes "
             "son COMPATIBLES con MCAR. Eso no demuestra MCAR de forma absoluta: un p-valor alto no prueba la hipótesis nula, "
             "y la prueba solo evalúa las variables comparadas. Algunas tablas tienen frecuencias esperadas menores que 5, "
             "donde la aproximación χ² pierde precisión.")


def _leer_json(ruta: Path):
    return _json(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def _leer_csv(ruta: Path):
    if not ruta.is_file():
        return None
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def calidad(conn, aj: Ajustes) -> dict:
    ult = fila(conn, "SELECT lote_id FROM ejecuciones WHERE estado='COMPLETADO' ORDER BY fin DESC, inicio DESC, rowid DESC LIMIT 1")
    bit = bitacora_de(aj, ult["lote_id"]) if ult else None
    leslie = aj.raiz_salidas / "etapa_leslie"
    perfil = _leer_json(leslie / "01_perfil_antes.json")
    mcar = _leer_json(leslie / "02_faltantes_mcar_mar.json")
    antes_despues = _leer_csv(leslie / "06_antes_despues.csv")
    graficas = []
    for nombre, titulo, descr in (("boxplot_cantidad_fisica.png", "Cantidad por ticket · tienda física",
                                   "Antes y después del capping (escala logarítmica)."),
                                  ("boxplot_importe_mxn.png", "Importe por transacción en MXN",
                                   "Total crudo frente a monto_total_mxn_cap en la base estadística.")):
        if (leslie / "graficas" / nombre).is_file():
            graficas.append({"id": nombre, "titulo": titulo, "descripcion": descr,
                             "url": f"/api/reportes/etapa_leslie/graficas/{nombre}", "fuente": "etapa_leslie"})
    return {
        "lote_id": ult["lote_id"] if ult else None,
        "limpieza": (bit or {}).get("limpieza"), "iqr": (bit or {}).get("iqr"),
        "transformacion": (bit or {}).get("transformacion"),
        "perfil_antes": perfil, "faltantes": mcar, "antes_despues": antes_despues, "graficas": graficas,
        "nota_mcar": NOTA_MCAR,
        "distincion": {
            "originales": "Valores tal como llegaron (cantidad_origen, monto_total_origen, precio_unitario_original, fecha_cruda, registro_original).",
            "corregidos": "Faltantes imputados e importes recalculados (códigos IMPUTADO_* y MONTO_RECALCULADO_*).",
            "tratados": "Valores atípicos recortados con IQR en columnas aparte (cantidad_cap, monto_total_mxn_cap)."},
        "conteo_correcciones": (bit or {}).get("limpieza", {}).get("conteo_correcciones"),
        "fuentes": {"bitacora": f"bitacora_{ult['lote_id']}.json" if ult and bit else None,
                    "reportes_leslie_disponibles": perfil is not None,
                    "nota": "El perfil inicial, el MCAR/MAR y la tabla antes/después provienen de los reportes de la etapa de Leslie "
                            "(salidas/etapa_leslie); los conteos de limpieza e IQR, de la bitácora de la última ejecución."},
    }
