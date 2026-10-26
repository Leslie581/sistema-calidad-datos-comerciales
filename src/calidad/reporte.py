"""
Reporte comparativo de calidad (responsable: Leslie).

- tabla_antes_despues(): métricas sobre el dato crudo homologado vs. la salida de F2+F3.
- comparar_con_referencia(): contrasta los resultados reales con diagnostico/resultados_diagnostico.json
  y explica cada diferencia.
- graficar_boxplots(): figuras antes/después para el reporte PDF.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import TOLERANCIA_MONTO
from .perfilado import es_vacio

COLOR_ANTES = "#eb6834"    # paleta categórica validada (skill dataviz): slot 2
COLOR_DESPUES = "#2a78d6"  # slot 1


def _n(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 4)


def tabla_antes_despues(df_antes: pd.DataFrame, df_despues: pd.DataFrame) -> pd.DataFrame:
    """Métricas comparables. 'Antes' = homologado (valores crudos); 'Después' = salida de la etapa de Leslie.
    Los conteos son sobre las 1,220 filas salvo que la columna 'base' indique otra cosa."""
    a, d = df_antes, df_despues
    fis_a, fis_d = a["origen"] == "FISICA", d["origen"] == "FISICA"
    onl_a, onl_d = a["origen"] == "ONLINE", d["origen"] == "ONLINE"

    def inconsistentes(df, col_monto):
        c, p, m = df["cantidad"], df["precio_unitario"], df[col_monto]
        ok = c.notna() & p.notna() & m.notna() & (c > 0)
        return int(((m - c * p).abs() > TOLERANCIA_MONTO)[ok].sum())

    base = d["es_base_estadistica"]
    # Misma base en ambos lados: total CRUDO (convertido a MXN) vs monto_total_mxn_cap, solo base estadística
    monto_crudo_mxn = (d["monto_total_origen"] * d["tipo_cambio_aplicado"])[base]
    filas = [
        ("Filas", "todas", len(a), len(d), "No se elimina ninguna fila (R1.3)"),
        ("Duplicados exactos sin identificar", "todas", int(a["registro_original"].duplicated().sum()),
         int((d["registro_original"].duplicated() & ~d["es_duplicado"]).sum()),
         f"{int(d['es_duplicado'].sum())} marcados con es_duplicado → cuarentena en F6"),
        ("Montos nulos", "todas", int(a["monto_total"].isna().sum()), int(d["monto_total"].isna().sum()),
         "Recalculados cantidad × precio (R6.2)"),
        ("Montos ≠ cantidad × precio", "cantidad > 0", inconsistentes(a, "monto_total"),
         inconsistentes(d, "monto_total"), "Recalculados; original en monto_total_origen (R6.3)"),
        ("id_cliente faltante (física)", "física", int(es_vacio(a.loc[fis_a, "id_cliente"]).sum()),
         int(es_vacio(d.loc[fis_d, "id_cliente"]).sum()), "Etiqueta ANONIMO (R3.8)"),
        ("Correo faltante (online)", "online", int(es_vacio(a.loc[onl_a, "email_cliente"]).sum()),
         int(es_vacio(d.loc[onl_d, "email_cliente"]).sum()), "Etiqueta SIN_CORREO (R3.8)"),
        ("Dirección faltante (online)", "online", int(es_vacio(a.loc[onl_a, "direccion_envio"]).sum()),
         int(es_vacio(d.loc[onl_d, "direccion_envio"]).sum()), "Etiqueta SIN_DIRECCION (R3.8)"),
        ("Cantidades ≤ 0", "todas", int((a["cantidad"] <= 0).sum()), int((d["cantidad"] <= 0).sum()),
         "Se conservan marcadas: son imposibles, no atípicas; cuarentena en F6 (R4)"),
        ("Monedas en la columna de análisis", "todas", int(a["moneda"].nunique()),
         int(d["precio_unitario_mxn"].notna().any()), "monto_total_mxn y precio_unitario_mxn en MXN (R7)"),
        ("Cantidad máxima (física)", "física", _n(a.loc[fis_a, "cantidad"].max()),
         _n(d.loc[fis_d & (d["cantidad"] > 0), "cantidad_cap"].max()), "cantidad_cap; original en cantidad (R5.3)"),
        ("Cantidad máxima (online)", "online", _n(a.loc[onl_a, "cantidad"].max()),
         _n(d.loc[onl_d, "cantidad_cap"].max()), "Sin outliers en online"),
        ("Importe MXN · media", "base estadística (antes: total crudo × tc, sin nulos)",
         _n(monto_crudo_mxn.mean()), _n(d.loc[base, "monto_total_mxn_cap"].mean()), "monto_total_mxn_cap (R5.4)"),
        ("Importe MXN · n con valor", "ídem", int(monto_crudo_mxn.notna().sum()), int(d.loc[base, "monto_total_mxn_cap"].notna().sum()),
         "Los nulos recalculados ya cuentan después"),
        ("Importe MXN · mediana", "ídem", _n(monto_crudo_mxn.median()), _n(d.loc[base, "monto_total_mxn_cap"].median()), ""),
        ("Importe MXN · máximo", "ídem", _n(monto_crudo_mxn.max()), _n(d.loc[base, "monto_total_mxn_cap"].max()), "Tope = LS"),
        ("Importe MXN · asimetría", "ídem", _n(monto_crudo_mxn.skew()), _n(d.loc[base, "monto_total_mxn_cap"].skew()), ""),
        ("Importe MXN · desviación estándar", "ídem", _n(monto_crudo_mxn.std()), _n(d.loc[base, "monto_total_mxn_cap"].std()), ""),
    ]
    return pd.DataFrame(filas, columns=["metrica", "base", "antes", "despues", "como_se_logro"])


# ----------------------------------------------------------------------------- referencia
def _get(dic, ruta: str):
    for k in ruta.split("."):
        dic = dic[k]
    return dic


def comparar_con_referencia(resultados: dict, referencia: dict) -> pd.DataFrame:
    """resultados: dict plano {clave: valor} calculado por el pipeline real.
    Cada fila: métrica, referencia, obtenido, diferencia, coincide (según tolerancia), explicación."""
    R = resultados
    filas = [
        # (métrica, ruta en JSON de referencia, clave en resultados, tolerancia, explicación si difiere)
        ("Filas física", "tienda_fisica.filas", "fisica_filas", 0, ""),
        ("Completitud global física %", "tienda_fisica.completitud_global_pct", "fisica_completitud", 0, ""),
        ("Duplicados exactos física", "tienda_fisica.duplicados_exactos", "fisica_duplicados", 0, ""),
        ("Monto nulo física", "tienda_fisica.monto_nulo", "fisica_monto_nulo", 0, ""),
        ("id_cliente nulo física", "tienda_fisica.id_cliente_nulo", "fisica_id_cliente_nulo", 0, ""),
        ("Cantidades ≤ 0 física", "tienda_fisica.cantidad_menor_igual_0", "fisica_cantidad_invalida", 0, ""),
        ("Media monto física (crudo)", "tienda_fisica.iqr_monto_crudo.media", "fisica_monto_media", 0.01, ""),
        ("Mediana monto física (crudo)", "tienda_fisica.iqr_monto_crudo.mediana", "fisica_monto_mediana", 0.01, ""),
        ("Asimetría monto física (crudo)", "tienda_fisica.iqr_monto_crudo.asimetria", "fisica_monto_asimetria", 1e-3, ""),
        ("p χ² id_cliente vs sucursal", "tienda_fisica.faltantes_id_cliente_vs_sucursal.p_valor", "p_idcliente_sucursal", 1e-4, ""),
        ("p χ² id_cliente vs método pago", "tienda_fisica.faltantes_id_cliente_vs_metodo_pago.p_valor", "p_idcliente_metodo", 1e-4, ""),
        ("p χ² monto vs sucursal", "tienda_fisica.faltantes_monto_vs_sucursal.p_valor", "p_monto_sucursal", 1e-4, ""),
        ("p χ² monto vs método pago", "tienda_fisica.faltantes_monto_vs_metodo_pago.p_valor", "p_monto_metodo", 1e-4, ""),
        ("Completitud global online %", "tienda_online.completitud_global_pct", "online_completitud", 0, ""),
        ("Correo faltante online", "tienda_online.email_faltante_total", "online_email_faltante", 0, ""),
        ("Dirección nula online", "tienda_online.shipping_address_nulo", "online_direccion_nula", 0, ""),
        ("Totales inconsistentes online", "tienda_online.total_inconsistente_vs_units_x_price", "online_inconsistentes", 0, ""),
        ("p χ² dirección vs estado", "tienda_online.faltantes_shipping_vs_status.p_valor", "p_dir_estado", 1e-4, ""),
        ("p χ² dirección vs pasarela", "tienda_online.faltantes_shipping_vs_gateway.p_valor", "p_dir_pasarela", 1e-4, ""),
        ("p χ² correo vs pasarela", "tienda_online.faltantes_email_vs_gateway.p_valor", "p_email_pasarela", 1e-4, ""),
        ("p χ² correo vs moneda", "tienda_online.faltantes_email_vs_currency.p_valor", "p_email_moneda", 1e-4, ""),
        ("Huérfanos física", "tienda_fisica.huerfanos", "fisica_huerfanos", 0, ""),
        ("Huérfanos online", "tienda_online.huerfanos", "online_huerfanos", 0, ""),
        ("Diferencia máx. USD×19.50 vs catálogo", "tienda_online.precio_vs_catalogo.USD_diferencia_maxima_mxn",
         "usd_dif_max_catalogo", 0.001,
         "El diagnóstico comparó el precio SIN redondear (46.45 × 19.5 = 905.775); el pipeline redondea primero "
         "con ROUND_HALF_UP (R6.4) → 905.78, y frente a 905.68 del catálogo la diferencia queda en 0.10. "
         "Sigue dentro de la tolerancia de ±0.50 (R7.3)."),
        ("Base estadística (filas)", "referencia_integrada.filas_base_estadistica_sin_duplicados_invalidos_ni_huerfanos",
         "base_total", 0, ""),
        ("Base estadística física", "referencia_integrada.base_por_origen.FISICA", "base_fisica", 0, ""),
        ("Base estadística online", "referencia_integrada.base_por_origen.ONLINE", "base_online", 0, ""),
        ("Q1 cantidad física", "referencia_integrada.iqr_cantidad_fisica.Q1", "cant_q1", 0, ""),
        ("Q3 cantidad física", "referencia_integrada.iqr_cantidad_fisica.Q3", "cant_q3", 0, ""),
        ("LS cantidad física", "referencia_integrada.iqr_cantidad_fisica.limite_superior", "cant_ls", 0, ""),
        ("Tope entero cantidad física", "referencia_integrada.tope_entero_cantidad_fisica", "cant_tope", 0, ""),
        ("Cantidades recortadas física", "referencia_integrada.cantidades_fisica_a_recortar", "cant_recortadas", 0, ""),
        ("Q1 monto MXN", "referencia_integrada.iqr_monto_unificado_mxn.Q1", "monto_q1", 0.005, ""),
        ("Q3 monto MXN", "referencia_integrada.iqr_monto_unificado_mxn.Q3", "monto_q3", 0.005, ""),
        ("IQR monto MXN", "referencia_integrada.iqr_monto_unificado_mxn.IQR", "monto_iqr", 0.005, ""),
        ("LS monto MXN", "referencia_integrada.iqr_monto_unificado_mxn.limite_superior", "monto_ls", 0.005, ""),
        ("Mediana monto MXN (base)", "referencia_integrada.iqr_monto_unificado_mxn.mediana", "monto_mediana", 0.005, ""),
        ("Asimetría monto MXN antes del capping (base)", "referencia_integrada.iqr_monto_unificado_mxn.asimetria",
         "monto_asimetria", 1e-3, ""),
        ("Outliers de monto en la base", "referencia_integrada.iqr_monto_unificado_mxn.outliers_superiores",
         "monto_outliers_base", 0, ""),
        ("Montos recortados", "referencia_integrada.montos_a_recortar", "monto_recortados", 0,
         "El diagnóstico contó solo la base estadística (80). El pipeline aplica el recorte a TODA fila con "
         "cantidad > 0, y 2 duplicados exactos (filas 608 y 609 del CSV, copias de POS-2026-0257 y "
         "POS-2026-0457) superan el LS. Como irán a cuarentena por DUPLICADO_EXACTO, no afectan "
         "la tabla limpia. En la base, los recortes son 80, igual que la referencia."),
        ("Máximo monto con capping", "referencia_integrada.monto_cap_min_max.1", "monto_cap_max", 0.005, ""),
    ]
    salida = []
    for metrica, ruta, clave, tol, explicacion in filas:
        ref = _get(referencia, ruta) if not ruta.endswith(".1") else _get(referencia, ruta[:-2])[1]
        obt = R.get(clave)
        dif = None if ref is None or obt is None else round(float(obt) - float(ref), 6)
        coincide = dif is not None and abs(dif) <= tol + 1e-9
        salida.append({"metrica": metrica, "referencia": ref, "obtenido": obt, "diferencia": dif,
                       "tolerancia": tol, "coincide": coincide,
                       "explicacion": "" if coincide else (explicacion or "SIN EXPLICAR: revisar")})
    return pd.DataFrame(salida)


# ----------------------------------------------------------------------------- gráficas
def graficar_boxplots(antes: pd.Series, despues: pd.Series, titulo: str, eje_y: str, ruta: Path,
                      escala_log: bool = False, etiquetas=("Antes", "Después")) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.5, 4.6), dpi=150)
    datos = [pd.to_numeric(antes, errors="coerce").dropna(), pd.to_numeric(despues, errors="coerce").dropna()]
    bp = ax.boxplot(datos, widths=0.45, patch_artist=True, showfliers=True,
                    medianprops={"color": "#0b0b0b", "linewidth": 1.6},
                    flierprops={"marker": "o", "markersize": 4, "alpha": 0.55, "markeredgewidth": 0})
    for caja, color in zip(bp["boxes"], (COLOR_ANTES, COLOR_DESPUES)):
        caja.set(facecolor=color, alpha=0.35, edgecolor=color, linewidth=1.5)
    for flier, color in zip(bp["fliers"], (COLOR_ANTES, COLOR_DESPUES)):
        flier.set_markerfacecolor(color)
    ax.set_xticks([1, 2], [f"{etiquetas[0]}\n(n = {len(datos[0])})", f"{etiquetas[1]}\n(n = {len(datos[1])})"])
    if escala_log:
        ax.set_yscale("log")
    ax.set_ylabel(eje_y, color="#52514e")
    ax.set_title(titulo, loc="left", fontsize=11, color="#0b0b0b")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    for i, d in enumerate(datos, start=1):
        ax.annotate(f"mediana {d.median():,.2f}\nmáx {d.max():,.2f}", (i + 0.27, d.median()), fontsize=7.5,
                    color="#52514e", va="center")
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, facecolor="#fcfcfb")
    plt.close(fig)
    return ruta
