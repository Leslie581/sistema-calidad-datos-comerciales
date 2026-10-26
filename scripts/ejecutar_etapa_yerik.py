"""
Ejecuta la etapa de Yerik sobre los datasets OFICIALES y guarda las evidencias en salidas/etapa_yerik/.

Flujo completo hasta la entrega a Nono (orden acordado, ambigüedad A2):
    extraer → homologar → F2 limpieza (Leslie) → F4 integrar (fechas, USD→MXN, catálogo)
    → F3 IQR/capping (Leslie) → F5 transformar (Min-Max y terciles)

Uso (desde la raíz del proyecto):
    python scripts/ejecutar_etapa_yerik.py
"""
from __future__ import annotations

import json
import platform
import sys
import warnings
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from dateutil import parser as dateutil_parser  # noqa: E402

from src.calidad.limpieza import limpiar_registros  # noqa: E402
from src.calidad.outliers import tratar_outliers  # noqa: E402
from src.config import RUTA_DIAGNOSTICO, RUTA_SALIDAS  # noqa: E402
from src.contratos import (COLUMNAS_AGREGA_CATALOGO, COLUMNAS_AGREGA_FECHAS, COLUMNAS_AGREGA_IMPORTES_MXN,  # noqa: E402
                           COLUMNAS_AGREGA_OUTLIERS, COLUMNAS_AGREGA_TRANSFORMACION, COLUMNAS_HOMOLOGADAS)
from src.extraccion import extraer_fuentes, verificar_integridad  # noqa: E402
from src.integracion import integrar  # noqa: E402
from src.integracion.catalogo import huerfanos  # noqa: E402
from src.integracion.fechas import ZONA_NEGOCIO, ZONA_UTC, diagnostico_formatos, normalizar_fechas  # noqa: E402
from src.integracion.homologacion import homologar_columnas  # noqa: E402
from src.integracion.transformacion import transformar  # noqa: E402

SALIDA = RUTA_SALIDAS / "etapa_yerik"
EJEMPLOS = ["POS-2026-0001", "POS-2026-0003", "POS-2026-0021", "POS-2026-0031", "WEB-00002", "WEB-00003",
            "WEB-00005", "WEB-00237", "WEB-00508"]
COLOR_PRINCIPAL, COLOR_ALERTA, COLOR_GRIS = "#2a6f97", "#c1121f", "#6c757d"


def guardar_json(obj, nombre):
    (SALIDA / nombre).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def titulo(t):
    print("\n" + "=" * 80 + f"\n{t}\n" + "=" * 80)


