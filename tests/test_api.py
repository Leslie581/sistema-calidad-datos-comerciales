"""Pruebas de la API FastAPI de KOVA contra una base REAL generada por el pipeline (no datos simulados)."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.config import Ajustes
from src.api.db import ErrorApi, conectar
from src.api.ejecucion import EjecutorPipeline
from src.api.main import crear_app
from src.config import RUTA_SALIDAS, RUTAS_FUENTES
from src.pipeline import ejecutar_pipeline
from tests.ayudas_nono import HOY


def ajustes_en(d: Path, **kw) -> Ajustes:
    return Ajustes(ruta_bd=d / "kova.db", dir_salida=d / "salida", raiz_salidas=RUTA_SALIDAS, dist_frontend=d / "sin_dist", **kw)


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    d = tmp_path_factory.mktemp("api")
    aj = ajustes_en(d)
    r = ejecutar_pipeline(ruta_bd=aj.ruta_bd, dir_salida=aj.dir_salida, hoy=HOY)
    assert r["estado"] == "COMPLETADO"
    return aj, r


@pytest.fixture(scope="module")
def c(entorno):
    return TestClient(crear_app(entorno[0]))


@pytest.fixture
def bd_directa(entorno):
    with closing(sqlite3.connect(str(entorno[0].ruta_bd))) as con:
        yield con


# ----------------------------------------------------------------------------- base inexistente o vacía
RUTAS_GET = ["/api/dashboard", "/api/facetas", "/api/transacciones", "/api/transacciones/WEB-00001", "/api/cuarentena",
             "/api/cuarentena/1", "/api/catalogo", "/api/calidad", "/api/ejecuciones"]


@pytest.mark.parametrize("ruta", RUTAS_GET)
def test_sin_base_de_datos_responde_503_controlado(tmp_path, ruta):
    cli = TestClient(crear_app(ajustes_en(tmp_path)))
    r = cli.get(ruta)
    assert r.status_code == 503 and r.json()["codigo"] == "BD_NO_ENCONTRADA" and "pipeline" in r.json()["mensaje"]


def test_base_vacia_sin_tablas_es_503_sin_esquema(tmp_path):
    sqlite3.connect(str(tmp_path / "kova.db")).close()
    cli = TestClient(crear_app(ajustes_en(tmp_path)))
    assert cli.get("/api/dashboard").json()["codigo"] == "BD_SIN_ESQUEMA"
    assert cli.get("/api/salud").json()["base_datos"] == "sin_esquema"


def test_salud_sin_base_y_estado_del_pipeline_siguen_funcionando(tmp_path):
    cli = TestClient(crear_app(ajustes_en(tmp_path)))
    assert cli.get("/api/salud").json() == {"api": "ok", "base_datos": "no_encontrada", "ruta_bd_relativa": "kova.db", "version": "1.0.0"}
    e = cli.get("/api/pipeline/estado").json()
    assert e["ruta_bd_existe"] is False and e["ultima"] is None and all(f["estado"] == "SIN_DATOS" for f in e["fases"])


def test_la_api_abre_la_base_en_solo_lectura(entorno):
    with conectar(entorno[0].ruta_bd) as con:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM transacciones_limpias")
        with pytest.raises(sqlite3.OperationalError):
            con.execute("CREATE TABLE intruso (x)")


# ----------------------------------------------------------------------------- dashboard
def test_dashboard_coincide_con_sqlite(c, bd_directa):
    d = c.get("/api/dashboard").json()
    n_ok = bd_directa.execute("SELECT COUNT(*) FROM transacciones_limpias").fetchone()[0]
    n_qz = bd_directa.execute("SELECT COUNT(*) FROM cuarentena_errores").fetchone()[0]
    assert d["hay_datos"] and d["totales"] == {"entrada": n_ok + n_qz, "limpias": n_ok, "cuarentena": n_qz,
                                              "tasa_aceptacion": round(n_ok / (n_ok + n_qz), 4), "cuadra": True}
    assert sum(x["limpias"] for x in d["canales"]) == n_ok and sum(x["cuarentena"] for x in d["canales"]) == n_qz
    assert sum(s["n"] for s in d["segmentos"]) == n_ok
    assert d["motivos"]["total_registros"] == n_qz
    assert d["ultima_ejecucion"]["estado"] == "COMPLETADO" and d["ultima_ejecucion"]["duracion_s"] > 0


def test_dashboard_valores_oficiales(c):
    d = c.get("/api/dashboard").json()
    assert (d["totales"]["entrada"], d["totales"]["limpias"], d["totales"]["cuarentena"]) == (1220, 1104, 116)
    por = {m["codigo"]: m["registros"] for m in d["motivos"]["por_codigo"]}
    assert por == {"PRODUCTO_HUERFANO": 62, "EMAIL_MALFORMADO": 28, "DUPLICADO_EXACTO": 20, "CANTIDAD_INVALIDA": 11, "MONTO_INVALIDO": 11}
    assert d["motivos"]["con_varios_motivos"] == 15


def test_indice_de_salud_es_explicito_y_distinto_de_las_metricas_oficiales(c, bd_directa):
    s = c.get("/api/dashboard").json()["salud"]
    assert s["es_indicador_compuesto"] is True and "÷" in s["formula"] and "oficiales" in s["detalle"]
    assert s["conformes"] + s["reparados"] + s["rechazados"] == s["entrada"]
    assert s["valor"] == round(s["conformes"] / s["entrada"], 4)
    reparados = bd_directa.execute("SELECT COUNT(*) FROM transacciones_limpias WHERE correcciones LIKE '%\"IMPUTADO_%' "
                                   "OR correcciones LIKE '%\"MONTO_RECALCULADO_%'").fetchone()[0]
    assert s["reparados"] == reparados


# ----------------------------------------------------------------------------- transacciones
def test_paginacion_real(c):
    p1 = c.get("/api/transacciones", params={"tam": 25, "pagina": 1}).json()
    assert (p1["total"], p1["pagina"], p1["tam"], p1["paginas"], len(p1["items"])) == (1104, 1, 25, 45, 25)
    ultima = c.get("/api/transacciones", params={"tam": 25, "pagina": 45}).json()
    assert len(ultima["items"]) == 1104 - 44 * 25
    ids = {t["id_transaccion"] for pag in (1, 2) for t in c.get("/api/transacciones", params={"tam": 25, "pagina": pag}).json()["items"]}
    assert len(ids) == 50                                   # páginas distintas, sin solaparse
    assert c.get("/api/transacciones", params={"pagina": 999}).json()["items"] == []


@pytest.mark.parametrize("params", [{"tam": 101}, {"tam": 0}, {"pagina": 0}, {"canal": "TIENDA"}, {"segmento": "Premium"}, {"orden": "id; DROP TABLE x"},
                                    {"direccion": "up"}, {"desde": "2026-13-01"}, {"hasta": "ayer"}, {"desde": "2026-10-10", "hasta": "2026-09-01"},
                                    {"q": "x" * 81}])
def test_parametros_invalidos_son_422_con_mensaje(c, params):
    r = c.get("/api/transacciones", params=params)
    assert r.status_code == 422 and r.json()["codigo"] == "PARAMETRO_INVALIDO" and r.json()["mensaje"]


def test_filtros_combinados(c, bd_directa):
    r = c.get("/api/transacciones", params={"canal": "ONLINE", "segmento": "Alto", "categoria": "Hogar", "tam": 100}).json()
    esperado = bd_directa.execute("SELECT COUNT(*) FROM transacciones_limpias WHERE origen='ONLINE' AND segmento_importe='Alto' AND categoria='Hogar'").fetchone()[0]
    assert r["total"] == esperado > 0
    assert all(t["origen"] == "ONLINE" and t["segmento_importe"] == "Alto" and t["categoria"] == "Hogar" for t in r["items"])


def test_filtro_de_fechas_inclusivo(c):
    r = c.get("/api/transacciones", params={"desde": "2026-09-05", "hasta": "2026-09-06", "tam": 100}).json()
    assert r["total"] > 0 and {t["fecha_venta"] for t in r["items"]} <= {"2026-09-05", "2026-09-06"}


def test_busqueda_por_id_y_estado(c):
    assert [t["id_transaccion"] for t in c.get("/api/transacciones", params={"q": "WEB-00508"}).json()["items"]] == ["WEB-00508"]
    r = c.get("/api/transacciones", params={"estado": "CANCELADO", "tam": 100}).json()
    assert r["total"] > 0 and all(t["estado_pedido"] == "CANCELADO" and t["origen"] == "ONLINE" for t in r["items"])


def test_ordenacion_asc_y_desc(c):
    asc = [t["monto_total_mxn"] for t in c.get("/api/transacciones", params={"orden": "importe", "direccion": "asc", "tam": 50}).json()["items"]]
    desc = [t["monto_total_mxn"] for t in c.get("/api/transacciones", params={"orden": "importe", "direccion": "desc", "tam": 50}).json()["items"]]
    assert asc == sorted(asc) and desc == sorted(desc, reverse=True) and asc[0] < desc[0]


@pytest.mark.parametrize("q", ["'; DROP TABLE transacciones_limpias;--", "' OR '1'='1", "%", "_", "\\"])
def test_busqueda_con_sql_o_comodines_es_texto_literal(c, q, bd_directa):
    r = c.get("/api/transacciones", params={"q": q})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert bd_directa.execute("SELECT COUNT(*) FROM transacciones_limpias").fetchone()[0] == 1104


def test_un_parametro_sql_no_existe_y_se_ignora(c):
    r = c.get("/api/transacciones", params={"sql": "DELETE FROM transacciones_limpias", "tam": 1})
    assert r.status_code == 200 and r.json()["total"] == 1104


def test_contrato_de_una_transaccion(c):
    t = c.get("/api/transacciones", params={"q": "WEB-00002"}).json()["items"][0]
    assert t == {**t, "id_transaccion": "WEB-00002", "origen": "ONLINE", "moneda_original": "USD", "precio_unitario_mxn": 3307.01,
                 "fecha_venta": "2026-10-12", "segmento_importe": "Medio"}
    assert set(t) >= {"nombre_producto", "categoria", "cantidad", "monto_total_mxn", "monto_total_mxn_cap", "estado_pedido"}


def test_detalle_con_trazabilidad_de_web_00508(c):
    d = c.get("/api/transacciones/WEB-00508").json()
    assert [e["clave"] for e in d["trazabilidad"]] == ["original", "homologacion", "correcciones", "capping", "transformacion", "validacion", "resultado"]
    t = d["transaccion"]
    assert (t["monto_total_origen"], t["monto_total_mxn"], t["monto_total_mxn_cap"]) == (826360.8, 10329.51, 10329.51)
    corr = next(e for e in d["trazabilidad"] if e["clave"] == "correcciones")
    assert "MONTO_RECALCULADO_INCONSISTENTE" in corr["codigos"] and corr["estado"] == "corregido"
    assert d["registro_original"]["total_amount"] == 826360.8 and "registro_original" not in t
    assert "MONTO_RECALCULADO_INCONSISTENTE" in d["glosario"] and d["glosario"]["MONTO_RECALCULADO_INCONSISTENTE"]


def test_detalle_con_capping_de_cantidad(c):
    d = c.get("/api/transacciones/POS-2026-0031").json()
    cap = next(e for e in d["trazabilidad"] if e["clave"] == "capping")
    assert cap["estado"] == "tratado" and "CAPPING_IQR_CANTIDAD" in cap["codigos"]
    assert (d["transaccion"]["cantidad_origen"], d["transaccion"]["cantidad_cap"]) == (500.0, 8.0)


def test_id_duplicado_muestra_su_cuarentena_relacionada(c):
    d = c.get("/api/transacciones/POS-2026-0001").json()
    assert len(d["cuarentena_relacionada"]) == 1 and d["cuarentena_relacionada"][0]["codigos"] == ["DUPLICADO_EXACTO"]


@pytest.mark.parametrize("id_", ["WEB-99999", "POS-2026-0017", "' OR 1=1 --"])
def test_transaccion_inexistente_o_en_cuarentena_es_404(c, id_):
    r = c.get(f"/api/transacciones/{id_}")
    assert r.status_code == 404 and r.json()["codigo"] == "TRANSACCION_NO_ENCONTRADA"


# ----------------------------------------------------------------------------- cuarentena
def test_cuarentena_cuenta_cada_transaccion_una_vez(c, bd_directa):
    r = c.get("/api/cuarentena", params={"tam": 100}).json()
    assert r["total"] == 116 == bd_directa.execute("SELECT COUNT(*) FROM cuarentena_errores").fetchone()[0]
    todos = [i["id_error"] for pag in (1, 2) for i in c.get("/api/cuarentena", params={"tam": 100, "pagina": pag}).json()["items"]]
    assert len(todos) == len(set(todos)) == 116
    assert max(i["num_motivos"] for i in r["items"]) == 3


@pytest.mark.parametrize("codigo, esperado", [("PRODUCTO_HUERFANO", 62), ("EMAIL_MALFORMADO", 28), ("DUPLICADO_EXACTO", 20),
                                              ("CANTIDAD_INVALIDA", 11), ("MONTO_INVALIDO", 11), ("ERROR_INESPERADO", 0)])
def test_filtro_por_codigo(c, codigo, esperado):
    r = c.get("/api/cuarentena", params={"codigo": codigo, "tam": 100}).json()
    assert r["total"] == esperado and all(codigo in i["codigos"] for i in r["items"])


def test_filtros_de_cuarentena_canal_etapa_y_busqueda(c):
    assert c.get("/api/cuarentena", params={"canal": "ONLINE"}).json()["total"] == 58
    assert c.get("/api/cuarentena", params={"etapa": "PYDANTIC"}).json()["total"] > 0
    assert [i["id_registro"] for i in c.get("/api/cuarentena", params={"q": "POS-2026-0216"}).json()["items"]] == ["POS-2026-0216"]
    assert c.get("/api/cuarentena", params={"codigo": "x'; DROP"}).status_code == 422
    assert c.get("/api/cuarentena", params={"etapa": "OTRA"}).status_code == 422


def test_detalle_de_cuarentena_conserva_el_registro_crudo_y_todos_los_motivos(c):
    item = c.get("/api/cuarentena", params={"q": "POS-2026-0493"}).json()["items"][0]
    d = c.get(f"/api/cuarentena/{item['id_error']}").json()
    assert d["registro"]["codigos"] == ["CANTIDAD_INVALIDA", "MONTO_INVALIDO", "PRODUCTO_HUERFANO"]
    assert {x["codigo"] for x in d["detalle"]} == set(d["registro"]["codigos"]) and all(x["descripcion"] for x in d["detalle"])
    assert d["registro_original"]["id_ticket"] == "POS-2026-0493" and d["registro_original"]["cantidad"] == "-1"
    assert [e["clave"] for e in d["trazabilidad"]] == ["original", "deteccion", "resultado"]


def test_cuarentena_inexistente_y_parametro_no_numerico(c):
    assert c.get("/api/cuarentena/999999").status_code == 404
    assert c.get("/api/cuarentena/abc").status_code == 422


# ----------------------------------------------------------------------------- catálogo
def test_catalogo_oficial(c):
    r = c.get("/api/catalogo", params={"tam": 100}).json()
    assert r["total"] == 50 and len(r["items"]) == 50 and r["huerfanos"] == 62
    assert {p["categoria"] for p in r["items"]} == {"Alimentos", "Deportes", "Electrónica", "Hogar", "Juguetería", "Ropa"}
    assert sum(p["ventas"] for p in r["items"]) == 1104
    assert {"id_producto", "nombre_producto", "categoria", "precio_base_mxn", "stock_minimo", "proveedor"} <= set(r["items"][0])


def test_catalogo_filtros_y_orden(c):
    r = c.get("/api/catalogo", params={"categoria": "Ropa"}).json()
    assert r["total"] == 5 and all(p["categoria"] == "Ropa" for p in r["items"])
    por_precio = [p["precio_base_mxn"] for p in c.get("/api/catalogo", params={"orden": "precio", "direccion": "desc", "tam": 100}).json()["items"]]
    assert por_precio == sorted(por_precio, reverse=True)
    assert c.get("/api/catalogo", params={"q": "PROD-025"}).json()["items"][0]["id_producto"] == "PROD-025"
    assert c.get("/api/catalogo", params={"orden": "x"}).status_code == 422


# ----------------------------------------------------------------------------- calidad, ejecuciones, reportes
def test_calidad_usa_reportes_reales(c):
    r = c.get("/api/calidad").json()
    assert r["limpieza"]["duplicados_exactos"] == 20 and r["iqr"]["monto_mxn"]["LS"] == 12032.68
    assert r["transformacion"]["segmentos"]["corte_bajo_medio"] == 2069.07
    assert "COMPATIBLES con MCAR" in r["nota_mcar"] and "no demuestra" in r["nota_mcar"]
    if r["fuentes"]["reportes_leslie_disponibles"]:
        assert r["perfil_antes"]["fisica"]["filas"] == 620 and len(r["faltantes"]) == 4
        assert any(g["url"].endswith("boxplot_importe_mxn.png") for g in r["graficas"])
    assert set(r["distincion"]) == {"originales", "corregidos", "tratados"}


def test_historial_y_detalle_de_ejecucion(c, entorno):
    lote = entorno[1]["lote_id"]
    lista = c.get("/api/ejecuciones").json()
    assert lista["total"] >= 1 and lista["items"][0]["lote_id"] == lote and "última ejecución" in lista["nota"]
    d = c.get(f"/api/ejecuciones/{lote}").json()
    assert [f["estado"] for f in d["fases"]] == ["COMPLETADA"] * 7 and all(f["duracion_s"] > 0 for f in d["fases"])
    assert d["log"] and any("Carga transaccional" in linea for linea in d["log"]) and d["huellas_entrada"]


@pytest.mark.parametrize("lote, estado", [("../../etc/passwd", 404), ("L2026", 422), ("L20200101-000000-abcd", 404)])
def test_ejecucion_con_id_invalido_o_inexistente(c, lote, estado):
    assert c.get(f"/api/ejecuciones/{lote}").status_code == estado


def test_una_ejecucion_fallida_no_se_muestra_como_exitosa(tmp_path):
    aj = ajustes_en(tmp_path)
    ok = ejecutar_pipeline(ruta_bd=aj.ruta_bd, dir_salida=aj.dir_salida, hoy=HOY, generar_reportes=False)
    roto = tmp_path / "ventas_online.json"
    roto.write_text('[{"order_id": "WEB-', encoding="utf-8")
    fallo = ejecutar_pipeline({**RUTAS_FUENTES, "online": roto}, aj.ruta_bd, aj.dir_salida, hoy=HOY, generar_reportes=False)
    assert ok["estado"] == "COMPLETADO" and fallo["estado"] == "FALLIDO"
    cli = TestClient(crear_app(aj))
    items = {e["lote_id"]: e for e in cli.get("/api/ejecuciones").json()["items"]}
    assert items[fallo["lote_id"]]["estado"] == "FALLIDO" and items[fallo["lote_id"]]["etapa_fallida"] == "1. Extracción"
    assert items[fallo["lote_id"]]["filas_limpias"] is None and items[ok["lote_id"]]["estado"] == "COMPLETADO"
    det = cli.get(f"/api/ejecuciones/{fallo['lote_id']}").json()
    assert det["fases"][0]["estado"] == "FALLIDA" and det["fases"][-1]["estado"] == "NO_EJECUTADA"
    assert cli.get("/api/ejecuciones", params={"estado": "FALLIDO"}).json()["total"] == 1
    assert cli.get("/api/pipeline/estado").json()["ultima"]["estado"] == "FALLIDO"
    assert cli.get("/api/dashboard").json()["totales"]["limpias"] == 1104          # los datos de la carga buena siguen intactos


def test_reportes_listado_y_descarga(c):
    r = c.get("/api/reportes").json()
    carpetas = {g["carpeta"] for g in r["grupos"]}
    assert "etapa_nono" in carpetas
    nono = next(g for g in r["grupos"] if g["carpeta"] == "etapa_nono")
    assert any(a["nombre"].startswith("09_comparacion") for a in nono["archivos"])
    assert not any(a["tipo"] in ("db", "log") for g in r["grupos"] for a in g["archivos"])
    archivo = next(a for a in nono["archivos"] if a["nombre"] == "02_conteos_conservacion.csv")
    resp = c.get(archivo["url"])
    assert resp.status_code == 200 and "FISICA" in resp.text and resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in c.get(archivo["url"], params={"descargar": "true"}).headers["content-disposition"]


@pytest.mark.parametrize("ruta", ["/api/reportes/etapa_nono/..%2f..%2fREADME.md", "/api/reportes/etapa_nono/../../../.gitignore", "/api/reportes/etapa_nono/kova.db",
                                  "/api/reportes/src/pipeline.py", "/api/reportes/etapa_nono/logs", "/api/reportes/etapa_nono/no_existe.csv",
                                  "/api/reportes/..%2f/README.md", "/api/reportes/etapa_nono/%2e%2e/%2e%2e/requirements.txt"])
def test_no_se_pueden_leer_archivos_fuera_de_los_reportes(c, ruta):
    r = c.get(ruta)
    assert r.status_code in (404, 422) and "import" not in r.text and "fastapi" not in r.text


# ----------------------------------------------------------------------------- ejecución protegida del pipeline
def test_ejecutar_exige_confirmacion(entorno):
    cli = TestClient(crear_app(entorno[0], EjecutorPipeline(entorno[0], ejecutar=lambda **_: {"estado": "COMPLETADO"})))
    assert cli.post("/api/pipeline/ejecutar").status_code == 422
    r = cli.post("/api/pipeline/ejecutar", json={"confirmar": False})
    assert r.status_code == 400 and r.json()["codigo"] == "CONFIRMACION_REQUERIDA"
    assert cli.post("/api/pipeline/ejecutar", json={"confirmar": "tal vez"}).status_code == 422


def test_ejecutar_rechaza_origenes_no_locales(entorno):
    cli = TestClient(crear_app(entorno[0], EjecutorPipeline(entorno[0], ejecutar=lambda **_: {"estado": "COMPLETADO"})))
    r = cli.post("/api/pipeline/ejecutar", json={"confirmar": True}, headers={"Origin": "https://sitio-malicioso.example"})
    assert r.status_code == 403 and r.json()["codigo"] == "ORIGEN_NO_PERMITIDO"


def test_no_hay_ejecuciones_simultaneas(entorno):
    liberar = threading.Event()
    llamadas = []

    def lenta(**kw):
        llamadas.append(kw)
        liberar.wait(5)
        return {"estado": "COMPLETADO", "lote_id": "L20260101-000000-aaaa", "duracion_s": 0.1}

    aj = entorno[0]
    runner = EjecutorPipeline(aj, ejecutar=lenta)
    cli = TestClient(crear_app(aj, runner))
    primera = cli.post("/api/pipeline/ejecutar", json={"confirmar": True}, headers={"Origin": "http://localhost:5173"})
    assert primera.status_code == 202 and primera.json()["estado"] == "EN_EJECUCION"
    segunda = cli.post("/api/pipeline/ejecutar", json={"confirmar": True})
    assert segunda.status_code == 409 and segunda.json()["codigo"] == "PIPELINE_EN_EJECUCION"
    assert cli.get("/api/pipeline/estado").json()["ejecutor"]["estado"] == "EN_EJECUCION"
    liberar.set()
    runner.esperar(5)
    estado = cli.get("/api/pipeline/estado").json()["ejecutor"]
    assert estado["estado"] == "INACTIVO" and estado["ultimo_resultado"]["estado"] == "COMPLETADO" and len(llamadas) == 1
    assert cli.post("/api/pipeline/ejecutar", json={"confirmar": True}).status_code == 202       # se libera el candado
    runner.esperar(5)


def test_un_fallo_del_ejecutor_se_reporta_y_libera_el_candado(entorno):
    def explota(**_):
        raise RuntimeError("fallo simulado")

    runner = EjecutorPipeline(entorno[0], ejecutar=explota)
    cli = TestClient(crear_app(entorno[0], runner))
    assert cli.post("/api/pipeline/ejecutar", json={"confirmar": True}).status_code == 202
    runner.esperar(5)
    e = cli.get("/api/pipeline/estado").json()["ejecutor"]
    assert e["estado"] == "INACTIVO" and e["ultimo_resultado"]["estado"] == "FALLIDO" and "fallo simulado" in e["ultimo_resultado"]["error"]
    assert cli.post("/api/pipeline/ejecutar", json={"confirmar": True}).status_code == 202
    runner.esperar(5)


def test_ejecucion_real_desde_la_api_actualiza_la_base(tmp_path):
    aj = ajustes_en(tmp_path)
    runner = EjecutorPipeline(aj)
    cli = TestClient(crear_app(aj, runner))
    assert cli.get("/api/dashboard").status_code == 503
    assert cli.post("/api/pipeline/ejecutar", json={"confirmar": True}).status_code == 202
    runner.esperar(60)
    estado = cli.get("/api/pipeline/estado").json()
    assert estado["ejecutor"]["ultimo_resultado"]["estado"] == "COMPLETADO" and estado["ultima"]["estado"] == "COMPLETADO"
    d = cli.get("/api/dashboard").json()
    assert (d["totales"]["limpias"], d["totales"]["cuarentena"]) == (1104, 116)
    assert estado["fases"][0]["metricas"]["integridad_originales"] == {"catalogo_productos.csv": True, "ventas_tienda_fisica.csv": True, "ventas_online.json": True}
    assert cli.get("/api/ejecuciones").json()["total"] == 1


# ----------------------------------------------------------------------------- CORS y errores
def test_cors_solo_para_origenes_locales(c):
    ok = c.options("/api/dashboard", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    mal = c.options("/api/dashboard", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in mal.headers
    assert "*" not in ok.headers.get("access-control-allow-origin", "")


def test_error_interno_no_expone_detalles(entorno, monkeypatch):
    from src.api import servicios
    monkeypatch.setattr(servicios, "dashboard", lambda *a, **k: 1 / 0)
    cli = TestClient(crear_app(entorno[0]), raise_server_exceptions=False)
    r = cli.get("/api/dashboard")
    assert r.status_code == 500 and r.json() == {"codigo": "ERROR_INTERNO", "mensaje": "Ocurrió un error inesperado en el servidor."}
    assert "division" not in r.text.lower()


def test_error_api_tiene_forma_estable():
    e = ErrorApi("X", "mensaje", 418)
    assert (e.codigo, e.mensaje, e.estado) == ("X", "mensaje", 418)


def test_la_api_no_modifica_la_base(entorno, c):
    antes = Path(entorno[0].ruta_bd).stat().st_mtime_ns
    for ruta in RUTAS_GET + ["/api/reportes", "/api/pipeline/estado"]:
        c.get(ruta)
    time.sleep(0.05)
    assert Path(entorno[0].ruta_bd).stat().st_mtime_ns == antes


def test_sirve_el_frontend_compilado_y_no_confunde_rutas_de_api(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>KOVA</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    aj = ajustes_en(tmp_path)
    aj.dist_frontend = dist
    cli = TestClient(crear_app(aj))
    assert cli.get("/etl").text == "<html>KOVA</html>" and cli.get("/assets/app.js").text == "console.log(1)"
    assert cli.get("/api/no_existe").json()["codigo"] == "RUTA_NO_ENCONTRADA"
    assert cli.get("/../../README.md").text == "<html>KOVA</html>"


# ----------------------------------------------------------------------------- precio original en la lista de transacciones
def test_listado_incluye_precio_original_persistido_para_usd_y_mxn(c, bd_directa):
    filas = [f for pag in range(1, 13) for f in c.get("/api/transacciones", params={"tam": 100, "pagina": pag, "orden": "id", "direccion": "asc"}).json()["items"]]
    assert len(filas) == 1104
    esperados = {r[0]: r[1:] for r in bd_directa.execute(
        "SELECT id_transaccion, moneda_original, precio_unitario_original, precio_unitario_mxn, tipo_cambio_aplicado FROM transacciones_limpias")}
    usd = [f for f in filas if f["moneda_original"] == "USD"]
    mxn = [f for f in filas if f["moneda_original"] == "MXN"]
    assert usd and mxn
    for f in filas:                                         # valores EXACTOS de SQLite, no recalculados
        assert (f["moneda_original"], f["precio_unitario_original"], f["precio_unitario_mxn"], f["tipo_cambio_aplicado"]) == esperados[f["id_transaccion"]]
    assert all(f["tipo_cambio_aplicado"] == 19.5 and f["precio_unitario_original"] != f["precio_unitario_mxn"] for f in usd)
    assert all(f["tipo_cambio_aplicado"] == 1.0 and f["precio_unitario_original"] == f["precio_unitario_mxn"] for f in mxn)


def test_listado_usd_conocido_y_orden_por_precio_sigue_siendo_en_mxn(c):
    f = c.get("/api/transacciones", params={"q": "WEB-00002"}).json()["items"][0]
    assert (f["moneda_original"], f["precio_unitario_original"], f["precio_unitario_mxn"], f["tipo_cambio_aplicado"]) == ("USD", 169.59, 3307.01, 19.5)
    precios = [x["precio_unitario_mxn"] for x in c.get("/api/transacciones", params={"orden": "precio", "direccion": "asc", "tam": 50}).json()["items"]]
    assert precios == sorted(precios)
