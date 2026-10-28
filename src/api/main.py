"""
API de KOVA (FastAPI). Aplicación LOCAL y académica: lee la base SQLite generada por el pipeline y puede relanzarlo.

    uvicorn src.api.main:app --host 127.0.0.1 --port 8000

- Solo lectura sobre SQLite (conexión `mode=ro`); no existe ningún endpoint que reciba SQL ni rutas de archivos.
- Los únicos archivos descargables son reportes de las carpetas etapa_leslie / etapa_yerik / etapa_nono con extensión permitida.
- CORS limitado a los orígenes locales de Vite. El POST que ejecuta el pipeline exige confirmación explícita y rechaza
  orígenes que no sean locales (defensa básica contra peticiones desde otras páginas del navegador).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import comercial as co
from . import servicios as sv
from .config import Ajustes
from .db import ErrorApi, conectar
from .ejecucion import EjecutorPipeline
from .esquemas import (CanalesComerciales, OpcionesComerciales, ProductosComerciales, ResumenComercial, TendenciaComercial,
                       Calidad, Dashboard, DetalleCuarentena, DetalleEjecucion, DetalleTransaccion, EstadoPipeline,
                       Facetas, ListaEjecuciones, ListaReportes, PaginaCatalogo, PaginaCuarentena, PaginaTransacciones,
                       RespuestaEjecucion, Salud, SolicitudEjecucion)

VERSION = "1.0.0"
RE_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
Pag = Annotated[int, Query(ge=1, le=100000, description="Página (desde 1)")]
Tam = Annotated[int, Query(ge=1, le=100, description="Registros por página (máx. 100)")]
Texto = Annotated[Optional[str], Query(max_length=80)]
Dir = Literal["asc", "desc"]
Mes = Annotated[Optional[str], Query(max_length=7, description="YYYY-MM; por omisión, el último mes con datos")]
Fecha = Annotated[Optional[str], Query(max_length=10, description="YYYY-MM-DD")]
ParamCanal = Annotated[Optional[Literal["FISICA", "ONLINE"]], Query(description="vacío = ambos canales")]
ParamComp = Annotated[Literal["equivalente", "mes_anterior_completo", "ninguna"], Query(description="forma de elegir el período anterior")]
ParamEstados = Annotated[Literal["todas", "efectivas"], Query(description="«efectivas» excluye pedidos CANCELADO y DEVUELTO")]


def _fecha(valor: Optional[str], nombre: str) -> Optional[str]:
    if valor is None or valor == "":
        return None
    try:
        if not RE_FECHA.match(valor):
            raise ValueError
        date.fromisoformat(valor)
    except ValueError:
        raise ErrorApi("PARAMETRO_INVALIDO", f"«{nombre}» debe ser una fecha YYYY-MM-DD válida.", 422) from None
    return valor


def crear_app(ajustes: Ajustes | None = None, ejecutor: EjecutorPipeline | None = None) -> FastAPI:
    aj = ajustes or Ajustes.desde_entorno()
    runner = ejecutor or EjecutorPipeline(aj)
    app = FastAPI(title="KOVA API", version=VERSION,
                  description="Inteligencia comercial, datos confiables. API local sobre el pipeline ETL.")
    app.state.ajustes, app.state.ejecutor = aj, runner
    app.add_middleware(CORSMiddleware, allow_origins=list(aj.origenes), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False)

    # ------------------------------------------------------------------ errores con forma estable {codigo, mensaje}
    @app.exception_handler(ErrorApi)
    async def _error_api(_: Request, e: ErrorApi):
        return JSONResponse({"codigo": e.codigo, "mensaje": e.mensaje}, status_code=e.estado)

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_: Request, e: RequestValidationError):
        primero = e.errors()[0]
        campo = ".".join(str(x) for x in primero["loc"] if x not in ("query", "body", "path"))
        return JSONResponse({"codigo": "PARAMETRO_INVALIDO", "mensaje": f"Parámetro «{campo}» inválido: {primero['msg']}"},
                            status_code=422)

    @app.exception_handler(Exception)
    async def _error_inesperado(_: Request, e: Exception):
        return JSONResponse({"codigo": "ERROR_INTERNO", "mensaje": "Ocurrió un error inesperado en el servidor."}, status_code=500)

    # ------------------------------------------------------------------ salud
    @app.get("/api/salud", response_model=Salud, tags=["sistema"])
    def salud():
        estado = "no_encontrada"
        if aj.ruta_bd.is_file():
            try:
                with conectar(aj.ruta_bd) as c:
                    c.execute("SELECT 1 FROM ejecuciones LIMIT 1")
                estado = "disponible"
            except ErrorApi as e:
                estado = "sin_esquema" if e.codigo == "BD_SIN_ESQUEMA" else "no_disponible"
        return {"base_datos": estado, "ruta_bd_relativa": aj.ruta_bd.name, "version": VERSION}

    # ------------------------------------------------------------------ lectura
    @app.get("/api/dashboard", response_model=Dashboard, tags=["consulta"])
    def dashboard():
        with conectar(aj.ruta_bd) as c:
            return sv.dashboard(c, aj)

    @app.get("/api/facetas", response_model=Facetas, tags=["consulta"])
    def facetas():
        with conectar(aj.ruta_bd) as c:
            return sv.facetas(c)

    @app.get("/api/transacciones", response_model=PaginaTransacciones, tags=["consulta"])
    def transacciones(q: Texto = None, canal: Optional[Literal["FISICA", "ONLINE"]] = None, desde: Optional[str] = None,
                      hasta: Optional[str] = None, categoria: Texto = None,
                      segmento: Optional[Literal["Bajo", "Medio", "Alto"]] = None, estado: Texto = None,
                      orden: Literal[tuple(sv.ORDEN_TRANSACCIONES)] = "fecha", direccion: Dir = "desc",
                      pagina: Pag = 1, tam: Tam = 25):
        desde, hasta = _fecha(desde, "desde"), _fecha(hasta, "hasta")
        if desde and hasta and desde > hasta:
            raise ErrorApi("PARAMETRO_INVALIDO", "«desde» no puede ser posterior a «hasta».", 422)
        with conectar(aj.ruta_bd) as c:
            return sv.listar_transacciones(c, q, canal, desde, hasta, categoria, segmento, estado, orden, direccion, pagina, tam)

    @app.get("/api/transacciones/{id_transaccion}", response_model=DetalleTransaccion, tags=["consulta"])
    def transaccion(id_transaccion: str):
        if len(id_transaccion) > 40:
            raise ErrorApi("PARAMETRO_INVALIDO", "Identificador demasiado largo.", 422)
        with conectar(aj.ruta_bd) as c:
            return sv.detalle_transaccion(c, id_transaccion)

    @app.get("/api/cuarentena", response_model=PaginaCuarentena, tags=["consulta"])
    def cuarentena(q: Texto = None, canal: Optional[Literal["FISICA", "ONLINE"]] = None,
                   codigo: Annotated[Optional[str], Query(pattern=r"^[A-Z_]{3,40}$")] = None,
                   etapa: Optional[Literal["FASE_PREVIA", "PYDANTIC", "ERROR_INESPERADO"]] = None,
                   orden: Literal[tuple(sv.ORDEN_CUARENTENA)] = "registro", direccion: Dir = "asc",
                   pagina: Pag = 1, tam: Tam = 25):
        with conectar(aj.ruta_bd) as c:
            return sv.listar_cuarentena(c, q, canal, codigo, etapa, orden, direccion, pagina, tam)

    @app.get("/api/cuarentena/{id_error}", response_model=DetalleCuarentena, tags=["consulta"])
    def cuarentena_detalle(id_error: int):
        with conectar(aj.ruta_bd) as c:
            return sv.detalle_cuarentena(c, id_error)

    @app.get("/api/catalogo", response_model=PaginaCatalogo, tags=["consulta"])
    def catalogo(q: Texto = None, categoria: Texto = None, proveedor: Texto = None,
                 orden: Literal[tuple(sv.ORDEN_CATALOGO)] = "id", direccion: Dir = "asc", pagina: Pag = 1, tam: Tam = 50):
        with conectar(aj.ruta_bd) as c:
            return sv.listar_catalogo(c, q, categoria, proveedor, orden, direccion, pagina, tam)

    @app.get("/api/calidad", response_model=Calidad, tags=["consulta"])
    def calidad():
        with conectar(aj.ruta_bd) as c:
            return sv.calidad(c, aj)

    @app.get("/api/ejecuciones", response_model=ListaEjecuciones, tags=["consulta"])
    def ejecuciones(estado: Optional[Literal["COMPLETADO", "FALLIDO"]] = None):
        with conectar(aj.ruta_bd) as c:
            return sv.listar_ejecuciones(c, aj, estado)

    @app.get("/api/ejecuciones/{lote_id}", response_model=DetalleEjecucion, tags=["consulta"])
    def ejecucion(lote_id: str):
        with conectar(aj.ruta_bd) as c:
            return sv.detalle_ejecucion(c, aj, lote_id)

    @app.get("/api/reportes", response_model=ListaReportes, tags=["reportes"])
    def reportes():
        return sv.listar_reportes(aj)

    @app.get("/api/reportes/{carpeta}/{ruta:path}", tags=["reportes"])
    def reporte(carpeta: str, ruta: str, descargar: bool = False):
        archivo, tipo = sv.resolver_reporte(aj, carpeta, ruta)
        return FileResponse(archivo, media_type=tipo, filename=archivo.name if descargar else None,
                            content_disposition_type="attachment" if descargar else "inline")

    # ------------------------------------------------------------------ pulso comercial (solo lectura)

    def _fechas(desde, hasta):
        for nombre, v in (("desde", desde), ("hasta", hasta)):
            if v and not RE_FECHA.match(v):
                raise ErrorApi("PARAMETRO_INVALIDO", f"«{nombre}» debe ser una fecha YYYY-MM-DD válida.", 422)

    @app.get("/api/comercial/opciones", response_model=OpcionesComerciales, tags=["comercial"])
    def comercial_opciones():
        with conectar(aj.ruta_bd) as c:
            return co.opciones(c)

    @app.get("/api/comercial/resumen", response_model=ResumenComercial, tags=["comercial"])
    def comercial_resumen(mes: Mes = None, desde: Fecha = None, hasta: Fecha = None, canal: ParamCanal = None,
                          comparacion: ParamComp = "equivalente", estados: ParamEstados = "todas"):
        _fechas(desde, hasta)
        with conectar(aj.ruta_bd) as c:
            return co.resumen(c, mes, desde, hasta, canal, comparacion, estados, aj.criterios_comerciales)

    @app.get("/api/comercial/tendencia", response_model=TendenciaComercial, tags=["comercial"])
    def comercial_tendencia(mes: Mes = None, desde: Fecha = None, hasta: Fecha = None, canal: ParamCanal = None,
                            comparacion: ParamComp = "equivalente", estados: ParamEstados = "todas"):
        _fechas(desde, hasta)
        with conectar(aj.ruta_bd) as c:
            return co.tendencia(c, mes, desde, hasta, canal, comparacion, estados)

    @app.get("/api/comercial/canales", response_model=CanalesComerciales, tags=["comercial"])
    def comercial_canales(mes: Mes = None, desde: Fecha = None, hasta: Fecha = None, comparacion: ParamComp = "equivalente",
                          estados: ParamEstados = "todas"):
        _fechas(desde, hasta)
        with conectar(aj.ruta_bd) as c:
            return co.canales(c, mes, desde, hasta, comparacion, estados)

    @app.get("/api/comercial/productos", response_model=ProductosComerciales, tags=["comercial"])
    def comercial_productos(mes: Mes = None, desde: Fecha = None, hasta: Fecha = None, canal: ParamCanal = None,
                            comparacion: ParamComp = "equivalente", estados: ParamEstados = "todas",
                            orden: Literal["importe", "unidades", "transacciones"] = "importe",
                            limite: Annotated[int, Query(ge=1, le=50)] = 10):
        _fechas(desde, hasta)
        with conectar(aj.ruta_bd) as c:
            return co.productos(c, mes, desde, hasta, canal, comparacion, estados, orden, limite)

    # ------------------------------------------------------------------ pipeline
    @app.get("/api/pipeline/estado", response_model=EstadoPipeline, tags=["pipeline"])
    def pipeline_estado():
        ultima, fases = None, sv._fases(None)
        if aj.ruta_bd.is_file():
            try:
                with conectar(aj.ruta_bd) as c:
                    fila_ult = sv.fila(c, "SELECT * FROM ejecuciones ORDER BY inicio DESC, rowid DESC LIMIT 1")
                    if fila_ult:
                        bit = sv.bitacora_de(aj, fila_ult["lote_id"])
                        ultima, fases = sv._ejecucion_publica(fila_ult, bit), sv._fases(bit, fila_ult.get("etapa_fallida"))
            except ErrorApi:
                pass
        return {"ejecutor": runner.estado(), "ultima": ultima, "fases": fases, "ruta_bd_existe": aj.ruta_bd.is_file(),
                "fuentes": {"oficiales": aj.rutas_fuentes is None,
                            "verificacion_sha256": aj.rutas_fuentes is None},
                "nota_progreso": ("El pipeline no emite progreso por fase mientras corre: se muestra «en ejecución» y, al terminar, "
                                  "el resultado real y la duración medida de cada fase.")}

    @app.post("/api/pipeline/ejecutar", response_model=RespuestaEjecucion, status_code=202, tags=["pipeline"])
    def pipeline_ejecutar(solicitud: SolicitudEjecucion, request: Request):
        origen = request.headers.get("origin")
        if origen is not None and origen not in aj.origenes:
            raise ErrorApi("ORIGEN_NO_PERMITIDO", "Esta acción solo se acepta desde la aplicación local de KOVA.", 403)
        if not solicitud.confirmar:
            raise ErrorApi("CONFIRMACION_REQUERIDA", "Confirma la ejecución: reemplazará el contenido de la base de datos.", 400)
        inicio = runner.iniciar()
        if inicio is None:
            raise ErrorApi("PIPELINE_EN_EJECUCION", "Ya hay una ejecución en curso. Espera a que termine.", 409)
        return {"iniciado_en": inicio, "mensaje": "Ejecución iniciada. Consulta /api/pipeline/estado para ver el resultado."}

    # ------------------------------------------------------------------ frontend compilado (opcional)
    dist = aj.dist_frontend
    if (dist / "index.html").is_file():
        @app.get("/{ruta:path}", include_in_schema=False)
        def spa(ruta: str):
            if ruta.startswith("api/"):
                raise ErrorApi("RUTA_NO_ENCONTRADA", "Ruta de API inexistente.", 404)
            candidato = (dist / ruta).resolve()
            if ruta and dist.resolve() in candidato.parents and candidato.is_file():
                return FileResponse(candidato)
            return FileResponse(dist / "index.html")

    return app


app = crear_app()
