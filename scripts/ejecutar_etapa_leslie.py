"""
Ejecuta la etapa de Leslie sobre los datasets OFICIALES y guarda las evidencias en salidas/etapa_leslie/.

Flujo (orden acordado, ambigüedad A2):
    extraer (Yerik) → F1 perfil ANTES (Leslie) → homologar (Yerik) → F2 limpieza (Leslie)
    → USD→MXN + catálogo (Yerik, versión mínima) → F3 IQR/capping (Leslie) → reporte (Leslie)

Uso (desde la raíz del proyecto):
    python scripts/ejecutar_etapa_leslie.py
"""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402

from src.calidad.limpieza import limpiar_registros  # noqa: E402
from src.calidad.outliers import tratar_outliers  # noqa: E402
from src.calidad.perfilado import (clasificar_faltantes_por_canal, metricas_calidad, perfil_a_tabla,  # noqa: E402
                                   perfilar_dataframe, perfilar_fuentes)
from src.calidad.reporte import comparar_con_referencia, graficar_boxplots, tabla_antes_despues  # noqa: E402
from src.config import RUTA_DIAGNOSTICO, RUTA_SALIDAS  # noqa: E402
from src.extraccion import extraer_fuentes, verificar_integridad  # noqa: E402
from src.integracion.catalogo import cruzar_catalogo  # noqa: E402
from src.integracion.homologacion import homologar_columnas  # noqa: E402
from src.integracion.moneda import convertir_a_mxn  # noqa: E402

SALIDA = RUTA_SALIDAS / "etapa_leslie"
EJEMPLOS = ["POS-2026-0001", "POS-2026-0005", "POS-2026-0021", "POS-2026-0031", "POS-2026-0075",
            "POS-2026-0216", "WEB-00002", "WEB-00003", "WEB-00040", "WEB-00237", "WEB-00508"]


