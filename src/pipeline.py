"""
Orquestador del pipeline ETL completo (responsable: Nono) — une el trabajo de los tres ingenieros.

    python -m src.pipeline [--bd RUTA.db] [--salida CARPETA] [--no-reemplazar]

ORDEN DE EJECUCIÓN (7 fases oficiales del profesor + extracción y reporte)
     1. Extracción CSV/JSON + verificación SHA-256 de los originales        (Yerik · F0)
     2. Perfilado inicial y clasificación MCAR/MAR                          (Leslie · Fase 1)
     3. Homologación de esquemas                                            (Yerik)
     4. Limpieza e imputación                                               (Leslie · Fase 2)
     5. Integración: fechas ISO, USD→MXN, cruce con catálogo y huérfanos   (Yerik · Fase 4)
     6. IQR y capping                                                       (Leslie · Fase 3)
     7. Min-Max y discretización                                            (Yerik · Fase 5)
     8. Validación Pydantic y segregación a cuarentena                      (Nono · Fase 6)
     9. Carga transaccional SQLite                                          (Nono · Fase 7)
    10. Reporte final y evidencias                                          (Nono)
    Decisión: la normalización de fechas (pedida en 7.° lugar) se ejecuta DENTRO de la integración (paso 5): no
    depende del IQR ni lo afecta (Yerik §4), y el IQR sí necesita el importe en MXN y el cruce con el catálogo
    (ambigüedad A2). Las siete fases oficiales se cumplen todas; solo cambia el orden interno.

ERRORES: por REGISTRO (recuperables) → cuarentena y el lote continúa. GLOBALES (archivo ilegible, contrato roto,
huella SHA-256 distinta, conservación violada, fallo de BD) → estado FALLIDO, bitácora y log con la causa; la BD
conserva los datos de la última ejecución COMPLETADA. Ninguna excepción llega a la consola como traceback.
"""
from __future__ import annotations

import argparse
import json
import logging
import platform
import sqlite3
import sys
import time
import traceback
import uuid
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .calidad.limpieza import limpiar_registros
from .calidad.outliers import tratar_outliers
from .calidad.perfilado import clasificar_faltantes_por_canal, perfilar_fuentes
from .config import RUTA_BD, RUTA_SALIDAS_NONO, RUTAS_FUENTES
from .contratos import ErrorContrato
from .extraccion import ErrorExtraccion, calcular_sha256, extraer_fuentes, verificar_integridad
from .integracion import integrar
from .integracion.homologacion import homologar_columnas
from .integracion.transformacion import transformar
from .persistencia.carga import (ErrorCarga, abrir_conexion, cargar_lote, crear_tablas, filas_catalogo, registrar_fallo,
                                 resumen_bd)
from .validacion.cuarentena import ErrorConservacion, validar_lote

log = logging.getLogger("src.pipeline")
ERRORES_GLOBALES_PREVISTOS = ("ErrorExtraccion", "ErrorContrato", "ErrorIntegridad", "ErrorConservacion", "ErrorCarga")


class ErrorIntegridad(Exception):
    """Un archivo original no coincide con la huella SHA-256 registrada en el diagnóstico (R: originales de solo lectura)."""


class _Seguimiento:
    """Mide cada etapa y recuerda en cuál estamos, para atribuir una falla global."""

    def __init__(self):
        self.actual = "INICIO"
        self.duraciones: dict[str, float] = {}

    def etapa(self, nombre: str):
        seg = self

        class _Ctx:
            def __enter__(self_):
                seg.actual = nombre
                self_.t0 = time.perf_counter()
                log.info("▶ %s", nombre)

            def __exit__(self_, tipo, exc, tb):
                seg.duraciones[nombre] = round(time.perf_counter() - self_.t0, 3)
                return False

        return _Ctx()


def _entorno() -> dict:
    import pydantic
    return {"python": platform.python_version(), "pandas": pd.__version__, "pydantic": pydantic.VERSION,
            "sqlite": sqlite3.sqlite_version, "so": platform.platform()}


def _configurar_log(archivo: Path, consola: bool) -> list[logging.Handler]:
    raiz = logging.getLogger("src")
    raiz.setLevel(logging.INFO)
    manejadores = []
    archivo.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for h in [logging.FileHandler(archivo, encoding="utf-8")] + ([logging.StreamHandler(sys.stdout)] if consola else []):
        h.setFormatter(fmt)
        raiz.addHandler(h)
        manejadores.append(h)
    return manejadores


