"""
Pruebas de estrés con datos corruptos (responsable: Nono · guía §8).

Los archivos ORIGINALES (datos/crudos/) solo se LEEN: este módulo copia registros reales, inyecta defectos y escribe
los archivos corruptos en un directorio de trabajo (temporal en las pruebas). Cada escenario declara qué debe pasar.

    python datos/estres/generar_estres.py [CARPETA_SALIDA]     # corre todo y escribe resultados_estres.csv

`ejecutar_todo()` es la ÚNICA implementación de los escenarios: la usan `tests/test_estres.py` y este script.

Criterio para los escenarios por registro:
- esperado "VALIDO": el registro termina en transacciones_limpias.
- esperado = conjunto de códigos: el registro termina en cuarentena y su `codigos_error` CONTIENE esos códigos
  (puede contener más: p. ej. un precio inválido arrastra un monto inconsistente).
"""
from __future__ import annotations

import copy
import csv
import json
import random
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from src.config import RUTAS_FUENTES  # noqa: E402
from src.contratos import COLUMNAS_FISICA, COLUMNAS_ONLINE  # noqa: E402
from src.pipeline import ejecutar_pipeline  # noqa: E402

HOY = date(2026, 10, 25)                      # fecha de referencia fija: las pruebas no dependen del reloj
N_BASE = 80                                   # filas reales copiadas como contexto de cada archivo
PLANTILLA_FISICA, PLANTILLA_ONLINE = "POS-2026-0002", "WEB-00003"     # registros reales 100 % válidos
V = "VALIDO"