def a_texto_json(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ("alertas", "correcciones"):
        out[c] = out[c].map(lambda v: json.dumps(v, ensure_ascii=False))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")        # la consola de Windows (cp1252) no imprime → ni acentos
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "graficas").mkdir(exist_ok=True)
    inicio = datetime.now()

    titulo("0. Integridad de los archivos originales (SHA-256)")
    integridad = verificar_integridad()
    print(integridad)
    if not all(integridad.values()):
        print("ERROR: algún archivo original cambió. Se detiene la ejecución.")
        return 1

    titulo("1. Extracción y homologación (Yerik)")
    fuentes = extraer_fuentes()
    print({k: v.shape for k, v in fuentes.items()})
    df_h = homologar_columnas(fuentes)
    por_origen = df_h.groupby("origen").size().to_dict()
    print(por_origen, "columnas:", len(df_h.columns))
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 28):
        print(df_h.drop(columns=["registro_original", "alertas", "correcciones"]).head(5).to_string(index=False))
    cat_antes = {"metodo_pago (física)": fuentes["fisica"]["metodo_pago"].nunique(),
                 "estado_pedido (online)": fuentes["online"]["order_status"].nunique()}
    cat_despues = {"metodo_pago (física)": int(df_h[df_h["origen"] == "FISICA"]["metodo_pago"].nunique()),
                   "estado_pedido (online)": int(df_h[df_h["origen"] == "ONLINE"]["estado_pedido"].nunique())}
    print("categorías antes:", cat_antes, "· después:", cat_despues)
    guardar_json({"filas_por_origen": por_origen, "columnas": list(df_h.columns), "categorias_antes": cat_antes,
                  "categorias_despues": cat_despues}, "01_homologacion.json")
    df_h.drop(columns=["alertas", "correcciones"]).head(20).to_csv(SALIDA / "01_homologacion_muestra.csv",
                                                                    index=False, encoding="utf-8")

    titulo("2. Fechas: formatos detectados y rango (parseo explícito)")
    formatos = diagnostico_formatos(df_h)
    formatos.to_csv(SALIDA / "02_formatos_fecha.csv", index=False, encoding="utf-8")
    print(formatos.to_string(index=False))
    df_l, bitacora = limpiar_registros(df_h)
    df_i = integrar(df_l, fuentes["catalogo"])
    muestra_ids = ["POS-2026-0001", "POS-2026-0002", "POS-2026-0003", "WEB-00002", "WEB-00005"]
    muestra = df_i[df_i["id_transaccion"].isin(muestra_ids)][["id_transaccion", "origen", "fecha_cruda", "fecha_venta"]]
    muestra.to_csv(SALIDA / "02_fechas_muestra.csv", index=False, encoding="utf-8")
    print(muestra.sort_values("id_transaccion").to_string(index=False))
    utc = normalizar_fechas(df_l, ZONA_UTC)["fecha_venta"]
    cambian_epoch = int((utc != df_i["fecha_venta"]).sum())
    print(f"\nZona del epoch: {ZONA_NEGOCIO} · fechas que cambian respecto a UTC: {cambian_epoch}")

    titulo("3. Comparación: lectura con día primero genérica (INCORRECTA, solo demostración) vs parseo explícito")
    fis = df_i[df_i["origen"] == "FISICA"]
    # dateutil con dayfirst=True es el analizador genérico que usa pandas para texto no ISO; con YYYY-MM-DD invierte día y mes.
    generico = fis["fecha_cruda"].map(lambda t: dateutil_parser.parse(t, dayfirst=True).strftime("%Y-%m-%d"))
    mal = int((generico != fis["fecha_venta"]).sum())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mixto_pd = pd.to_datetime(fis["fecha_cruda"], format="mixed", dayfirst=True).dt.strftime("%Y-%m-%d")
    comp_fechas = {"rango_explicito": [fis["fecha_venta"].min(), fis["fecha_venta"].max()],
                   "rango_dateutil_dayfirst_incorrecto": [generico.min(), generico.max()],
                   "fechas_mal_interpretadas_dateutil_dayfirst": mal,
                   "pandas": pd.__version__,
                   "fechas_mal_interpretadas_pd_to_datetime_mixed_en_este_entorno": int((mixto_pd != fis["fecha_venta"]).sum()),
                   "nota": "El resultado de pd.to_datetime(format='mixed', dayfirst=True) depende de la versión de pandas; "
                           "el parseo explícito por patrón no depende de ella."}
    guardar_json(comp_fechas, "03_mixed_vs_explicito.json")
    print(json.dumps(comp_fechas, ensure_ascii=False, indent=2))
    mixto = generico

    titulo("4. USD → MXN a 19.50 verificado contra el catálogo")
    usd = df_i[df_i["moneda_original"] == "USD"]
    usd_cat = usd[usd["en_catalogo"]]
    cols_usd = ["id_transaccion", "id_producto", "precio_unitario", "precio_unitario_mxn", "precio_catalogo_mxn",
                "dif_precio_catalogo", "cantidad", "monto_total_mxn"]
    usd_cat[cols_usd].to_csv(SALIDA / "04_usd_vs_catalogo.csv", index=False, encoding="utf-8")
    resumen_usd = {"pedidos_usd": len(usd), "usd_en_catalogo": len(usd_cat),
                   "dif_max_catalogo": round(float(usd_cat["dif_precio_catalogo"].max()), 4),
                   "mxn_en_catalogo": int(((df_i["moneda_original"] == "MXN") & df_i["en_catalogo"]).sum()),
                   "dif_max_mxn": round(float(df_i[(df_i["moneda_original"] == "MXN")]["dif_precio_catalogo"].max()), 4)}
    guardar_json(resumen_usd, "04_resumen_usd.json")
    print(resumen_usd)
    print(usd_cat[cols_usd][usd_cat["id_transaccion"].isin(["WEB-00002", "WEB-00237"])].to_string(index=False))

    titulo("5. Productos huérfanos (LEFT JOIN, en_catalogo = False)")
    h = huerfanos(df_i)
    h_canal = h["origen"].value_counts().to_dict()
    h_ids = {o: h[h["origen"] == o]["id_producto"].nunique() for o in ("FISICA", "ONLINE")}
    precios_h = h.groupby(["origen", "moneda_original"])["precio_unitario"].agg(["min", "max", "count"]).reset_index()
    h[["id_transaccion", "origen", "id_fila_origen", "id_producto", "precio_unitario", "moneda_original",
       "es_duplicado"]].to_csv(SALIDA / "05_huerfanos.csv", index=False, encoding="utf-8")
    guardar_json({"registros_por_canal": h_canal, "ids_distintos_por_canal": h_ids}, "05_resumen_huerfanos.json")
    print(h_canal, h_ids)
    print(precios_h.to_string(index=False))

    titulo("6. F3 (Leslie) y F5 (Yerik): Min-Max y terciles")
    df_o, limites = tratar_outliers(df_i)
    df_t, parametros = transformar(df_o)
    guardar_json(parametros, "06_parametros_transformacion.json")
    print(json.dumps(parametros, ensure_ascii=False, indent=2))
    cols_tr = ["id_transaccion", "monto_total_origen", "monto_total_mxn", "monto_cantidad_cap_mxn",
               "monto_total_mxn_cap", "monto_minmax", "segmento_importe", "minmax_recortado"]
    ej = df_t[df_t["id_transaccion"].isin(EJEMPLOS)][cols_tr].sort_values("id_transaccion")
    ej.to_csv(SALIDA / "06_ejemplos_transformacion.csv", index=False, encoding="utf-8")
    print(ej.to_string(index=False))
    inval = df_t[pd.to_numeric(df_t["cantidad"], errors="coerce") <= 0]
    print(f"\nRegistros con cantidad <= 0: {len(inval)} · acotados a [0,1]: {int(inval['minmax_recortado'].sum())}")
    seg = (df_t.groupby(["segmento_importe", "es_base_estadistica"]).size().unstack(fill_value=0)
           .reindex(["Bajo", "Medio", "Alto"]))
    seg.columns = ["fuera_de_base", "base"]
    seg.to_csv(SALIDA / "06_segmentos_conteo.csv", encoding="utf-8")
    print(seg.to_string())

    titulo("7. Conservación de registros y comparación con el diagnóstico (Avance 01)")
    mm = df_t["monto_minmax"].astype(float)
    base = df_t["es_base_estadistica"]
    ref = json.loads(Path(RUTA_DIAGNOSTICO).read_text(encoding="utf-8"))
    ri, fis_ref, onl_ref = ref["referencia_integrada"], ref["tienda_fisica"], ref["tienda_online"]
    fis_t, onl_t = df_t[df_t["origen"] == "FISICA"], df_t[df_t["origen"] == "ONLINE"]
    pruebas = [
        ("Filas totales", 620 + 600, len(df_t)),
        ("Filas física", ref["tienda_fisica"]["filas"], len(fis_t)),
        ("Filas online", ref["tienda_online"]["filas"], len(onl_t)),
        ("Fechas no interpretables", fis_ref["fechas_no_parseables"], int(df_t["fecha_venta"].isna().sum())),
        ("Rango fechas física (min)", fis_ref["rango_fechas_parseo_explicito"][0], fis_t["fecha_venta"].min()),
        ("Rango fechas física (max)", fis_ref["rango_fechas_parseo_explicito"][1], fis_t["fecha_venta"].max()),
        ("Fechas mal leídas por lectura genérica dayfirst", fis_ref["advertencia_parseo_mixed_dayfirst"]["fechas_que_cambian"], mal),
        ("Rango erróneo dayfirst (min)", fis_ref["advertencia_parseo_mixed_dayfirst"]["rango_resultante_erroneo"][0], mixto.min()),
        ("Rango erróneo dayfirst (max)", fis_ref["advertencia_parseo_mixed_dayfirst"]["rango_resultante_erroneo"][1], mixto.max()),
        ("Epoch: fechas distintas UTC vs México", onl_ref["epoch_fecha_distinta_utc_vs_mexico"], cambian_epoch),
        ("Pedidos USD", onl_ref["currency"]["USD"], len(usd)),
        ("USD con producto en catálogo", onl_ref["precio_vs_catalogo"]["USD_x_19.50_coinciden_tolerancia_0.50"], len(usd_cat)),
        ("Huérfanos física", fis_ref["huerfanos"], h_canal.get("FISICA")),
        ("Huérfanos online", onl_ref["huerfanos"], h_canal.get("ONLINE")),
        ("Base estadística", ref["referencia_integrada"]["filas_base_estadistica_sin_duplicados_invalidos_ni_huerfanos"],
         parametros["minmax"]["n_base"]),
        ("Min-Max: mínimo de la base", ri["monto_cap_min_max"][0], parametros["minmax"]["min"]),
        ("Min-Max: máximo de la base", ri["monto_cap_min_max"][1], parametros["minmax"]["max"]),
        ("Tercil 1 (corte Bajo/Medio)", ri["terciles_monto_cap"]["P33.3"], round(parametros["segmentos"]["corte_bajo_medio"], 2)),
        ("Tercil 2 (corte Medio/Alto)", ri["terciles_monto_cap"]["P66.7"], round(parametros["segmentos"]["corte_medio_alto"], 2)),
        ("Segmento Bajo (base)", ri["segmentos_en_base"]["Bajo"], parametros["segmentos"]["conteo_base"]["Bajo"]),
        ("Segmento Medio (base)", ri["segmentos_en_base"]["Medio"], parametros["segmentos"]["conteo_base"]["Medio"]),
        ("Segmento Alto (base)", ri["segmentos_en_base"]["Alto"], parametros["segmentos"]["conteo_base"]["Alto"]),
        ("monto_minmax mínimo en la base", 0.0, float(mm[base].min())),
        ("monto_minmax máximo en la base", 1.0, float(mm[base].max())),
        ("monto_minmax fuera de [0,1]", 0, int((~mm.between(0, 1)).sum())),
        ("Duplicados marcados (física)", fis_ref["duplicados_exactos"], int(fis_t["es_duplicado"].sum())),
        ("Cantidad <= 0 conservada (física)", fis_ref["cantidad_menor_igual_0"],
         int((pd.to_numeric(fis_t["cantidad"]) <= 0).sum())),
        ("USD: dif. máx. vs catálogo (centavos, ±0.01)", ri.get("usd_diferencia_max", 0.095),
         resumen_usd["dif_max_catalogo"]),
    ]
    tolerancias = {"USD: dif. máx. vs catálogo (centavos, ±0.01)": 0.01}
    filas = []
    for nombre, esperado, obtenido in pruebas:
        tol = tolerancias.get(nombre)
        ok = abs(float(obtenido) - float(esperado)) <= tol if tol else esperado == obtenido
        filas.append({"metrica": nombre, "referencia": esperado, "obtenido": obtenido, "coincide": bool(ok)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA / "07_comparacion_referencia.csv", index=False, encoding="utf-8")
    print(tabla.to_string(index=False))
    print(f"\nCoinciden: {int(tabla['coincide'].sum())} / {len(tabla)}")

    titulo("8. Entrega para Nono")
    columnas_entrega = list(df_t.columns)
    contrato = (COLUMNAS_HOMOLOGADAS + ["es_duplicado", "es_id_conflicto", "cantidad_origen", "monto_total_origen"]
                + COLUMNAS_AGREGA_FECHAS + COLUMNAS_AGREGA_IMPORTES_MXN + COLUMNAS_AGREGA_CATALOGO
                + COLUMNAS_AGREGA_OUTLIERS + COLUMNAS_AGREGA_TRANSFORMACION)
    faltan = [c for c in contrato if c not in columnas_entrega]
    print("Columnas del contrato ausentes:", faltan or "ninguna", "· filas:", len(df_t), "· columnas:", len(df_t.columns))
    a_texto_json(df_t).to_csv(SALIDA / "10_salida_etapa_yerik.csv", index=False, encoding="utf-8")
    guardar_json({"columnas": columnas_entrega, "filas": len(df_t)}, "10_columnas_entrega.json")
    if faltan:
        return 1

    titulo("9. Gráficas")
    # 9.1 histograma de monto_minmax con los cortes de los terciles
    c1, c2 = parametros["segmentos"]["corte_bajo_medio"], parametros["segmentos"]["corte_medio_alto"]
    mn, mx = parametros["minmax"]["min"], parametros["minmax"]["max"]
    x1, x2 = (c1 - mn) / (mx - mn), (c2 - mn) / (mx - mn)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(mm[base], bins=40, color=COLOR_PRINCIPAL, edgecolor="white")
    for x, et in ((x1, f"Bajo/Medio\n${c1:,.2f}"), (x2, f"Medio/Alto\n${c2:,.2f}")):
        ax.axvline(x, color=COLOR_ALERTA, linestyle="--")
        ax.text(x + 0.01, ax.get_ylim()[1] * 0.85, et, color=COLOR_ALERTA, fontsize=9)
    ax.set(title="Importe normalizado (Min-Max) y cortes de los segmentos · base estadística",
           xlabel="monto_minmax = (x − 332.67) / (12 032.68 − 332.67)", ylabel="Registros")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    g1 = SALIDA / "graficas" / "hist_monto_minmax.png"
    fig.savefig(g1, dpi=150)
    plt.close(fig)

    # 9.2 fechas físicas: parseo mixto (incorrecto) vs explícito
    fig, ax = plt.subplots(figsize=(8, 4.5))
    mes_mixto = pd.to_datetime(mixto).dt.to_period("M").value_counts().sort_index()
    mes_expl = pd.to_datetime(fis["fecha_venta"]).dt.to_period("M").value_counts().sort_index()
    meses = sorted(set(mes_mixto.index) | set(mes_expl.index))
    pos = np.arange(len(meses))
    ax.bar(pos - 0.2, [mes_expl.get(m, 0) for m in meses], 0.4, label="Explícito por patrón (correcto)", color=COLOR_PRINCIPAL)
    ax.bar(pos + 0.2, [mes_mixto.get(m, 0) for m in meses], 0.4, label="Genérico dayfirst (incorrecto)", color=COLOR_ALERTA)
    ax.set_xticks(pos, [str(m) for m in meses], rotation=45)
    ax.set(title="Ventas físicas por mes según el método de parseo", ylabel="Registros")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    g2 = SALIDA / "graficas" / "fechas_mixed_vs_explicito.png"
    fig.savefig(g2, dpi=150)
    plt.close(fig)

    # 9.3 USD convertido vs precio de catálogo
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(usd_cat["precio_catalogo_mxn"], usd_cat["precio_unitario_mxn"], s=14, color=COLOR_PRINCIPAL, alpha=0.7)
    lim = [0, float(usd_cat["precio_catalogo_mxn"].max()) * 1.05]
    ax.plot(lim, lim, color=COLOR_GRIS, linestyle="--", linewidth=1)
    ax.set(title=f"USD × 19.50 vs catálogo (n={len(usd_cat)}, dif. máx. ${resumen_usd['dif_max_catalogo']:.2f})",
           xlabel="Precio de catálogo (MXN)", ylabel="precio_unitario_mxn", xlim=lim, ylim=lim)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    g3 = SALIDA / "graficas" / "usd_vs_catalogo.png"
    fig.savefig(g3, dpi=150)
    plt.close(fig)

    # 9.4 registros por segmento (base vs fuera de la base)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar(seg.index, seg["base"], color=COLOR_PRINCIPAL, label="Base estadística (define los cortes)")
    ax.bar(seg.index, seg["fuera_de_base"], bottom=seg["base"], color=COLOR_GRIS, label="Fuera de la base (cuarentena probable)")
    ax.set(title="Registros por segmento de importe", ylabel="Registros")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    g4 = SALIDA / "graficas" / "segmentos_importe.png"
    fig.savefig(g4, dpi=150)
    plt.close(fig)
    print(g1, g2, g3, g4, sep="\n")

    import scipy  # noqa: F401
    guardar_json({"inicio": inicio.isoformat(timespec="seconds"),
                  "duracion_s": round((datetime.now() - inicio).total_seconds(), 2),
                  "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                  "zona_horaria_epoch": str(ZONA_NEGOCIO), "integridad_originales": integridad,
                  "coincidencias_referencia": f"{int(tabla['coincide'].sum())}/{len(tabla)}"}, "00_ejecucion.json")
    print("\nEvidencias en:", SALIDA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
