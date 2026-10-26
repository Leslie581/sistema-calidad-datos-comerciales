"""
Reporte final y evidencias del pipeline (responsable: Nono). Escribe en `salidas/etapa_nono/`.

Todo se calcula leyendo la BASE DE DATOS YA CONFIRMADA (no los objetos en memoria): lo que se reporta es lo que
quedó persistido. Los gráficos y tablas salen de la ejecución real; nada se escribe a mano.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .config import RUTA_DIAGNOSTICO, TOLERANCIA_MONTO  # noqa: E402
from .persistencia.carga import abrir_conexion  # noqa: E402
from .validacion.esquemas import TransaccionLimpia  # noqa: E402

log = logging.getLogger(__name__)
COLOR_PRINCIPAL, COLOR_ALERTA, COLOR_GRIS = "#2a6f97", "#c1121f", "#6c757d"
EJEMPLOS_ACEPTADOS = ["POS-2026-0002", "WEB-00002", "POS-2026-0005", "POS-2026-0075", "WEB-00508", "POS-2026-0031",
                      "WEB-00040"]
EJEMPLOS_RECHAZADOS = ["POS-2026-0001", "POS-2026-0216", "POS-2026-0035", "POS-2026-0017", "POS-2026-0493",
                       "WEB-00004", "WEB-00083", "WEB-00124", "WEB-00001", "WEB-00477"]
CONSULTAS = {
    "1_conservacion": "SELECT (SELECT COUNT(*) FROM transacciones_limpias) AS limpias, "
                      "(SELECT COUNT(*) FROM cuarentena_errores) AS cuarentena, "
                      "(SELECT filas_entrada FROM ejecuciones WHERE estado='COMPLETADO' ORDER BY fin DESC LIMIT 1) AS entrada",
    "2_cuarentena_por_motivo": "SELECT codigos_error, COUNT(*) AS n FROM cuarentena_errores "
                               "GROUP BY codigos_error ORDER BY n DESC, codigos_error",
    "3_integridad_referencial": "SELECT COUNT(*) AS huerfanas_en_limpias FROM transacciones_limpias t "
                                "LEFT JOIN catalogo_productos c USING (id_producto) WHERE c.id_producto IS NULL",
    "4_ventas_por_canal_y_segmento": "SELECT origen, segmento_importe, COUNT(*) AS n, "
                                     "ROUND(SUM(monto_total_mxn_cap), 2) AS monto_cap_mxn FROM transacciones_limpias "
                                     "GROUP BY origen, segmento_importe ORDER BY origen, segmento_importe",
    "5_trazabilidad_web_00508": "SELECT id_transaccion, monto_total_origen, monto_total_mxn, monto_total_mxn_cap, correcciones "
                                "FROM transacciones_limpias WHERE id_transaccion = 'WEB-00508'",
    "6_historial_ejecuciones": "SELECT lote_id, estado, filas_entrada, filas_limpias, filas_cuarentena "
                               "FROM ejecuciones ORDER BY inicio",
}


def _df(conn, sql, params=()):
    return pd.read_sql_query(sql, conn, params=params)


def _es_fecha_iso(texto) -> bool:
    try:
        return datetime.strptime(texto, "%Y-%m-%d").strftime("%Y-%m-%d") == texto
    except (TypeError, ValueError):
        return False


def _validadores() -> list[dict]:
    dec = TransaccionLimpia.__pydantic_decorators__.field_validators
    return [{"validador": n, "campos": list(d.info.fields), "modo": d.info.mode,
             "regla": (d.func.__doc__ or "").strip().splitlines()[0] if d.func.__doc__ else ""} for n, d in dec.items()]


def _verificar_validas(conn, resumen) -> dict:
    """Comprueba sobre la BD que las transacciones válidas cumplen lo prometido (fechas, moneda, importes, escala)."""
    t = _df(conn, "SELECT * FROM transacciones_limpias")
    mm = resumen["transformacion"]["minmax"]
    seg = resumen["transformacion"]["segmentos"]
    esperado_mm = ((t["monto_total_mxn_cap"] - mm["min"]) / (mm["max"] - mm["min"])).clip(0, 1)
    esperado_seg = t["monto_total_mxn_cap"].map(
        lambda x: "Bajo" if x <= seg["corte_bajo_medio"] else "Medio" if x <= seg["corte_medio_alto"] else "Alto")
    return {
        "filas": len(t),
        "fechas_iso_validas": int(t["fecha_venta"].map(_es_fecha_iso).sum()),
        "rango_fechas": [t["fecha_venta"].min(), t["fecha_venta"].max()],
        "moneda_mxn": int((t["moneda"] == "MXN").sum()),
        "moneda_original": t["moneda_original"].value_counts().to_dict(),
        "monto_incoherente_con_cantidad_x_precio": int(
            ((t["cantidad"] * t["precio_unitario_mxn"]).round(2) - t["monto_total_mxn"]).abs().gt(TOLERANCIA_MONTO).sum()),
        "monto_minmax_min": float(t["monto_minmax"].min()), "monto_minmax_max": float(t["monto_minmax"].max()),
        "minmax_difiere_del_recalculo_(>1e-6)": int((t["monto_minmax"] - esperado_mm).abs().gt(1e-6).sum()),
        "segmento_difiere_del_recalculo": int((t["segmento_importe"] != esperado_seg).sum()),
        "segmentos": t["segmento_importe"].value_counts().to_dict(),
        "cantidad_cap_mayor_que_cantidad": int((t["cantidad_cap"] > t["cantidad"]).sum()),
        "con_valor_original_distinto_del_tratado": {
            "cantidad": int((t["cantidad_cap"] != t["cantidad"]).sum()),
            "monto": int(((t["monto_total_mxn_cap"] - t["monto_total_mxn"]).abs() > 0.005).sum())},
    }


def generar_reporte_final(resumen: dict, resultado, df: pd.DataFrame, dir_salida, ruta_bd) -> dict:
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    (dir_salida / "graficas").mkdir(exist_ok=True)

    def guardar_json(nombre, obj):
        (dir_salida / nombre).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    with closing(abrir_conexion(ruta_bd)) as conn:
        lim = _df(conn, "SELECT origen, COUNT(*) AS limpias FROM transacciones_limpias GROUP BY origen")
        cua = _df(conn, "SELECT origen, COUNT(*) AS cuarentena FROM cuarentena_errores GROUP BY origen")
        conteos = (pd.DataFrame({"origen": ["FISICA", "ONLINE"]}).merge(lim, how="left").merge(cua, how="left")
                   .fillna(0).astype({"limpias": int, "cuarentena": int}))
        conteos["entrada"] = conteos["origen"].map(resumen["filas_por_origen"]).fillna(0).astype(int)
        conteos["cuadra"] = conteos["entrada"] == conteos["limpias"] + conteos["cuarentena"]
        total = {"origen": "TOTAL", **{c: int(conteos[c].sum()) for c in ("limpias", "cuarentena", "entrada")}}
        total["cuadra"] = total["entrada"] == total["limpias"] + total["cuarentena"]
        conteos = pd.concat([conteos, pd.DataFrame([total])], ignore_index=True)
        conteos.to_csv(dir_salida / "02_conteos_conservacion.csv", index=False, encoding="utf-8")

        por_codigo = pd.DataFrame(
            [{"codigo": c, "registros": n, "pct_de_cuarentena": round(100 * n / max(len(resultado.cuarentena), 1), 1)}
             for c, n in resultado.conteo_por_codigo.items()])
        por_codigo.to_csv(dir_salida / "03_cuarentena_por_codigo.csv", index=False, encoding="utf-8")
        _df(conn, "SELECT origen, codigos_error, COUNT(*) AS registros FROM cuarentena_errores "
                  "GROUP BY origen, codigos_error ORDER BY registros DESC, origen").to_csv(
            dir_salida / "03_cuarentena_por_canal_y_combinacion.csv", index=False, encoding="utf-8")
        _df(conn, "SELECT etapa_deteccion, COUNT(*) AS registros FROM cuarentena_errores GROUP BY etapa_deteccion "
                  "ORDER BY registros DESC").to_csv(dir_salida / "03_cuarentena_por_etapa.csv", index=False, encoding="utf-8")

        marcas = ",".join("?" * len(EJEMPLOS_ACEPTADOS))
        _df(conn, f"SELECT id_transaccion, origen, fecha_cruda, fecha_venta, id_producto, cantidad_origen, cantidad, "
                  f"cantidad_cap, moneda_original, precio_unitario_original, precio_unitario_mxn, monto_total_origen, "
                  f"monto_total_mxn, monto_total_mxn_cap, monto_minmax, segmento_importe, id_cliente, email_cliente, "
                  f"correcciones FROM transacciones_limpias WHERE id_transaccion IN ({marcas}) "
                  f"ORDER BY id_transaccion", EJEMPLOS_ACEPTADOS).to_csv(
            dir_salida / "04_ejemplos_aceptados.csv", index=False, encoding="utf-8")
        marcas = ",".join("?" * len(EJEMPLOS_RECHAZADOS))
        _df(conn, f"SELECT id_registro, origen, id_fila_origen, etapa_deteccion, codigos_error, num_motivos, "
                  f"motivo_rechazo_cuarentena, registro_original FROM cuarentena_errores "
                  f"WHERE id_registro IN ({marcas}) ORDER BY id_registro, id_fila_origen", EJEMPLOS_RECHAZADOS).to_csv(
            dir_salida / "05_ejemplos_rechazados.csv", index=False, encoding="utf-8")

        consultas = {n: _df(conn, sql) for n, sql in CONSULTAS.items()}
        with (dir_salida / "07_consultas_verificacion.txt").open("w", encoding="utf-8") as f:
            for n, sql in CONSULTAS.items():
                f.write(f"-- {n}\n{sql};\n\n{consultas[n].to_string(index=False)}\n\n")
        verificacion = _verificar_validas(conn, resumen)
        guardar_json("10_verificacion_transacciones_validas.json", verificacion)

    guardar_json("01_resumen_validacion_pydantic.json", {
        "modelo": "TransaccionLimpia (Pydantic 2, strict=True, extra='ignore')",
        "validadores": _validadores(),
        "validos": len(resultado.validos), "rechazados": len(resultado.cuarentena),
        "registros_por_codigo": resultado.conteo_por_codigo, "registros_por_etapa": resultado.conteo_por_etapa,
        "errores_inesperados": resultado.errores_inesperados,
        "reglas_propuestas_pendientes_de_aprobacion": ["ID_ORIGEN_INCONSISTENTE", "CAMPO_OBLIGATORIO_FALTANTE",
                                                       "ESTADO_INVALIDO", "TIPO_CAMBIO_INCONSISTENTE"]})
    guardar_json("06_resumen_sqlite.json", {**resumen["sqlite"], "ruta_bd": str(ruta_bd), "carga": resumen["carga"]})
    guardar_json("08_metricas_pipeline.json", {
        "lote_id": resumen["lote_id"], "duracion_total_s": resumen["duracion_s"],
        "duracion_etapas_s": resumen["duracion_etapas_s"], "filas_entrada": resumen["filas_entrada"],
        "filas_por_origen": resumen["filas_por_origen"], "entorno": resumen["entorno"],
        "huellas_entrada": resumen["huellas_entrada"], "integridad_originales": resumen.get("integridad_originales"),
        "limpieza": resumen["limpieza"]["conteo_correcciones"], "transformacion": resumen["transformacion"],
        "advertencias": resumen["advertencias"]})

    # --- comparación con las estimaciones del diagnóstico (no se fuerzan: se reporta la diferencia) ---
    ref = json.loads(Path(RUTA_DIAGNOSTICO).read_text(encoding="utf-8"))["cuarentena_esperada"]
    p = {r["origen"]: r for r in conteos.to_dict(orient="records")}
    c = resultado.conteo_por_codigo
    multi = int(sum(1 for r in resultado.cuarentena if r["num_motivos"] > 1))
    filas = [("Transacciones limpias (total)", ref["total_transacciones_limpias_esperado"], p["TOTAL"]["limpias"]),
             ("Cuarentena (total)", ref["total_cuarentena_esperado"], p["TOTAL"]["cuarentena"]),
             ("Limpias física", 562, p["FISICA"]["limpias"]), ("Limpias online", 542, p["ONLINE"]["limpias"]),
             ("Cuarentena física (únicos)", ref["tienda_fisica_registros_unicos_en_cuarentena"], p["FISICA"]["cuarentena"]),
             ("Cuarentena online (únicos)", ref["online_registros_unicos_en_cuarentena"], p["ONLINE"]["cuarentena"]),
             ("DUPLICADO_EXACTO", ref["tienda_fisica_por_regla"]["DUPLICADO_EXACTO"], c.get("DUPLICADO_EXACTO", 0)),
             ("CANTIDAD_INVALIDA", ref["tienda_fisica_por_regla"]["CANTIDAD_INVALIDA"], c.get("CANTIDAD_INVALIDA", 0)),
             ("PRODUCTO_HUERFANO", ref["tienda_fisica_por_regla"]["PRODUCTO_HUERFANO"] + ref["online_por_regla"]["PRODUCTO_HUERFANO"],
              c.get("PRODUCTO_HUERFANO", 0)),
             ("EMAIL_MALFORMADO", ref["online_por_regla"]["EMAIL_MALFORMADO"], c.get("EMAIL_MALFORMADO", 0)),
             ("Registros con más de un motivo", ref["tienda_fisica_con_mas_de_un_motivo"] + ref["online_con_mas_de_un_motivo"]
              + 11, multi),
             ("MONTO_INVALIDO (la referencia lo cuenta junto con CANTIDAD_INVALIDA)", 11, c.get("MONTO_INVALIDO", 0))]
    notas = {"Registros con más de un motivo":
             "La referencia suma 5 (por códigos de regla) + 11 (cantidad inválida + monto) = 16, pero POS-2026-0493 "
             "está en ambos grupos (huérfano y cantidad -1): se cuenta una sola vez → 5 + 11 − 1 = 15 (R13: una "
             "transacción se cuenta una vez)."}
    cmp_df = pd.DataFrame([{"metrica": m, "estimado_diagnostico": e, "obtenido": o, "coincide": e == o,
                            "nota": notas.get(m, "")} for m, e, o in filas])
    cmp_df.to_csv(dir_salida / "09_comparacion_estimaciones.csv", index=False, encoding="utf-8")

    # --- gráficos ---
    fig, ax = plt.subplots(figsize=(8, 4.2))
    d = por_codigo.sort_values("registros")
    ax.barh(d["codigo"], d["registros"], color=COLOR_PRINCIPAL)
    for y, v in enumerate(d["registros"]):
        ax.text(v + 0.8, y, str(v), va="center", fontsize=9)
    ax.set(title="Motivos de cuarentena (un registro puede tener varios)", xlabel="Registros que contienen el código")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(dir_salida / "graficas" / "cuarentena_por_motivo.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    base = conteos[conteos["origen"] != "TOTAL"]
    ax.bar(base["origen"], base["limpias"], color=COLOR_PRINCIPAL, label="Limpias")
    ax.bar(base["origen"], base["cuarentena"], bottom=base["limpias"], color=COLOR_ALERTA, label="Cuarentena")
    for i, r in enumerate(base.itertuples()):
        ax.text(i, r.limpias / 2, str(r.limpias), ha="center", color="white")
        ax.text(i, r.limpias + r.cuarentena / 2, str(r.cuarentena), ha="center", color="white")
    ax.set(title=f"Conservación: {total['entrada']} entrada = {total['limpias']} limpias + {total['cuarentena']} cuarentena",
           ylabel="Registros")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(dir_salida / "graficas" / "conservacion_por_canal.png", dpi=150)
    plt.close(fig)

    return {"conteos": conteos.to_dict(orient="records"), "comparacion_estimaciones": cmp_df.to_dict(orient="records"),
            "verificacion_validas": verificacion, "carpeta": str(dir_salida)}