# ----------------------------------------------------------------------------- lectura de plantillas reales
def _leer_csv_real() -> list[dict]:
    with open(RUTAS_FUENTES["fisica"], encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _leer_json_real() -> list[dict]:
    return json.loads(Path(RUTAS_FUENTES["online"]).read_text(encoding="utf-8"))


def _escribir_csv(ruta: Path, filas: list[dict], columnas=COLUMNAS_FISICA) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def _escribir_json(ruta: Path, registros) -> None:
    Path(ruta).write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------------------- escenarios por registro
def _escenarios_fisica(p: dict) -> list[tuple]:
    """(id, descripción, registro, esperado). `p` = plantilla CSV válida."""
    def r(**cambios):
        return {**p, **cambios}
    return [
        ("E01", "cantidad = 'dos' (texto)", r(id_ticket="POS-2026-9001", cantidad="dos"), {"CANTIDAD_INVALIDA"}),
        ("E02", "cantidad = 2.5 (no entera)", r(id_ticket="POS-2026-9002", cantidad="2.5"), {"CANTIDAD_INVALIDA"}),
        ("E03", "cantidad y monto vacíos (imputación + recálculo)",
         r(id_ticket="POS-2026-9003", cantidad="", monto_total_mxn=""), V),
        ("E04", "precio_unitario = -10", r(id_ticket="POS-2026-9004", precio_unitario="-10"), {"PRECIO_INVALIDO"}),
        ("E05", "precio_unitario = 'abc' (texto)", r(id_ticket="POS-2026-9005", precio_unitario="abc"), {"PRECIO_INVALIDO"}),
        ("E06", "fecha imposible 31/02/2026", r(id_ticket="POS-2026-9006", fecha_venta="31/02/2026"), {"FECHA_INVALIDA"}),
        ("E07", "fecha futura 2027-01-01", r(id_ticket="POS-2026-9007", fecha_venta="2027-01-01"), {"FECHA_INVALIDA"}),
        ("E08", "cantidad = 0", r(id_ticket="POS-2026-9008", cantidad="0", monto_total_mxn="0"),
         {"CANTIDAD_INVALIDA", "MONTO_INVALIDO"}),
        ("E09", "cantidad negativa -3", r(id_ticket="POS-2026-9009", cantidad="-3", monto_total_mxn="-3506.37"),
         {"CANTIDAD_INVALIDA", "MONTO_INVALIDO"}),
        ("E10", "producto inexistente PROD-999", r(id_ticket="POS-2026-9010", id_producto="PROD-999"), {"PRODUCTO_HUERFANO"}),
        ("E11", "ID con formato inválido 'POS-1'", r(id_ticket="POS-1"), {"ID_FORMATO_INVALIDO"}),
        ("E12", "inyección SQL en el ID", r(id_ticket="'; DROP TABLE transacciones_limpias;--"), {"ID_FORMATO_INVALIDO"}),
        ("E13", "total ×80 (importe inconsistente reparable)",
         r(id_ticket="POS-2026-9013", monto_total_mxn="93502.40"), V),
        ("E14", "fecha con formato desconocido 'ayer'", r(id_ticket="POS-2026-9014", fecha_venta="ayer"), {"FECHA_INVALIDA"}),
        ("E15", "método de pago en minúsculas (homologable)", r(id_ticket="POS-2026-9015", metodo_pago="  efectivo "), V),
        ("E16", "plantilla sin cambios con otro ID (control)", r(id_ticket="POS-2026-9016"), V),
    ]


def _escenarios_online(p: dict) -> list[tuple]:
    def r(**cambios):
        return {**p, **cambios}

    def sin(campo, **cambios):
        d = {k: v for k, v in p.items() if k != campo}
        d.update(cambios)
        return d
    return [
        ("E20", "order_timestamp = 'ayer'", r(order_id="WEB-90020", order_timestamp="ayer"), {"FECHA_INVALIDA"}),
        ("E21", "currency = 'EUR'", r(order_id="WEB-90021", currency="EUR"), {"MONEDA_NO_SOPORTADA"}),
        ("E22", "product_id = null", r(order_id="WEB-90022", product_id=None), {"PRODUCTO_HUERFANO"}),
        ("E23", "customer_email = 'a@b'", r(order_id="WEB-90023", customer_email="a@b"), {"EMAIL_MALFORMADO"}),
        ("E24", "order_id = 'WEB-1'", r(order_id="WEB-1"), {"ID_FORMATO_INVALIDO"}),
        ("E25", "inyección SQL en order_id", r(order_id="'; DROP TABLE transacciones_limpias;--"), {"ID_FORMATO_INVALIDO"}),
        ("E26", "mismo order_id con dos contenidos (1/2)", r(order_id="WEB-90026", units=1), {"ID_REPETIDO_CONFLICTO"}),
        ("E27", "mismo order_id con dos contenidos (2/2)", r(order_id="WEB-90026", units=2, total_amount=2457.44),
         {"ID_REPETIDO_CONFLICTO"}),
        ("E28", "registro sin el campo 'units'", sin("units", order_id="WEB-90028"), V),
        ("E29", "campo extra {'hacker': true}", r(order_id="WEB-90029", hacker=True), V),
        ("E30", "total_amount = 1e308", r(order_id="WEB-90030", total_amount=1e308), V),
        ("E31", "dirección con emoji y acentos", r(order_id="WEB-90031", shipping_address="Calle Ñandú 5 😀, Colima"), V),
        ("E32", "registro sin order_id (campo ausente)", sin("order_id"), {"TIPO_INVALIDO"}),
        ("E33", "tipos incorrectos: units lista, unit_price objeto",
         r(order_id="WEB-90033", units=[1, 2], unit_price={"x": 1}), {"CANTIDAD_INVALIDA", "PRECIO_INVALIDO"}),
        ("E34", "order_status fuera del catálogo 'ENVIADO' [propuesta]", r(order_id="WEB-90034", order_status="ENVIADO"),
         {"ESTADO_INVALIDO"}),
        ("E35", "correo vacío '' (faltante ≠ malformado)", r(order_id="WEB-90035", customer_email=""), V),
        ("E36", "correo con doble arroba", r(order_id="WEB-90036", customer_email="usuario@@gmail..com"), {"EMAIL_MALFORMADO"}),
        ("E37", "units = 0", r(order_id="WEB-90037", units=0, total_amount=0), {"CANTIDAD_INVALIDA"}),
        ("E38", "order_status vacío (obligatorio online)", r(order_id="WEB-90038", order_status=None), {"ESTADO_INVALIDO"}),
        ("E39", "unit_price = null", r(order_id="WEB-90039", unit_price=None), {"PRECIO_FALTANTE"}),
        ("E40", "timestamp epoch inválido (13 dígitos, ms)", r(order_id="WEB-90040", order_timestamp=1789105020000), {"FECHA_INVALIDA"}),
    ]


def construir_dataset_filas(dir_trabajo: Path) -> tuple[dict, list[dict]]:
    """Escribe catálogo (copia), CSV y JSON corruptos. Devuelve (rutas, escenarios con la fila donde quedaron)."""
    dir_trabajo = Path(dir_trabajo)
    dir_trabajo.mkdir(parents=True, exist_ok=True)
    csv_real, json_real = _leer_csv_real(), _leer_json_real()
    p_fis = next(f for f in csv_real if f["id_ticket"] == PLANTILLA_FISICA)
    p_onl = next(o for o in json_real if o["order_id"] == PLANTILLA_ONLINE)
    filas_csv, filas_json = copy.deepcopy(csv_real[:N_BASE]), copy.deepcopy(json_real[:N_BASE])
    escenarios: list[dict] = []
    for sid, desc, reg, esp in _escenarios_fisica(p_fis):
        filas_csv.append(reg)
        escenarios.append({"id": sid, "descripcion": desc, "canal": "FISICA", "fila": len(filas_csv), "esperado": esp})
    # duplicado exacto de un registro corrupto-pero-válido (E17): se repite la fila de E16
    dup = copy.deepcopy(filas_csv[-1])
    filas_csv.append(dup)
    escenarios.append({"id": "E17", "descripcion": "fila duplicada exacta (2.ª aparición)", "canal": "FISICA",
                       "fila": len(filas_csv), "esperado": {"DUPLICADO_EXACTO"}})
    for sid, desc, reg, esp in _escenarios_online(p_onl):
        filas_json.append(reg)
        escenarios.append({"id": sid, "descripcion": desc, "canal": "ONLINE", "fila": len(filas_json), "esperado": esp})
    rutas = {"catalogo": dir_trabajo / "catalogo_productos.csv", "fisica": dir_trabajo / "ventas_tienda_fisica.csv",
             "online": dir_trabajo / "ventas_online.json"}
    shutil.copyfile(RUTAS_FUENTES["catalogo"], rutas["catalogo"])
    _escribir_csv(rutas["fisica"], filas_csv)
    _escribir_json(rutas["online"], filas_json)
    return rutas, escenarios


# ----------------------------------------------------------------------------- ejecución y evaluación
def _consultar(ruta_bd, sql, params=()):
    with closing(sqlite3.connect(str(ruta_bd))) as c:
        return c.execute(sql, params).fetchall()


def _invariantes(ruta_bd, n_entrada: int) -> dict:
    """Afirmaciones que deben cumplirse en TODA ejecución completada (guía §8.2)."""
    n_ok = _consultar(ruta_bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0]
    n_qz = _consultar(ruta_bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0]
    return {
        "conserva_conteo": n_ok + n_qz == n_entrada,
        "cuarentena_sin_motivo_vacio": _consultar(
            ruta_bd, "SELECT COUNT(*) FROM cuarentena_errores WHERE trim(motivo_rechazo_cuarentena) = ''")[0][0] == 0,
        "fechas_iso_en_limpias": _consultar(
            ruta_bd, "SELECT COUNT(*) FROM transacciones_limpias "
                     "WHERE fecha_venta NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")[0][0] == 0,
        "tabla_limpias_existe": bool(_consultar(ruta_bd, "SELECT name FROM sqlite_master WHERE name='transacciones_limpias'")),
        "limpias": n_ok, "cuarentena": n_qz,
    }


def _clasificar(ruta_bd, canal: str, fila: int) -> tuple[str, set, str]:
    q = _consultar(ruta_bd, "SELECT codigos_error, motivo_rechazo_cuarentena FROM cuarentena_errores "
                            "WHERE origen=? AND id_fila_origen=?", (canal, fila))
    if q:
        return "CUARENTENA", set(q[0][0].split(";")), q[0][1]
    ok = _consultar(ruta_bd, "SELECT 1 FROM transacciones_limpias WHERE origen=? AND id_fila_origen=?", (canal, fila))
    return ("VALIDO" if ok else "PERDIDO"), set(), ""


def ejecutar_escenarios_fila(dir_trabajo: Path) -> tuple[list[dict], dict]:
    rutas, escenarios = construir_dataset_filas(dir_trabajo)
    bd = Path(dir_trabajo) / "estres_filas.db"
    r = ejecutar_pipeline(rutas, bd, Path(dir_trabajo) / "salida", hoy=HOY, generar_reportes=False)
    out = []
    for e in escenarios:
        if r["estado"] != "COMPLETADO":
            obtenido, codigos, motivo = "PIPELINE_FALLIDO", set(), r.get("error", "")
        else:
            obtenido, codigos, motivo = _clasificar(bd, e["canal"], e["fila"])
        esperado = e["esperado"]
        ok = (obtenido == "VALIDO") if esperado == V else (obtenido == "CUARENTENA" and esperado <= codigos)
        out.append({"id": e["id"], "escenario": e["descripcion"], "canal": e["canal"], "fila": e["fila"],
                    "esperado": V if esperado == V else "CUARENTENA ⊇ " + ";".join(sorted(esperado)),
                    "obtenido": obtenido if obtenido != "CUARENTENA" else "CUARENTENA " + ";".join(sorted(codigos)),
                    "ok": bool(ok), "motivo": motivo})
    extra = {"resumen": r, "bd": bd, "n_entrada": r.get("filas_entrada"),
             "invariantes": _invariantes(bd, r["filas_entrada"]) if r["estado"] == "COMPLETADO" else None}
    return out, extra


def _dataset_base(dir_trabajo: Path, n: int = N_BASE) -> dict:
    d = Path(dir_trabajo)
    d.mkdir(parents=True, exist_ok=True)
    rutas = {"catalogo": d / "catalogo_productos.csv", "fisica": d / "ventas_tienda_fisica.csv",
             "online": d / "ventas_online.json"}
    shutil.copyfile(RUTAS_FUENTES["catalogo"], rutas["catalogo"])
    _escribir_csv(rutas["fisica"], _leer_csv_real()[:n])
    _escribir_json(rutas["online"], _leer_json_real()[:n])
    return rutas


def _res(id_, desc, esperado, obtenido, ok, detalle="") -> dict:
    return {"id": id_, "escenario": desc, "canal": "GLOBAL", "fila": "", "esperado": esperado, "obtenido": obtenido,
            "ok": bool(ok), "motivo": detalle}


def ejecutar_escenarios_globales(dir_trabajo: Path) -> list[dict]:
    d = Path(dir_trabajo)
    resultados = []

    def correr(rutas, bd, **kw):
        return ejecutar_pipeline(rutas, bd, d / "salida_g", hoy=HOY, generar_reportes=False, **kw)

    # G01 archivo JSON vacío []
    rutas = _dataset_base(d / "g01")
    _escribir_json(rutas["online"], [])
    r = correr(rutas, d / "g01" / "bd.db")
    inv = _invariantes(d / "g01" / "bd.db", r.get("filas_entrada", -1)) if r["estado"] == "COMPLETADO" else {}
    resultados.append(_res("G01", "JSON online vacío []", "COMPLETADO y conserva el conteo", f"{r['estado']} {inv}",
                           r["estado"] == "COMPLETADO" and inv.get("conserva_conteo") and r["filas_por_origen"].get("ONLINE", 0) == 0,
                           r.get("error", "")))

    # G02 JSON truncado: FALLIDO con mensaje claro y la BD anterior intacta
    rutas = _dataset_base(d / "g02")
    bd = d / "g02" / "bd.db"
    previa = correr(rutas, bd)
    antes = _consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0], \
        _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0]
    rutas["online"].write_text('[{"order_id": "WEB-', encoding="utf-8")
    r = correr(rutas, bd)
    despues = _consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0], \
        _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0]
    hist = _consultar(bd, "SELECT estado FROM ejecuciones ORDER BY inicio")
    ok = (previa["estado"] == "COMPLETADO" and r["estado"] == "FALLIDO" and r["tipo_error"] == "ErrorExtraccion"
          and antes == despues and [h[0] for h in hist] == ["COMPLETADO", "FALLIDO"] and "traceback" not in r)
    resultados.append(_res("G02", "JSON truncado (archivo corrupto)", "FALLIDO controlado; BD anterior intacta",
                           f"{r['estado']} {r.get('tipo_error')}; BD {antes}→{despues}; historial {[h[0] for h in hist]}",
                           ok, r.get("error", "")))

    # G03 archivo inexistente
    rutas = _dataset_base(d / "g03")
    rutas["fisica"].unlink()
    r = correr(rutas, d / "g03" / "bd.db")
    resultados.append(_res("G03", "CSV de ventas inexistente", "FALLIDO ErrorExtraccion", f"{r['estado']} {r.get('tipo_error')}",
                           r["estado"] == "FALLIDO" and r.get("tipo_error") == "ErrorExtraccion", r.get("error", "")))

    # G04 CSV sin columnas del contrato
    rutas = _dataset_base(d / "g04")
    rutas["fisica"].write_text("id_ticket,cantidad\nPOS-2026-0001,1\n", encoding="utf-8")
    r = correr(rutas, d / "g04" / "bd.db")
    resultados.append(_res("G04", "CSV con columnas faltantes", "FALLIDO ErrorExtraccion", f"{r['estado']} {r.get('tipo_error')}",
                           r["estado"] == "FALLIDO" and r.get("tipo_error") == "ErrorExtraccion", r.get("error", "")))

    # G05 JSON válido pero no es una lista de objetos
    rutas = _dataset_base(d / "g05")
    rutas["online"].write_text(json.dumps({"order_id": "WEB-00001"}), encoding="utf-8")
    r = correr(rutas, d / "g05" / "bd.db")
    resultados.append(_res("G05", "JSON que no es lista de objetos", "FALLIDO ErrorExtraccion", f"{r['estado']} {r.get('tipo_error')}",
                           r["estado"] == "FALLIDO" and r.get("tipo_error") == "ErrorExtraccion", r.get("error", "")))

    # G06 falla forzada a mitad de la carga: rollback y 0 filas parciales (la BD conserva la carga anterior)
    rutas = _dataset_base(d / "g06")
    bd = d / "g06" / "bd.db"
    previa = correr(rutas, bd)
    snap = (_consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0],
            _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0])
    from src.persistencia import carga as modulo_carga
    original = modulo_carga._insertar

    def falla_en_limpias(conn, tabla, filas):
        if tabla == "transacciones_limpias":
            raise sqlite3.OperationalError("disco lleno (simulado)")
        return original(conn, tabla, filas)

    with mock.patch.object(modulo_carga, "_insertar", falla_en_limpias):
        r = correr(rutas, bd)
    snap2 = (_consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0],
             _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0])
    catalogo_n = _consultar(bd, "SELECT COUNT(*) FROM catalogo_productos")[0][0]
    ok = (r["estado"] == "FALLIDO" and r.get("tipo_error") == "ErrorCarga" and snap == snap2 and catalogo_n == 50
          and "Carga revertida (rollback)" in r["error"])
    resultados.append(_res("G06", "Falla de persistencia a mitad de la carga", "ErrorCarga + rollback; 0 filas parciales",
                           f"{r['estado']} {r.get('tipo_error')}; BD {snap}→{snap2}; catálogo {catalogo_n}", ok, r.get("error", "")))

    # G07 volumen: los registros reales ×10 barajados
    rutas = _dataset_base(d / "g07", n=10 ** 6)
    filas = _leer_csv_real() * 10
    regs = _leer_json_real() * 10
    random.Random(2026).shuffle(filas)
    random.Random(2026).shuffle(regs)
    _escribir_csv(rutas["fisica"], filas)
    _escribir_json(rutas["online"], regs)
    t0 = time.perf_counter()
    r = correr(rutas, d / "g07" / "bd.db")
    seg = round(time.perf_counter() - t0, 2)
    inv = _invariantes(d / "g07" / "bd.db", r.get("filas_entrada", -1)) if r["estado"] == "COMPLETADO" else {}
    resultados.append(_res("G07", "Volumen: 12,200 registros (reales ×10, barajados)", "COMPLETADO y conserva el conteo",
                           f"{r['estado']} en {seg} s; limpias={inv.get('limpias')} cuarentena={inv.get('cuarentena')}",
                           r["estado"] == "COMPLETADO" and inv.get("conserva_conteo") and r["filas_entrada"] == 12200,
                           r.get("error", "")))

    # G08 originales alterados: la huella SHA-256 no coincide
    rutas = _dataset_base(d / "g08")
    r = correr(rutas, d / "g08" / "bd.db", verificar_huellas=True)
    resultados.append(_res("G08", "Archivo original con huella SHA-256 distinta", "FALLIDO ErrorIntegridad",
                           f"{r['estado']} {r.get('tipo_error')}", r["estado"] == "FALLIDO" and r.get("tipo_error") == "ErrorIntegridad",
                           r.get("error", "")))

    # G09 idempotencia: dos ejecuciones iguales no duplican filas y dejan 2 filas de historial
    rutas = _dataset_base(d / "g09")
    bd = d / "g09" / "bd.db"
    correr(rutas, bd)
    c1 = (_consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0], _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0])
    correr(rutas, bd)
    c2 = (_consultar(bd, "SELECT COUNT(*) FROM transacciones_limpias")[0][0], _consultar(bd, "SELECT COUNT(*) FROM cuarentena_errores")[0][0])
    n_ej = _consultar(bd, "SELECT COUNT(*) FROM ejecuciones")[0][0]
    resultados.append(_res("G09", "Ejecución repetida sobre los mismos datos", "mismas filas; 2 ejecuciones en el historial",
                           f"BD {c1}→{c2}; ejecuciones={n_ej}", c1 == c2 and n_ej == 2))

    # G10 excepción IMPREVISTA en una etapa: FALLIDO clasificado como imprevisto, con traceback en el log, sin propagarse
    rutas = _dataset_base(d / "g10")
    with mock.patch("src.pipeline.tratar_outliers", side_effect=RuntimeError("fallo simulado en IQR")):
        r = correr(rutas, d / "g10" / "bd.db")
    log_existe = any((d / "salida_g" / "logs").glob("*.log"))
    resultados.append(_res("G10", "Excepción imprevista en una etapa (IQR)", "FALLIDO imprevisto con traceback registrado",
                           f"{r['estado']} {r.get('tipo_error')} en «{r.get('etapa_fallida')}»; traceback={'traceback' in r}",
                           r["estado"] == "FALLIDO" and r.get("error_previsto") is False and "traceback" in r and log_existe,
                           r.get("error", "")))
    return resultados


def ejecutar_todo(dir_trabajo: Path) -> pd.DataFrame:
    filas, _ = ejecutar_escenarios_fila(Path(dir_trabajo) / "filas")
    return pd.DataFrame(filas + ejecutar_escenarios_globales(Path(dir_trabajo) / "globales"))


if __name__ == "__main__":
    import tempfile
    sys.stdout.reconfigure(encoding="utf-8")
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "salidas" / "etapa_nono" / "estres"
    destino.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tabla = ejecutar_todo(Path(tmp))
    tabla.to_csv(destino / "resultados_estres.csv", index=False, encoding="utf-8")
    with pd.option_context("display.width", 250, "display.max_colwidth", 70, "display.max_rows", 200):
        print(tabla.drop(columns=["motivo", "fila"]).to_string(index=False))
    print(f"\nOK: {int(tabla['ok'].sum())} / {len(tabla)}  →  {destino / 'resultados_estres.csv'}")
    sys.exit(0 if tabla["ok"].all() else 1)