def guardar_json(obj, nombre):
    (SALIDA / nombre).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def titulo(t):
    print("\n" + "=" * 80 + f"\n{t}\n" + "=" * 80)


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "graficas").mkdir(exist_ok=True)
    inicio = datetime.now()

    titulo("0. Integridad de los archivos originales (SHA-256)")
    integridad = verificar_integridad()
    print(integridad)
    if not all(integridad.values()):
        print("ERROR: algún archivo original cambió. Se detiene la ejecución.")
        return 1

    titulo("1. Extracción (Yerik · mínima)")
    fuentes = extraer_fuentes()
    print({k: v.shape for k, v in fuentes.items()})

    titulo("2. F1 · Perfil ANTES (Leslie)")
    perfiles = perfilar_fuentes(fuentes)
    guardar_json(perfiles, "01_perfil_antes.json")
    for nombre, perfil in perfiles.items():
        tabla = perfil_a_tabla(perfil)
        tabla.to_csv(SALIDA / f"01_perfil_antes_{nombre}.csv", index=False, encoding="utf-8")
        print(f"\n--- {nombre}: {perfil['filas']} filas × {perfil['columnas']} columnas · completitud "
              f"{perfil['completitud_global_pct']} % · duplicados exactos {perfil['duplicados_exactos']}")
        print(tabla.to_string(index=False))

    titulo("3. Homologación (Yerik · mínima)")
    df_h = homologar_columnas(fuentes)
    print(df_h.groupby("origen").size().to_dict(), "columnas:", len(df_h.columns))

    titulo("4. F1 · Clasificación de faltantes MCAR/MAR (χ²)")
    faltantes = clasificar_faltantes_por_canal(df_h)
    guardar_json(faltantes, "02_faltantes_mcar_mar.json")
    filas_f = [{"origen": r["origen"], "columna": r["columna"], "faltantes": r["faltantes"],
                "pct": r["pct_faltantes"], "vs": p["vs"], "chi2": p.get("chi2"), "gl": p.get("gl"),
                "p_valor": p.get("p_valor"), "esperados<5": p.get("esperados_menores_5"),
                "clasificacion": r["clasificacion"]} for r in faltantes for p in r["pruebas"]]
    pd.DataFrame(filas_f).to_csv(SALIDA / "02_faltantes_mcar_mar.csv", index=False, encoding="utf-8")
    print(pd.DataFrame(filas_f).to_string(index=False))

    titulo("5. F2 · Limpieza e imputación (Leslie)")
    df_l, bitacora = limpiar_registros(df_h)
    guardar_json(bitacora, "03_bitacora_limpieza.json")
    print(json.dumps(bitacora, ensure_ascii=False, indent=2))

    titulo("6. USD→MXN y cruce con catálogo (Yerik · mínima, necesaria para el IQR en MXN)")
    df_m = cruzar_catalogo(convertir_a_mxn(df_l), fuentes["catalogo"])
    usd = df_m[(df_m["moneda_original"] == "USD") & df_m["en_catalogo"]]
    integracion = {"convertidos_usd": int((df_m["moneda_original"] == "USD").sum()),
                   "usd_en_catalogo": len(usd), "usd_dif_max_catalogo": round(float(usd["dif_precio_catalogo"].max()), 4),
                   "huerfanos": df_m.loc[~df_m["en_catalogo"], "origen"].value_counts().to_dict()}
    guardar_json(integracion, "04_integracion_minima.json")
    print(integracion)

    titulo("7. F3 · IQR (factor 1.5) y capping (Leslie)")
    df_o, limites = tratar_outliers(df_m)
    guardar_json(limites, "05_limites_iqr.json")
    print(json.dumps(limites, ensure_ascii=False, indent=2, default=str))

    titulo("8. Comparación ANTES / DESPUÉS")
    comp = tabla_antes_despues(df_h, df_o)
    comp.to_csv(SALIDA / "06_antes_despues.csv", index=False, encoding="utf-8")
    print(comp.to_string(index=False))
    perfil_despues = perfilar_dataframe(
        df_o[["id_transaccion", "origen", "cantidad", "cantidad_cap", "precio_unitario_mxn", "monto_total_mxn",
              "monto_total_mxn_cap", "id_cliente", "email_cliente", "direccion_envio"]], "despues_etapa_leslie")
    guardar_json(perfil_despues, "06_perfil_despues.json")

    titulo("9. Comparación con la REFERENCIA del diagnóstico (Avance 01)")
    fis_h, onl_h = df_h[df_h["origen"] == "FISICA"], df_h[df_h["origen"] == "ONLINE"]
    m_fis = metricas_calidad(fis_h)
    p = {(r["origen"], r["columna"], pr["vs"]): pr.get("p_valor") for r in faltantes for pr in r["pruebas"]}
    lc, lm = limites["cantidad"]["FISICA"], limites["monto_mxn"]
    base = df_o["es_base_estadistica"]
    resultados = {
        "fisica_filas": perfiles["fisica"]["filas"], "fisica_completitud": perfiles["fisica"]["completitud_global_pct"],
        "fisica_duplicados": perfiles["fisica"]["duplicados_exactos"],
        "fisica_monto_nulo": perfiles["fisica"]["nulos"]["monto_total_mxn"],
        "fisica_id_cliente_nulo": perfiles["fisica"]["nulos"]["id_cliente"],
        "fisica_cantidad_invalida": m_fis["cantidad_menor_igual_0"],
        "fisica_monto_media": m_fis["monto_total_media"], "fisica_monto_mediana": m_fis["monto_total_mediana"],
        "fisica_monto_asimetria": m_fis["monto_total_asimetria"],
        "p_idcliente_sucursal": p[("FISICA", "id_cliente", "punto_venta")],
        "p_idcliente_metodo": p[("FISICA", "id_cliente", "metodo_pago")],
        "p_monto_sucursal": p[("FISICA", "monto_total", "punto_venta")],
        "p_monto_metodo": p[("FISICA", "monto_total", "metodo_pago")],
        "online_completitud": perfiles["online"]["completitud_global_pct"],
        "online_email_faltante": perfiles["online"]["nulos"]["customer_email"],
        "online_direccion_nula": perfiles["online"]["nulos"]["shipping_address"],
        "online_inconsistentes": metricas_calidad(onl_h)["monto_inconsistente"],
        "p_dir_estado": p[("ONLINE", "direccion_envio", "estado_pedido")],
        "p_dir_pasarela": p[("ONLINE", "direccion_envio", "metodo_pago")],
        "p_email_pasarela": p[("ONLINE", "email_cliente", "metodo_pago")],
        "p_email_moneda": p[("ONLINE", "email_cliente", "moneda")],
        "fisica_huerfanos": integracion["huerfanos"].get("FISICA"), "online_huerfanos": integracion["huerfanos"].get("ONLINE"),
        "usd_dif_max_catalogo": integracion["usd_dif_max_catalogo"],
        "base_total": limites["base_estadistica"]["total"],
        "base_fisica": limites["base_estadistica"]["por_canal"]["FISICA"],
        "base_online": limites["base_estadistica"]["por_canal"]["ONLINE"],
        "cant_q1": lc["Q1"], "cant_q3": lc["Q3"], "cant_ls": lc["LS"], "cant_tope": lc["tope_entero"],
        "cant_recortadas": lc["recortados"],
        "monto_q1": lm["Q1"], "monto_q3": lm["Q3"], "monto_iqr": lm["IQR"], "monto_ls": lm["LS"],
        "monto_mediana": lm["mediana"], "monto_asimetria": lm["asimetria"],
        "monto_outliers_base": lm["outliers_superiores"], "monto_recortados": lm["recortados"],
        "monto_cap_max": float(df_o.loc[base, "monto_total_mxn_cap"].max()),
    }
    referencia = json.loads(Path(RUTA_DIAGNOSTICO).read_text(encoding="utf-8"))
    tabla_ref = comparar_con_referencia(resultados, referencia)
    tabla_ref.to_csv(SALIDA / "07_comparacion_referencia.csv", index=False, encoding="utf-8")
    with pd.option_context("display.max_colwidth", 70, "display.width", 220):
        print(tabla_ref.drop(columns="explicacion").to_string(index=False))
    print(f"\nCoinciden: {int(tabla_ref['coincide'].sum())} / {len(tabla_ref)}")
    for _, r in tabla_ref[~tabla_ref["coincide"]].iterrows():
        print(f"\n· {r['metrica']}: referencia {r['referencia']} vs obtenido {r['obtenido']}\n  {r['explicacion']}")

    titulo("10. Ejemplos de trazabilidad y entrega para Yerik")
    cols = ["id_transaccion", "origen", "id_fila_origen", "es_duplicado", "cantidad_origen", "cantidad", "cantidad_cap",
            "moneda_original", "precio_unitario", "precio_unitario_mxn", "monto_total_origen", "monto_total",
            "monto_total_mxn", "monto_cantidad_cap_mxn", "monto_total_mxn_cap", "es_outlier_cantidad",
            "es_outlier_monto", "en_catalogo", "id_cliente", "email_cliente", "direccion_envio", "correcciones"]
    ej = df_o[df_o["id_transaccion"].isin(EJEMPLOS)][cols].sort_values(["id_transaccion", "id_fila_origen"])
    ej.to_csv(SALIDA / "08_ejemplos_trazabilidad.csv", index=False, encoding="utf-8")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(ej.to_string(index=False))
    entrega = df_o.copy()
    for c in ("alertas", "correcciones"):
        entrega[c] = entrega[c].map(lambda v: json.dumps(v, ensure_ascii=False))
    entrega.to_csv(SALIDA / "09_salida_etapa_leslie.csv", index=False, encoding="utf-8")
    print(f"\nSalida completa: {len(entrega)} filas × {entrega.shape[1]} columnas → 09_salida_etapa_leslie.csv")

    titulo("11. Gráficas")
    fis_o = df_o[(df_o["origen"] == "FISICA") & (df_o["cantidad"] > 0)]
    fis_base = fis_o[fis_o["es_base_estadistica"]]
    g1 = graficar_boxplots(fis_base["cantidad"], fis_base["cantidad_cap"],
                           "Cantidad por ticket, tienda física (base estadística)", "Unidades (escala log)",
                           SALIDA / "graficas" / "boxplot_cantidad_fisica.png", escala_log=True,
                           etiquetas=("Antes: cantidad", "Después: cantidad_cap"))
    crudo_mxn = (df_o["monto_total_origen"] * df_o["tipo_cambio_aplicado"])[base]
    g2 = graficar_boxplots(crudo_mxn, df_o.loc[base, "monto_total_mxn_cap"],
                           "Importe por transacción en MXN, base estadística (ambos canales)", "MXN (escala log)",
                           SALIDA / "graficas" / "boxplot_importe_mxn.png", escala_log=True,
                           etiquetas=("Antes: total crudo", "Después: monto_total_mxn_cap (base)"))
    print(g1, g2, sep="\n")

    import numpy, scipy  # noqa: E401
    guardar_json({"inicio": inicio.isoformat(timespec="seconds"),
                  "duracion_s": round((datetime.now() - inicio).total_seconds(), 2),
                  "python": platform.python_version(), "pandas": pd.__version__, "numpy": numpy.__version__,
                  "scipy": scipy.__version__, "integridad_originales": integridad,
                  "coincidencias_referencia": f"{int(tabla_ref['coincide'].sum())}/{len(tabla_ref)}"},
                 "00_ejecucion.json")
    print("\nEvidencias en:", SALIDA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
