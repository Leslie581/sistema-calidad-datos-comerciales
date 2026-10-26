"""
Diagnóstico inicial de calidad (Fase 1) — Sistema de Integración y Calidad de Datos Comerciales
Ingeniería de Datos (ATD-2602) · Unidad 2 · TecNM Campus Colima

Lee los TRES archivos originales SIN modificarlos y calcula:
  filas/columnas, tipos, % de nulos, duplicados, formatos de fecha, valores categóricos
  sin homologar, cantidades inválidas, importes inconsistentes o sospechosos, llaves
  huérfanas, correos malformados, IQR (factor 1.5) y pruebas de independencia de faltantes.

Uso:
    python diagnostico/diagnostico_inicial.py                # desde la raíz del proyecto
    python diagnostico/diagnostico_inicial.py --datos ruta/a/carpeta

Salidas:
    diagnostico/resultados_diagnostico.json   (todas las cifras, para citar en reportes)
    salida en consola (para capturas de pantalla)

Requisitos: pandas, numpy (scipy es opcional: solo para la prueba chi-cuadrada).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

try:
    from scipy.stats import chi2_contingency
except ImportError:  # scipy es opcional
    chi2_contingency = None

PARIDAD_USD_MXN = 19.50          # Paridad oficial fijada por el profesor
FACTOR_IQR = 1.5                 # Factor fijado por el profesor
RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")

FORMATOS_FECHA = {
    "ISO (YYYY-MM-DD)": (r"^\d{4}-\d{2}-\d{2}$", "%Y-%m-%d"),
    "DD/MM/YYYY": (r"^\d{2}/\d{2}/\d{4}$", "%d/%m/%Y"),
    "DD-MM-YYYY": (r"^\d{2}-\d{2}-\d{4}$", "%d-%m-%Y"),
    "ISO con hora (YYYY-MM-DDTHH:MM:SS)": (r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", "%Y-%m-%dT%H:%M:%S"),
    "Unix epoch (segundos)": (r"^\d{9,11}$", None),
}


# ----------------------------------------------------------------------------- utilidades
def redondear(valor: float) -> float:
    """Redondeo financiero a 2 decimales con ROUND_HALF_UP (regla R6.4)."""
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def titulo(texto: str) -> None:
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def a_python(obj):
    """Convierte tipos numpy/pandas a tipos nativos para guardar en JSON."""
    if isinstance(obj, dict):
        return {str(k): a_python(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [a_python(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else round(float(obj), 4)
    if isinstance(obj, float):
        return None if np.isnan(obj) else round(obj, 4)
    return obj


def es_vacio(serie: pd.Series) -> pd.Series:
    """Nulo real o texto vacío / solo espacios."""
    return serie.isna() | serie.astype(str).str.strip().isin(["", "nan", "None"])


def perfil_basico(df_texto: pd.DataFrame, df_tipado: pd.DataFrame) -> dict:
    """Completitud, unicidad y tipos (Fase 1 de la guía)."""
    n = len(df_texto)
    nulos = {c: int(es_vacio(df_texto[c]).sum()) for c in df_texto.columns}
    return {
        "filas": n,
        "columnas": df_texto.shape[1],
        "nombres_columnas": list(df_texto.columns),
        "dtypes_inferidos": {c: str(t) for c, t in df_tipado.dtypes.items()},
        "nulos": nulos,
        "pct_nulos": {c: round(v / n * 100, 2) for c, v in nulos.items()},
        "completitud_global_pct": round((1 - sum(nulos.values()) / (n * df_texto.shape[1])) * 100, 2),
        "duplicados_exactos": int(df_texto.duplicated().sum()),
    }


def clasificar_fechas(serie: pd.Series) -> pd.Series:
    def _f(v):
        if pd.isna(v):
            return "NULO"
        s = str(v).strip()
        for nombre, (patron, _) in FORMATOS_FECHA.items():
            if re.match(patron, s):
                return nombre
        return "NO_RECONOCIDO"
    return serie.map(_f)


def parsear_fecha(v) -> pd.Timestamp:
    """Parseo explícito por formato (NUNCA format='mixed', ver advertencia en el reporte)."""
    s = str(v).strip()
    for nombre, (patron, fmt) in FORMATOS_FECHA.items():
        if re.match(patron, s):
            if fmt is None:
                return pd.to_datetime(int(s), unit="s", utc=True)
            return pd.to_datetime(s, format=fmt)
    return pd.NaT


def iqr(serie: pd.Series) -> dict:
    s = pd.to_numeric(serie, errors="coerce").dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    rango = q3 - q1
    li, ls = q1 - FACTOR_IQR * rango, q3 + FACTOR_IQR * rango
    return {
        "n": int(len(s)), "Q1": q1, "Q3": q3, "IQR": rango,
        "limite_inferior": li, "limite_superior": ls,
        "outliers_inferiores": int((s < li).sum()), "outliers_superiores": int((s > ls).sum()),
        "media": s.mean(), "mediana": s.median(), "desv_std": s.std(), "min": s.min(), "max": s.max(),
        "asimetria": s.skew(),
    }


def chi2_faltantes(df: pd.DataFrame, col_faltante: str, col_grupo: str) -> dict:
    """¿La ausencia en col_faltante depende de col_grupo? (apoyo para MCAR vs MAR)."""
    tabla = pd.crosstab(df[col_grupo], es_vacio(df[col_faltante]))
    pct = (es_vacio(df[col_faltante]).groupby(df[col_grupo]).mean() * 100).round(1).to_dict()
    res = {"pct_faltante_por_grupo": pct}
    if chi2_contingency is not None and tabla.shape[1] == 2:
        chi2, p, gl, _ = chi2_contingency(tabla)
        res.update({"chi2": chi2, "gl": int(gl), "p_valor": p,
                    "conclusion": "sin dependencia (p>=0.05) -> compatible con MCAR" if p >= 0.05
                    else "dependencia significativa (p<0.05) -> indicio de MAR"})
    return res


# ----------------------------------------------------------------------------- diagnóstico
def diagnosticar(carpeta: Path) -> dict:
    r_cat = carpeta / "catalogo_productos.csv"
    r_pos = carpeta / "ventas_tienda_fisica.csv"
    r_web = carpeta / "ventas_online.json"
    R: dict = {"archivos": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)}
                            for p in (r_cat, r_pos, r_web)}}

    # Dos lecturas por archivo: como texto (para ver el dato crudo) y con tipos inferidos.
    cat_txt = pd.read_csv(r_cat, dtype=str, keep_default_na=False)
    cat = pd.read_csv(r_cat)
    pos_txt = pd.read_csv(r_pos, dtype=str, keep_default_na=False)
    pos = pd.read_csv(r_pos)
    web_raw = json.loads(r_web.read_text(encoding="utf-8"))
    web = pd.DataFrame(web_raw)
    web_txt = web.astype(object).where(web.notna(), None).astype(str).replace("None", "")
    ids_catalogo = set(cat["id_producto"])

    # ------------------------------------------------------------------ CATÁLOGO
    titulo("1. CATÁLOGO MAESTRO — catalogo_productos.csv")
    R["catalogo"] = perfil_basico(cat_txt, cat)
    R["catalogo"].update({
        "id_producto_duplicados": int(cat["id_producto"].duplicated().sum()),
        "rango_ids": [cat["id_producto"].min(), cat["id_producto"].max()],
        "productos_por_categoria": cat["categoria"].value_counts().to_dict(),
        "productos_por_proveedor": cat["proveedor"].value_counts().to_dict(),
        "precio_base_mxn": iqr(cat["precio_base_mxn"]),
    })
    print(json.dumps(a_python(R["catalogo"]), ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ TIENDA FÍSICA
    titulo("2. TIENDA FÍSICA — ventas_tienda_fisica.csv")
    P = perfil_basico(pos_txt, pos)
    dup_mask = pos_txt.duplicated(keep="first")
    P["duplicados_exactos_tickets"] = pos_txt.loc[dup_mask, "id_ticket"].tolist()
    P["id_ticket_repetidos"] = int(pos_txt["id_ticket"].duplicated().sum())
    P["id_ticket_repetidos_con_contenido_distinto"] = int(
        pos_txt.drop_duplicates()["id_ticket"].duplicated().sum())

    fmt = clasificar_fechas(pos_txt["fecha_venta"])
    P["formatos_fecha"] = fmt.value_counts().to_dict()
    barras = pos_txt.loc[fmt == "DD/MM/YYYY", "fecha_venta"].str.split("/").str[0].astype(int)
    guiones = pos_txt.loc[fmt == "DD-MM-YYYY", "fecha_venta"].str.split("-").str[0].astype(int)
    P["evidencia_dia_primero"] = {
        "DD/MM/YYYY_con_primer_campo_mayor_12": int((barras > 12).sum()),
        "DD-MM-YYYY_con_primer_campo_mayor_12": int((guiones > 12).sum()),
    }
    fechas = pos_txt["fecha_venta"].map(parsear_fecha)
    P["rango_fechas_parseo_explicito"] = [str(fechas.min().date()), str(fechas.max().date())]
    P["fechas_no_parseables"] = int(fechas.isna().sum())
    erroneas = pd.to_datetime(pos_txt["fecha_venta"].str.replace("/", "-"), format="mixed", dayfirst=True)
    P["advertencia_parseo_mixed_dayfirst"] = {
        "fechas_que_cambian": int((erroneas.dt.date != fechas.dt.date).sum()),
        "rango_resultante_erroneo": [str(erroneas.min().date()), str(erroneas.max().date())],
    }

    P["sucursal"] = pos["sucursal"].value_counts().to_dict()
    P["metodo_pago_crudo"] = pos["metodo_pago"].value_counts().to_dict()
    P["metodo_pago_homologado"] = pos["metodo_pago"].str.strip().str.upper().value_counts().to_dict()

    cant = pd.to_numeric(pos["cantidad"], errors="coerce")
    precio = pd.to_numeric(pos["precio_unitario"], errors="coerce")
    monto = pd.to_numeric(pos["monto_total_mxn"], errors="coerce")
    P["cantidad_distribucion"] = cant.value_counts().sort_index().to_dict()
    P["cantidad_menor_igual_0"] = int((cant <= 0).sum())
    P["cantidad_menor_0"] = int((cant < 0).sum())
    P["cantidad_igual_0"] = int((cant == 0).sum())
    P["tickets_cantidad_invalida"] = pos.loc[cant <= 0, "id_ticket"].tolist()
    P["cantidad_99_o_mas"] = int((cant >= 99).sum())
    P["tickets_cantidad_99_o_mas"] = pos.loc[cant >= 99, ["id_ticket", "cantidad", "monto_total_mxn"]] \
        .to_dict(orient="records")
    P["monto_nulo"] = int(monto.isna().sum())
    P["monto_nulo_recalculable"] = int((monto.isna() & cant.notna() & precio.notna()).sum())
    P["monto_inconsistente_vs_cantidad_x_precio"] = int(((monto - cant * precio).abs() > 0.01).sum())
    P["monto_negativo"] = int((monto < 0).sum())
    m_cat = pos.merge(cat[["id_producto", "precio_base_mxn"]], on="id_producto", how="left")
    P["precio_distinto_al_catalogo"] = int(((m_cat["precio_unitario"] - m_cat["precio_base_mxn"]).abs() > 0.01).sum())

    huerf = ~pos["id_producto"].isin(ids_catalogo)
    P["huerfanos"] = int(huerf.sum())
    P["huerfanos_ids"] = pos.loc[huerf, "id_producto"].value_counts().to_dict()
    P["huerfanos_tickets"] = pos.loc[huerf, "id_ticket"].tolist()

    P["id_cliente_nulo"] = int(pos["id_cliente"].isna().sum())
    P["clientes_distintos"] = int(pos["id_cliente"].nunique())
    P["faltantes_id_cliente_vs_sucursal"] = chi2_faltantes(pos, "id_cliente", "sucursal")
    P["faltantes_id_cliente_vs_metodo_pago"] = chi2_faltantes(pos.assign(
        metodo_pago=pos["metodo_pago"].str.upper()), "id_cliente", "metodo_pago")
    P["faltantes_monto_vs_sucursal"] = chi2_faltantes(pos, "monto_total_mxn", "sucursal")
    P["faltantes_monto_vs_metodo_pago"] = chi2_faltantes(pos.assign(
        metodo_pago=pos["metodo_pago"].str.upper()), "monto_total_mxn", "metodo_pago")

    validas = cant > 0
    P["iqr_cantidad_crudo"] = iqr(cant)
    P["iqr_cantidad_sin_invalidas"] = iqr(cant[validas])
    P["iqr_monto_crudo"] = iqr(monto)
    P["iqr_precio_unitario"] = iqr(precio)
    R["tienda_fisica"] = P
    print(json.dumps(a_python(P), ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ ONLINE
    titulo("3. TIENDA ONLINE — ventas_online.json")
    W = perfil_basico(web_txt, web)
    W["tipos_python_en_json"] = {c: sorted({type(r.get(c)).__name__ for r in web_raw}) for c in web.columns}
    W["order_id_repetidos"] = int(web["order_id"].duplicated().sum())
    W["duplicados_sin_order_id"] = int(web.drop(columns="order_id").astype(str).duplicated().sum())
    W["email_vacio_cadena"] = int((web["customer_email"].fillna("x").str.strip() == "").sum())
    W["email_nulo_json"] = int(web["customer_email"].isna().sum())

    fmt_w = clasificar_fechas(web["order_timestamp"].astype(str))
    W["formatos_fecha"] = fmt_w.value_counts().to_dict()
    epoch = pd.to_numeric(web["order_timestamp"].where(fmt_w == "Unix epoch (segundos)"), errors="coerce").dropna()
    ep_utc = pd.to_datetime(epoch.astype("int64"), unit="s", utc=True)
    ep_mx = ep_utc.dt.tz_convert("America/Mexico_City")
    W["epoch_rango_utc"] = [str(ep_utc.min()), str(ep_utc.max())]
    W["epoch_fecha_distinta_utc_vs_mexico"] = int((ep_utc.dt.date != ep_mx.dt.date).sum())
    iso = pd.to_datetime(web["order_timestamp"].where(fmt_w.str.startswith("ISO con hora")),
                         format="%Y-%m-%dT%H:%M:%S", errors="coerce").dropna()
    W["iso_rango"] = [str(iso.min()), str(iso.max())]
    W["tipo_python_order_timestamp"] = {k: int(v) for k, v in
                                        pd.Series([type(r["order_timestamp"]).__name__ for r in web_raw]).value_counts().items()}

    W["currency"] = web["currency"].value_counts(dropna=False).to_dict()
    W["order_status_crudo"] = web["order_status"].value_counts().to_dict()
    W["order_status_homologado"] = web["order_status"].str.strip().str.upper().value_counts().to_dict()
    W["payment_gateway"] = web["payment_gateway"].value_counts().to_dict()
    W["units_distribucion"] = web["units"].value_counts().sort_index().to_dict()
    W["units_menor_igual_0"] = int((web["units"] <= 0).sum())

    u, p, t = web["units"], web["unit_price"], web["total_amount"]
    ratio = (t / (u * p)).round(2)
    W["total_inconsistente_vs_units_x_price"] = int(((t - u * p).abs() > 0.01).sum())
    W["ratio_total_entre_units_x_price"] = ratio.value_counts().to_dict()
    sosp = web.loc[(t - u * p).abs() > 0.01,
                   ["order_id", "product_id", "units", "currency", "unit_price", "total_amount", "customer_email"]]
    W["registros_total_inflado"] = sosp.to_dict(orient="records")
    W["registros_total_inflado_huerfanos"] = int((~sosp["product_id"].isin(ids_catalogo)).sum())

    w_cat = web.merge(cat[["id_producto", "precio_base_mxn"]], left_on="product_id", right_on="id_producto", how="left")
    precio_mxn = np.where(w_cat["currency"] == "USD", w_cat["unit_price"] * PARIDAD_USD_MXN, w_cat["unit_price"])
    en_cat = w_cat["precio_base_mxn"].notna()
    dif = np.abs(precio_mxn - w_cat["precio_base_mxn"])
    W["precio_vs_catalogo"] = {
        "registros_con_producto_en_catalogo": int(en_cat.sum()),
        "MXN_coinciden": int(((w_cat["currency"] == "MXN") & en_cat & (dif <= 0.01)).sum()),
        "USD_x_19.50_coinciden_tolerancia_0.50": int(((w_cat["currency"] == "USD") & en_cat & (dif <= 0.5)).sum()),
        "USD_diferencia_maxima_mxn": float(np.nanmax(np.where((w_cat["currency"] == "USD") & en_cat, dif, np.nan))),
        "no_coinciden": int((en_cat & (dif > 0.5)).sum()),
    }

    huerf_w = ~web["product_id"].isin(ids_catalogo)
    W["huerfanos"] = int(huerf_w.sum())
    W["huerfanos_ids"] = web.loc[huerf_w, "product_id"].value_counts().to_dict()

    em = web["customer_email"]
    vacio = es_vacio(em)
    malo = ~vacio & ~em.fillna("").str.match(RE_EMAIL)
    W["email_faltante_total"] = int(vacio.sum())
    W["email_malformado"] = int(malo.sum())
    W["email_malformado_valores"] = em[malo].value_counts().to_dict()
    W["shipping_address_nulo"] = int(web["shipping_address"].isna().sum())
    W["faltantes_shipping_vs_status"] = chi2_faltantes(web.assign(
        order_status=web["order_status"].str.upper()), "shipping_address", "order_status")
    W["faltantes_shipping_vs_gateway"] = chi2_faltantes(web, "shipping_address", "payment_gateway")
    W["faltantes_email_vs_gateway"] = chi2_faltantes(web, "customer_email", "payment_gateway")
    W["faltantes_email_vs_currency"] = chi2_faltantes(web, "customer_email", "currency")

    W["iqr_units"] = iqr(u)
    W["iqr_total_amount_crudo_mezcla_monedas"] = iqr(t)
    total_mxn_crudo = np.where(web["currency"] == "USD", t * PARIDAD_USD_MXN, t)
    W["iqr_total_crudo_convertido_mxn"] = iqr(pd.Series(total_mxn_crudo))
    R["tienda_online"] = W
    print(json.dumps(a_python(W), ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ VISTA INTEGRADA (referencia)
    titulo("4. VISTA DE REFERENCIA — reglas propuestas aplicadas sólo para estimar umbrales")
    # Esto NO es el pipeline: sólo estima qué umbrales y conteos debería reproducir el sistema real.
    pos_u = pos_txt.drop_duplicates().copy()
    pos_u = pos_u.assign(
        cantidad=pd.to_numeric(pos_u["cantidad"]), precio=pd.to_numeric(pos_u["precio_unitario"]),
        origen="FISICA", id_producto=pos_u["id_producto"])
    web_u = web.assign(cantidad=web["units"],
                       precio=[redondear(p * PARIDAD_USD_MXN) if m == "USD" else p
                               for p, m in zip(web["unit_price"], web["currency"])],
                       origen="ONLINE", id_producto=web["product_id"])
    comunes = ["origen", "id_producto", "cantidad", "precio"]
    uni = pd.concat([pos_u[comunes], web_u[comunes]], ignore_index=True)
    # Base estadística = registros sin defecto estructural (ni duplicado, ni cantidad <= 0, ni huérfano)
    uni = uni[(uni["cantidad"] > 0) & uni["id_producto"].isin(ids_catalogo)].copy()
    ref = {"filas_base_estadistica_sin_duplicados_invalidos_ni_huerfanos": len(uni),
           "base_por_origen": uni["origen"].value_counts().to_dict()}
    ic_pos = iqr(uni.loc[uni["origen"] == "FISICA", "cantidad"])
    ref["iqr_cantidad_fisica"] = ic_pos
    tope = int(np.floor(ic_pos["limite_superior"]))
    ref["tope_entero_cantidad_fisica"] = tope
    ref["cantidades_fisica_a_recortar"] = int((uni.loc[uni["origen"] == "FISICA", "cantidad"] > tope).sum())
    uni["cantidad_cap"] = np.where(uni["origen"] == "FISICA", uni["cantidad"].clip(upper=tope), uni["cantidad"])
    uni["monto_recalculado_mxn"] = [redondear(c * p) for c, p in zip(uni["cantidad_cap"], uni["precio"])]
    im = iqr(uni["monto_recalculado_mxn"])
    ref["iqr_monto_unificado_mxn"] = im
    monto_cap = uni["monto_recalculado_mxn"].clip(lower=max(im["limite_inferior"], 0), upper=im["limite_superior"])
    ref["montos_a_recortar"] = int((uni["monto_recalculado_mxn"] > im["limite_superior"]).sum())
    ref["monto_cap_min_max"] = [monto_cap.min(), monto_cap.max()]
    terciles = monto_cap.quantile([1 / 3, 2 / 3])
    ref["terciles_monto_cap"] = {"P33.3": terciles.iloc[0], "P66.7": terciles.iloc[1]}
    seg = pd.cut(monto_cap, [-np.inf, terciles.iloc[0], terciles.iloc[1], np.inf], labels=["Bajo", "Medio", "Alto"])
    ref["segmentos_en_base"] = seg.value_counts().to_dict()
    usd = web[web["currency"] == "USD"]
    a = [redondear(u * redondear(p * PARIDAD_USD_MXN)) for u, p in zip(usd["units"], usd["unit_price"])]
    b = [redondear(u * p * PARIDAD_USD_MXN) for u, p in zip(usd["units"], usd["unit_price"])]
    ref["usd_diferencia_centavos_entre_metodos"] = int(sum(abs(x - y) > 0.001 for x, y in zip(a, b)))
    R["referencia_integrada"] = ref
    print(json.dumps(a_python(ref), ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ CUARENTENA ESPERADA
    titulo("5. CUARENTENA ESPERADA POR REGLA (con traslapes)")
    q_pos = pd.DataFrame({
        "DUPLICADO_EXACTO": dup_mask,
        # Pydantic acumula todos los errores de un registro, por eso no se excluyen entre sí
        "CANTIDAD_INVALIDA": cant <= 0,
        "PRODUCTO_HUERFANO": huerf,
    })
    q_web = pd.DataFrame({
        "CANTIDAD_INVALIDA": web["units"] <= 0,
        "PRODUCTO_HUERFANO": huerf_w,
        "EMAIL_MALFORMADO": malo,
    })
    cq = {
        "tienda_fisica_por_regla": q_pos.sum().to_dict(),
        "tienda_fisica_registros_unicos_en_cuarentena": int(q_pos.any(axis=1).sum()),
        "tienda_fisica_con_mas_de_un_motivo": int((q_pos.sum(axis=1) > 1).sum()),
        "online_por_regla": q_web.sum().to_dict(),
        "online_registros_unicos_en_cuarentena": int(q_web.any(axis=1).sum()),
        "online_con_mas_de_un_motivo": int((q_web.sum(axis=1) > 1).sum()),
    }
    cq["total_cuarentena_esperado"] = cq["tienda_fisica_registros_unicos_en_cuarentena"] + cq["online_registros_unicos_en_cuarentena"]
    cq["total_transacciones_limpias_esperado"] = len(pos_txt) + len(web) - cq["total_cuarentena_esperado"]
    R["cuarentena_esperada"] = cq
    print(json.dumps(a_python(cq), ensure_ascii=False, indent=2))
    return a_python(R)


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", type=Path, default=raiz / "datos" / "crudos")
    ap.add_argument("--salida", type=Path, default=raiz / "diagnostico" / "resultados_diagnostico.json")
    args = ap.parse_args()
    resultados = diagnosticar(args.datos)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados guardados en: {args.salida}")