def _escribir_json(ruta: Path, obj) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def ejecutar_pipeline(rutas: dict[str, Path] | None = None, ruta_bd: str | Path = RUTA_BD,
                      dir_salida: str | Path = RUTA_SALIDAS_NONO, hoy: date | None = None, reemplazar: bool = True,
                      verificar_huellas: bool | None = None, generar_reportes: bool = True,
                      consola: bool = False) -> dict:
    """Ejecuta el ETL completo y devuelve el resumen. Nunca lanza por datos: los fallos globales quedan en `estado`."""
    inicio_dt = datetime.now()
    lote_id = inicio_dt.strftime("L%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    dir_salida = Path(dir_salida)
    hoy = hoy or date.today()
    verificar_huellas = (rutas is None) if verificar_huellas is None else verificar_huellas
    seg = _Seguimiento()
    resumen: dict = {"lote_id": lote_id, "estado": "INICIADO", "inicio": inicio_dt.isoformat(timespec="seconds"),
                     "fecha_referencia": hoy.isoformat(), "entorno": _entorno(), "advertencias": [],
                     "ruta_bd": str(ruta_bd)}
    manejadores = _configurar_log(dir_salida / "logs" / f"pipeline_{lote_id}.log", consola)
    resultado = df = fuentes = None
    try:
        rutas_usadas = rutas or RUTAS_FUENTES
        with seg.etapa("1. Extracción"):
            resumen["huellas_entrada"] = {Path(r).name: calcular_sha256(r) for r in rutas_usadas.values()
                                          if Path(r).exists()}
            if verificar_huellas:
                integ = verificar_integridad(rutas_usadas)
                resumen["integridad_originales"] = integ
                if not all(integ.values()):
                    raise ErrorIntegridad(f"Archivos originales modificados: {[k for k, v in integ.items() if not v]}")
            fuentes = extraer_fuentes(rutas_usadas)
            resumen["filas_fuentes"] = {k: len(v) for k, v in fuentes.items()}

        with seg.etapa("2. Perfilado inicial y MCAR/MAR (informativo)"):
            resumen["perfil_antes"] = _informativo(resumen, "perfilado", lambda: perfilar_fuentes(fuentes))

        with seg.etapa("3. Homologación"):
            df = homologar_columnas(fuentes)
            resumen["filas_entrada"] = len(df)
            resumen["filas_por_origen"] = df.groupby("origen").size().to_dict()
        _informativo(resumen, "faltantes_mcar_mar", lambda: clasificar_faltantes_por_canal(df), guardar=False)

        with seg.etapa("4. Limpieza e imputación"):
            df, resumen["limpieza"] = limpiar_registros(df)
        with seg.etapa("5. Integración (fechas, USD→MXN, catálogo)"):
            df = integrar(df, fuentes["catalogo"])
        with seg.etapa("6. IQR y capping"):
            df, resumen["iqr"] = tratar_outliers(df)
        with seg.etapa("7. Min-Max y discretización"):
            df, resumen["transformacion"] = transformar(df)
        with seg.etapa("8. Validación Pydantic y cuarentena"):
            resultado = validar_lote(df, lote_id, hoy=hoy)
            resumen["validacion"] = {"validos": len(resultado.validos), "cuarentena": len(resultado.cuarentena),
                                     "por_codigo": resultado.conteo_por_codigo, "por_etapa": resultado.conteo_por_etapa,
                                     "errores_inesperados": resultado.errores_inesperados}
            log.info("Válidos=%d · cuarentena=%d (de %d)", len(resultado.validos), len(resultado.cuarentena), len(df))
        with seg.etapa("9. Carga transaccional SQLite"):
            with closing(abrir_conexion(ruta_bd)) as conn:
                crear_tablas(conn)
                resumen["carga"] = cargar_lote(
                    conn, {"lote_id": lote_id, "inicio": resumen["inicio"], "filas_entrada": len(df),
                           "huellas_entrada": resumen["huellas_entrada"], "entorno": resumen["entorno"]},
                    resultado.validos, resultado.cuarentena, filas_catalogo(fuentes["catalogo"]), reemplazar)
                resumen["sqlite"] = resumen_bd(conn)
        resumen["estado"] = "COMPLETADO"
    except Exception as e:  # noqa: BLE001 — frontera del pipeline: todo fallo global se clasifica y se registra
        tipo = type(e).__name__
        previsto = tipo in ERRORES_GLOBALES_PREVISTOS
        resumen.update(estado="FALLIDO", etapa_fallida=seg.actual, tipo_error=tipo, error_previsto=previsto,
                       error=str(e))
        log.error("FALLO GLOBAL en «%s» (%s, %s): %s", seg.actual, tipo, "previsto" if previsto else "IMPREVISTO", e)
        if not previsto:
            resumen["traceback"] = traceback.format_exc()
            log.error("Traceback completo:\n%s", resumen["traceback"])
        try:
            with closing(abrir_conexion(ruta_bd)) as conn:
                resumen["fallo_registrado_en_bd"] = registrar_fallo(
                    conn, lote_id, resumen["inicio"], seg.actual, f"{tipo}: {e}", resumen.get("huellas_entrada"),
                    resumen["entorno"], resumen.get("filas_entrada"))
        except Exception as e2:  # noqa: BLE001
            resumen["fallo_registrado_en_bd"] = False
            log.error("No se pudo abrir la BD para registrar el fallo: %s: %s", type(e2).__name__, e2)
    finally:
        resumen["fin"] = datetime.now().isoformat(timespec="seconds")
        resumen["duracion_s"] = round((datetime.now() - inicio_dt).total_seconds(), 3)
        resumen["duracion_etapas_s"] = seg.duraciones
        if generar_reportes and resumen["estado"] == "COMPLETADO":
            try:
                from .reporte_final import generar_reporte_final
                with seg.etapa("10. Reporte final y evidencias"):
                    resumen["reporte"] = generar_reporte_final(resumen, resultado, df, dir_salida, ruta_bd)
                resumen["duracion_etapas_s"] = seg.duraciones
            except Exception as e:  # noqa: BLE001 — un reporte fallido no invalida la carga ya confirmada
                resumen["advertencias"].append(f"Reporte final incompleto: {type(e).__name__}: {e}")
                log.error("Reporte final falló: %s\n%s", e, traceback.format_exc())
        try:
            _escribir_json(dir_salida / "bitacoras" / f"bitacora_{lote_id}.json", _sin_pesados(resumen))
        except OSError as e:
            log.error("No se pudo escribir la bitácora: %s", e)
        for h in manejadores:
            logging.getLogger("src").removeHandler(h)
            h.close()
    return resumen


def _informativo(resumen: dict, nombre: str, fn, guardar: bool = True):
    """Etapa de diagnóstico que no debe detener el ETL: si falla se deja constancia visible (no se oculta)."""
    try:
        r = fn()
        return r if guardar else None
    except Exception as e:  # noqa: BLE001
        msg = f"{nombre}: {type(e).__name__}: {e}"
        resumen["advertencias"].append(msg)
        log.warning("Etapa informativa omitida → %s\n%s", msg, traceback.format_exc())
        return None


def _sin_pesados(resumen: dict) -> dict:
    """Bitácora legible: se omite el perfil completo (ya se guarda aparte en el reporte)."""
    return {k: v for k, v in resumen.items() if k not in ("perfil_antes",)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.pipeline", description="Pipeline ETL con validación y cuarentena.")
    ap.add_argument("--bd", default=str(RUTA_BD), help="ruta de la base SQLite (por omisión %(default)s)")
    ap.add_argument("--salida", default=str(RUTA_SALIDAS_NONO), help="carpeta de evidencias (por omisión %(default)s)")
    for nombre in ("catalogo", "fisica", "online"):
        ap.add_argument(f"--{nombre}", help=f"ruta alterna del archivo «{nombre}» (pruebas con datos corruptos; "
                                            "desactiva la verificación SHA-256)")
    ap.add_argument("--no-reemplazar", action="store_true",
                    help="agrega el lote en vez de reemplazar el contenido (una transacción repetida provoca rollback)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")      # consola de Windows (cp1252)
    alternas = {k: Path(getattr(args, k)) for k in ("catalogo", "fisica", "online") if getattr(args, k)}
    rutas = {**RUTAS_FUENTES, **alternas} if alternas else None
    r = ejecutar_pipeline(rutas, ruta_bd=args.bd, dir_salida=args.salida, reemplazar=not args.no_reemplazar, consola=True)
    print("\n" + "=" * 70)
    print(f"Lote: {r['lote_id']}   Estado: {r['estado']}   Duración: {r['duracion_s']} s")
    if r["estado"] == "COMPLETADO":
        v = r["validacion"]
        print(f"Entrada: {r['filas_entrada']}  →  limpias: {v['validos']}  +  cuarentena: {v['cuarentena']}")
        for cod, n in v["por_codigo"].items():
            print(f"   {cod:<28}{n:>5}")
        print(f"Base de datos: {r['ruta_bd']}")
        print(f"Evidencias:    {args.salida}")
        for a in r["advertencias"]:
            print("ADVERTENCIA:", a)
        return 0
    print(f"FALLIDO en «{r['etapa_fallida']}» ({r['tipo_error']}): {r['error']}")
    print(f"Detalle en el log de {args.salida}/logs/ y en la bitácora. La base de datos conserva la última carga válida.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
