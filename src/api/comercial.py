"""
Pulso comercial: indicadores de ventas calculados en Python sobre la base SQLite (solo lectura).

IMPORTE COMERCIAL = `transacciones_limpias.monto_total_mxn`
    Es el importe de la transacción CONFORME después de las correcciones justificadas del ETL (monto recalculado como
    cantidad × precio) y de normalizar la moneda a MXN (USD × 19.50, ROUND_HALF_UP), pero ANTES del recorte estadístico.
    NO es `monto_total_mxn_cap` (con capping IQR, usado para escalar y segmentar) ni `monto_total_origen` (dato crudo,
    en la moneda original y posiblemente inconsistente). Las transacciones en cuarentena no están en esa tabla: no suman.
    Verificado: monto_total_mxn = ROUND(cantidad × precio_unitario_mxn, 2) en el 100 % de las filas conformes.

LO QUE ESTOS INDICADORES NO SON: ingresos contables auditados, utilidad, margen ni evidencia de rentabilidad. No hay costos
ni gastos en los datos.

PERÍODOS Y COMPARABILIDAD
    La «cobertura» de datos es el rango [primera fecha, última fecha] de las transacciones conformes. Un mes se evalúa dentro
    de esa cobertura (el último mes con datos suele ser parcial). La comparación por omisión es de INTERVALO EQUIVALENTE:
    mismos días del mes anterior. Una comparación es «homogénea» solo si ambos períodos tienen el mismo número de días y
    ambos están completamente cubiertos por los datos. Si no lo es, no se clasifica tendencia.

CRITERIOS PROPIOS DE KOVA (no son estándares del profesor): ver `Criterios`; son configurables y se devuelven en cada respuesta.
"""
from __future__ import annotations

import calendar
import os
import re
from dataclasses import asdict, dataclass, fields
from datetime import date, timedelta
from typing import Literal, Optional

from .db import ErrorApi, escalar, fila, filas

CAMPO_IMPORTE = "monto_total_mxn"
ESTADOS_NO_EFECTIVOS = ("CANCELADO", "DEVUELTO")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = [m[:3] for m in MESES]
RE_MES = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
MAX_DIAS_RANGO = 366
Comparacion = Literal["equivalente", "mes_anterior_completo", "ninguna"]
Estados = Literal["todas", "efectivas"]
Canal = Literal["FISICA", "ONLINE"]


@dataclass(frozen=True)
class Criterios:
    """Umbrales PROPIOS de KOVA para redactar el diagnóstico. No son estándares oficiales. Configurables (ver `desde_entorno`)."""
    umbral_crecimiento_pct: float = 5.0        # variación ≥ +5 % → «aumentaron»
    umbral_disminucion_pct: float = -5.0       # variación ≤ −5 % → «disminuyeron»; entre ambos → «estables»
    min_transacciones_periodo: int = 10        # con menos transacciones en alguno de los períodos la variación no es concluyente
    participacion_dominante_pct: float = 60.0  # un canal con ≥ 60 % del importe «concentra» las ventas
    brecha_canales_pp: float = 5.0             # diferencia mínima (puntos porcentuales) entre variaciones de canal para hablar de «mejor desempeño»
    atipicas_relevantes_pct: float = 20.0      # si las transacciones atípicas pesan ≥ 20 % del importe se advierte

    @classmethod
    def desde_entorno(cls) -> "Criterios":
        """KOVA_<NOMBRE_EN_MAYÚSCULAS> sobrescribe un umbral (p. ej. KOVA_UMBRAL_CRECIMIENTO_PCT=10)."""
        base = cls()
        cambios = {}
        for f in fields(cls):
            crudo = os.environ.get(f"KOVA_{f.name.upper()}")
            if crudo is not None:
                try:
                    cambios[f.name] = type(getattr(base, f.name))(crudo)
                except ValueError:
                    pass
        return cls(**{**asdict(base), **cambios})


# ----------------------------------------------------------------------------- fechas y formato
def _d(texto: str) -> date:
    return date.fromisoformat(texto)


def _fin_de_mes(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _mes_anterior(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def _etiqueta_mes(ym: str) -> str:
    return f"{MESES[int(ym[5:7]) - 1].capitalize()} {ym[:4]}"


def _rango(i: date, f: date) -> str:
    """«1–16 oct 2026» o «28 sep – 3 oct 2026»."""
    if i == f:
        return f"{i.day} {MESES_CORTOS[i.month - 1]} {i.year}"
    if i.year == f.year and i.month == f.month:
        return f"{i.day}–{f.day} {MESES_CORTOS[f.month - 1]} {f.year}"
    return f"{i.day} {MESES_CORTOS[i.month - 1]} {i.year} – {f.day} {MESES_CORTOS[f.month - 1]} {f.year}"


def _mxn(v: float) -> str:
    return f"${v:,.0f}"


def _pct(v: float) -> str:
    return f"{abs(v):.1f} %"


def variacion_pct(actual: Optional[float], anterior: Optional[float]) -> Optional[float]:
    """((actual − anterior) ÷ anterior) × 100. None si no hay comparación válida (sin anterior, o anterior = 0)."""
    if actual is None or anterior is None or anterior == 0:
        return None
    return round((actual - anterior) / anterior * 100, 2)


def _div(a: float, b: float) -> Optional[float]:
    return round(a / b, 2) if b else None


# ----------------------------------------------------------------------------- filtros SQL (siempre parametrizados)
def _filtro(canal: Optional[str], estados: str) -> tuple[str, list]:
    sql, params = "", []
    if canal:
        sql += " AND origen = ?"
        params.append(canal)
    if estados == "efectivas":
        sql += f" AND (estado_pedido IS NULL OR estado_pedido NOT IN ({', '.join('?' * len(ESTADOS_NO_EFECTIVOS))}))"
        params += list(ESTADOS_NO_EFECTIVOS)
    return sql, params


def cobertura_datos(conn) -> tuple[Optional[date], Optional[date]]:
    r = conn.execute("SELECT MIN(fecha_venta), MAX(fecha_venta) FROM transacciones_limpias").fetchone()
    return (_d(r[0]), _d(r[1])) if r[0] else (None, None)


# ----------------------------------------------------------------------------- períodos
def _periodo(inicio: date, fin: date, cob: tuple[Optional[date], Optional[date]], calendario: Optional[int] = None) -> dict:
    dias = (fin - inicio).days + 1
    if cob[0] is None:
        cubiertos = 0
    else:
        a, b = max(inicio, cob[0]), min(fin, cob[1])
        cubiertos = max(0, (b - a).days + 1)
    return {"inicio": inicio.isoformat(), "fin": fin.isoformat(), "dias": dias, "dias_cubiertos": cubiertos,
            "cobertura": round(cubiertos / dias, 4), "dias_calendario_mes": calendario,
            "parcial": cubiertos < dias or (calendario is not None and dias < calendario),
            "etiqueta": _rango(inicio, fin)}


def meses_disponibles(conn, canal: Optional[str] = None, estados: str = "todas") -> list[dict]:
    cob = cobertura_datos(conn)
    if cob[0] is None:
        return []
    filtro, p = _filtro(canal, estados)
    out = []
    for r in filas(conn, "SELECT substr(fecha_venta, 1, 7) AS mes, COUNT(*) AS n, COUNT(DISTINCT fecha_venta) AS dias_con_ventas, "
                         f"MIN(fecha_venta) AS primera, MAX(fecha_venta) AS ultima, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe "
                         f"FROM transacciones_limpias WHERE 1=1{filtro} GROUP BY mes ORDER BY mes", p):
        i = date(int(r["mes"][:4]), int(r["mes"][5:7]), 1)
        f = _fin_de_mes(i)
        per = _periodo(max(i, cob[0]), min(f, cob[1]), cob, calendario=f.day)
        out.append({"mes": r["mes"], "etiqueta": _etiqueta_mes(r["mes"]), "inicio_datos": per["inicio"], "fin_datos": per["fin"],
                    "dias_mes": f.day, "dias_cubiertos": per["dias_cubiertos"], "parcial": per["parcial"],
                    "transacciones": r["n"], "importe": round(r["importe"], 2), "dias_con_ventas": r["dias_con_ventas"],
                    "primera_venta": r["primera"], "ultima_venta": r["ultima"],
                    "promedio_diario": _div(r["importe"], per["dias_cubiertos"])})
    return out


def resolver_periodos(conn, mes: Optional[str], desde: Optional[str], hasta: Optional[str], comparacion: str) -> dict:
    """Devuelve {actual, anterior, modo, homogeneo, avisos}. Valida combinaciones; no inventa períodos fuera de la cobertura."""
    cob = cobertura_datos(conn)
    if cob[0] is None:
        raise ErrorApi("SIN_VENTAS", "La base no tiene transacciones conformes para analizar. Ejecuta el pipeline.", 404)
    if (desde or hasta) and mes:
        raise ErrorApi("PARAMETRO_INVALIDO", "Usa «mes» o un rango «desde/hasta», no ambos.", 422)
    if bool(desde) != bool(hasta):
        raise ErrorApi("PARAMETRO_INVALIDO", "Un rango personalizado necesita «desde» y «hasta».", 422)
    avisos: list[str] = []
    if desde and hasta:
        try:
            i, f = _d(desde), _d(hasta)
        except ValueError:
            raise ErrorApi("PARAMETRO_INVALIDO", "«desde» y «hasta» deben ser fechas YYYY-MM-DD válidas.", 422) from None
        if i > f:
            raise ErrorApi("PARAMETRO_INVALIDO", "«desde» no puede ser posterior a «hasta».", 422)
        if (f - i).days + 1 > MAX_DIAS_RANGO:
            raise ErrorApi("PARAMETRO_INVALIDO", f"El rango no puede exceder {MAX_DIAS_RANGO} días.", 422)
        if comparacion == "mes_anterior_completo":
            raise ErrorApi("PARAMETRO_INVALIDO", "«mes_anterior_completo» solo aplica al seleccionar un mes.", 422)
        actual = _periodo(i, f, cob)
        n = actual["dias"]
        anterior = None if comparacion == "ninguna" else _periodo(i - timedelta(days=n), i - timedelta(days=1), cob)
        modo = "personalizado"
    else:
        meses = meses_disponibles(conn)
        if mes is None:
            mes = meses[-1]["mes"]                          # último mes CON información, no el mes del sistema operativo
        elif not RE_MES.match(mes):
            raise ErrorApi("PARAMETRO_INVALIDO", "«mes» debe tener el formato YYYY-MM.", 422)
        if mes not in {m["mes"] for m in meses}:
            raise ErrorApi("MES_SIN_DATOS", f"No hay transacciones conformes en {_etiqueta_mes(mes)}.", 422)
        ini_mes = date(int(mes[:4]), int(mes[5:7]), 1)
        fin_mes = _fin_de_mes(ini_mes)
        ei, ef = max(ini_mes, cob[0]), min(fin_mes, cob[1])
        actual = _periodo(ei, ef, cob, calendario=fin_mes.day)
        prev_mes = _mes_anterior(ini_mes)
        prev_fin_mes = _fin_de_mes(prev_mes)
        if comparacion == "ninguna":
            anterior = None
        elif comparacion == "mes_anterior_completo":
            anterior = _periodo(prev_mes, prev_fin_mes, cob, calendario=prev_fin_mes.day)
        else:                                               # intervalo equivalente: mismos días del mes anterior
            pi = prev_mes + timedelta(days=ei.day - 1)
            pf = min(pi + timedelta(days=actual["dias"] - 1), prev_fin_mes)
            anterior = _periodo(pi, pf, cob, calendario=prev_fin_mes.day)
        modo = "mes"
    homogeneo = bool(anterior and anterior["dias"] == actual["dias"] and anterior["cobertura"] == 1 and actual["cobertura"] == 1)
    if actual["parcial"]:
        avisos.append("periodo_parcial")
    if anterior and not homogeneo:
        avisos.append("periodos_no_homogeneos")
    return {"actual": actual, "anterior": anterior, "modo": modo, "homogeneo": homogeneo, "avisos": avisos, "mes": mes if modo == "mes" else None,
            "cobertura_datos": {"inicio": cob[0].isoformat(), "fin": cob[1].isoformat()}}


# ----------------------------------------------------------------------------- indicadores
def kpis(conn, periodo: dict, canal: Optional[str], estados: str) -> dict:
    filtro, p = _filtro(canal, estados)
    r = fila(conn, f"SELECT COUNT(*) AS n, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe, COALESCE(SUM(cantidad), 0) AS unidades, "
                   "COUNT(DISTINCT fecha_venta) AS dias_con_ventas, MIN(fecha_venta) AS primera, MAX(fecha_venta) AS ultima "
                   f"FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro}", [periodo["inicio"], periodo["fin"], *p])
    n, imp = r["n"], round(r["importe"], 2)
    base_dias = periodo["dias_cubiertos"]
    return {"transacciones": n, "importe": imp, "unidades": r["unidades"], "ticket_promedio": _div(imp, n),
            "promedio_diario": _div(imp, base_dias), "dias_con_ventas": r["dias_con_ventas"],
            "primera_venta": r["primera"], "ultima_venta": r["ultima"]}


def canales_periodo(conn, periodo: dict, anterior: Optional[dict], estados: str) -> list[dict]:
    """Física y online SIEMPRE (ignora el filtro de canal): participación y variación de cada uno."""
    out = []
    ks = {c: kpis(conn, periodo, c, estados) for c in ("FISICA", "ONLINE")}
    total = sum(k["importe"] for k in ks.values())
    for c, k in ks.items():
        prev = kpis(conn, anterior, c, estados) if anterior and anterior["cobertura"] > 0 else None
        out.append({"canal": c, **k, "participacion_pct": round(k["importe"] / total * 100, 2) if total else None,
                    "importe_anterior": prev["importe"] if prev else None, "transacciones_anterior": prev["transacciones"] if prev else None,
                    "variacion_importe_pct": variacion_pct(k["importe"], prev["importe"]) if prev else None})
    return out


def atipicas(conn, periodo: dict, canal: Optional[str], estados: str) -> dict:
    filtro, p = _filtro(canal, estados)
    r = fila(conn, f"SELECT COUNT(*) AS n, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe FROM transacciones_limpias "
                   f"WHERE fecha_venta BETWEEN ? AND ? AND (es_outlier_cantidad = 1 OR es_outlier_monto = 1){filtro}",
             [periodo["inicio"], periodo["fin"], *p])
    total = escalar(conn, f"SELECT COALESCE(SUM({CAMPO_IMPORTE}), 0) FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro}",
                    [periodo["inicio"], periodo["fin"], *p])
    return {"transacciones": r["n"], "importe": round(r["importe"], 2), "participacion_pct": round(r["importe"] / total * 100, 2) if total else None}


def sin_atipicas(conn, periodo: dict, anterior: Optional[dict], canal: Optional[str], estados: str) -> Optional[dict]:
    """Importe del período excluyendo transacciones atípicas (es_outlier_*), y la variación resultante frente al anterior."""
    filtro, p = _filtro(canal, estados)

    def importe(per: dict) -> float:
        return round(escalar(conn, f"SELECT COALESCE(SUM({CAMPO_IMPORTE}), 0) FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ? "
                                   f"AND es_outlier_cantidad = 0 AND es_outlier_monto = 0{filtro}", [per["inicio"], per["fin"], *p]), 2)
    act = importe(periodo)
    ant = importe(anterior) if anterior and anterior["cobertura"] > 0 else None
    return {"actual": act, "anterior": ant, "variacion_pct": variacion_pct(act, ant)}


def no_efectivas(conn, periodo: dict, canal: Optional[str]) -> dict:
    filtro, p = _filtro(canal, "todas")
    r = fila(conn, f"SELECT COUNT(*) AS n, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ? "
                   f"AND estado_pedido IN (?, ?){filtro}", [periodo["inicio"], periodo["fin"], *ESTADOS_NO_EFECTIVOS, *p])
    return {"transacciones": r["n"], "importe": round(r["importe"], 2)}


# ----------------------------------------------------------------------------- diagnóstico «¿Cómo va mi negocio?»
def _msg(id_: str, tipo: str, texto: str, **evidencia) -> dict:
    return {"id": id_, "tipo": tipo, "texto": texto, "evidencia": evidencia}


def clasificar_tendencia(var: Optional[float], criterios: Criterios) -> Optional[str]:
    if var is None:
        return None
    if var >= criterios.umbral_crecimiento_pct:
        return "crecimiento"
    if var <= criterios.umbral_disminucion_pct:
        return "disminucion"
    return "estable"


def diagnostico(periodos: dict, actual: dict, anterior_kpi: Optional[dict], canales: list[dict], atip: dict, no_ef: dict,
                estados: str, canal: Optional[str], criterios: Criterios, sin_atip: Optional[dict] = None) -> dict:
    """Reglas cuantitativas y verificables. Cada mensaje trae las cifras de las que sale (`evidencia`)."""
    per, prev = periodos["actual"], periodos["anterior"]
    mensajes: list[dict] = []
    estado = "sin_datos"
    titular = "No hay transacciones conformes en el período seleccionado."
    nombre_ant = prev["etiqueta"] if prev else None

    if actual["transacciones"] == 0:
        mensajes.append(_msg("sin_datos", "info", f"No hay transacciones conformes entre el {per['inicio']} y el {per['fin']}."
                             + (f" Los datos disponibles van del {periodos['cobertura_datos']['inicio']} al {periodos['cobertura_datos']['fin']}." if per["cobertura"] < 1 else ""),
                             periodo=per["etiqueta"]))
    else:
        if per["parcial"]:
            cal = per.get("dias_calendario_mes")
            if per["dias_cubiertos"] < per["dias"]:
                txt = f"El rango es parcial: solo {per['dias_cubiertos']} de sus {per['dias']} días están cubiertos por los datos ({periodos['cobertura_datos']['inicio']} a {periodos['cobertura_datos']['fin']})."
            else:
                txt = f"El período es parcial: solo hay datos del {per['inicio']} al {per['fin']} ({per['dias']} de los {cal} días del mes)."
            mensajes.append(_msg("periodo_parcial", "aviso", txt, dias=per["dias"], dias_cubiertos=per["dias_cubiertos"], dias_calendario_mes=cal))
        # ---- tendencia
        var = variacion_pct(actual["importe"], anterior_kpi["importe"]) if anterior_kpi else None
        if prev is None:
            estado, titular = "sin_comparacion", "No hay información suficiente para evaluar una tendencia."
            mensajes.append(_msg("sin_comparacion", "info", "No se solicitó una comparación o no existe un período anterior: no hay información suficiente para evaluar una tendencia."))
        elif prev["cobertura"] == 0 or anterior_kpi is None:
            estado, titular = "sin_comparacion", "No hay información suficiente para evaluar una tendencia."
            mensajes.append(_msg("sin_comparacion", "info", f"El período anterior comparable ({nombre_ant}) queda fuera de los datos disponibles "
                                 f"({periodos['cobertura_datos']['inicio']} a {periodos['cobertura_datos']['fin']}): no se calcula variación.", anterior=nombre_ant))
        elif not periodos["homogeneo"]:
            estado, titular = "no_concluyente", "Los períodos no son homogéneos: no se clasifica una tendencia."
            pd_ = variacion_pct(actual["promedio_diario"], anterior_kpi["promedio_diario"])
            mensajes.append(_msg("no_homogeneo", "aviso", f"Se compara {per['etiqueta']} ({per['dias']} días) con {nombre_ant} ({prev['dias']} días, cobertura {prev['cobertura'] * 100:.0f} %): "
                                 "los períodos no son equivalentes, así que no se clasifica una tendencia."
                                 + (f" El promedio diario cambió {'+' if pd_ >= 0 else '−'}{_pct(pd_)} (de {_mxn(anterior_kpi['promedio_diario'])} a {_mxn(actual['promedio_diario'])} por día)." if pd_ is not None else ""),
                                 promedio_diario_variacion_pct=pd_))
        elif anterior_kpi["importe"] == 0:
            estado, titular = "sin_comparacion", "El período anterior no registró ventas: no se calcula variación."
            mensajes.append(_msg("anterior_sin_ventas", "info", f"El período anterior ({nombre_ant}) no registró ventas conformes; la variación porcentual no está definida (denominador cero).", anterior=nombre_ant))
        elif min(actual["transacciones"], anterior_kpi["transacciones"]) < criterios.min_transacciones_periodo:
            estado, titular = "no_concluyente", "Hay muy pocas transacciones para una conclusión fiable."
            mensajes.append(_msg("pocas_transacciones", "aviso", f"Un período tiene menos de {criterios.min_transacciones_periodo} transacciones "
                                 f"({actual['transacciones']} frente a {anterior_kpi['transacciones']}): la variación ({'+' if var >= 0 else '−'}{_pct(var)}) no es concluyente.",
                                 actuales=actual["transacciones"], anteriores=anterior_kpi["transacciones"], minimo=criterios.min_transacciones_periodo, variacion_pct=var))
        else:
            estado = clasificar_tendencia(var, criterios) or "sin_comparacion"
            signo = "+" if var >= 0 else "−"
            if estado == "estable":
                frase = f"Tus ventas se mantienen relativamente estables (variación de {signo}{_pct(var)}, dentro del margen de ±{criterios.umbral_crecimiento_pct:g} %)"
                titular = "Tus ventas se mantienen relativamente estables respecto al período anterior comparable."
            else:
                verbo = "aumentaron" if estado == "crecimiento" else "disminuyeron"
                frase = f"Tus ventas {verbo} {_pct(var)}"
                titular = f"{frase} respecto al período anterior comparable."
            mensajes.append(_msg("tendencia", "tendencia", f"{frase}: {_mxn(actual['importe'])} en {per['etiqueta']} frente a {_mxn(anterior_kpi['importe'])} "
                                 f"en {nombre_ant} (mismos {per['dias']} días).",
                                 actual=actual["importe"], anterior=anterior_kpi["importe"], variacion_pct=var,
                                 umbral_crecimiento_pct=criterios.umbral_crecimiento_pct, umbral_disminucion_pct=criterios.umbral_disminucion_pct))
            vt = variacion_pct(actual["ticket_promedio"], anterior_kpi["ticket_promedio"])
            vn = variacion_pct(actual["transacciones"], anterior_kpi["transacciones"])
            if vt is not None and vn is not None:
                mensajes.append(_msg("composicion", "info", f"El número de transacciones cambió {'+' if vn >= 0 else '−'}{_pct(vn)} ({anterior_kpi['transacciones']} → {actual['transacciones']}) y el ticket promedio "
                                     f"{'+' if vt >= 0 else '−'}{_pct(vt)} ({_mxn(anterior_kpi['ticket_promedio'])} → {_mxn(actual['ticket_promedio'])}).",
                                     transacciones_variacion_pct=vn, ticket_variacion_pct=vt))
        # ---- canales (solo con ambos canales en vista)
        if not canal:
            fis, onl = (next(c for c in canales if c["canal"] == k) for k in ("FISICA", "ONLINE"))
            dom = max(canales, key=lambda c: c["participacion_pct"] or 0)
            nom = {"FISICA": "físico", "ONLINE": "online"}
            if dom["participacion_pct"] is not None and dom["participacion_pct"] >= criterios.participacion_dominante_pct:
                mensajes.append(_msg("canal_participacion", "canal", f"El canal {nom[dom['canal']]} concentró {dom['participacion_pct']:.1f} % de las ventas ({_mxn(dom['importe'])} de {_mxn(fis['importe'] + onl['importe'])}).",
                                     canal=dom["canal"], participacion_pct=dom["participacion_pct"], umbral=criterios.participacion_dominante_pct))
            elif dom["participacion_pct"] is not None:
                mensajes.append(_msg("canal_participacion", "canal", f"Las ventas están repartidas: físico {fis['participacion_pct']:.1f} % y online {onl['participacion_pct']:.1f} % (ningún canal alcanza {criterios.participacion_dominante_pct:g} %).",
                                     fisica=fis["participacion_pct"], online=onl["participacion_pct"]))
            vf, vo = fis["variacion_importe_pct"], onl["variacion_importe_pct"]
            if periodos["homogeneo"] and vf is not None and vo is not None and fis["transacciones_anterior"] >= criterios.min_transacciones_periodo and onl["transacciones_anterior"] >= criterios.min_transacciones_periodo:
                if abs(vf - vo) >= criterios.brecha_canales_pp:
                    mejor, vm, vp = ("FISICA", vf, vo) if vf > vo else ("ONLINE", vo, vf)
                    peor = "ONLINE" if mejor == "FISICA" else "FISICA"
                    mensajes.append(_msg("canal_desempeno", "canal", f"El canal {nom[mejor]} presentó un mejor desempeño: {'+' if vm >= 0 else '−'}{_pct(vm)} frente a {'+' if vp >= 0 else '−'}{_pct(vp)} del canal {nom[peor]}.",
                                         mejor=mejor, variacion_fisica_pct=vf, variacion_online_pct=vo, brecha_minima_pp=criterios.brecha_canales_pp))
                else:
                    mensajes.append(_msg("canal_desempeno", "canal", f"Ambos canales evolucionaron de forma similar (físico {'+' if vf >= 0 else '−'}{_pct(vf)}, online {'+' if vo >= 0 else '−'}{_pct(vo)}; diferencia menor que {criterios.brecha_canales_pp:g} puntos).",
                                         variacion_fisica_pct=vf, variacion_online_pct=vo))
        # ---- atípicas y estados
        if atip["participacion_pct"] is not None and atip["participacion_pct"] >= criterios.atipicas_relevantes_pct:
            extra = ""
            if sin_atip and sin_atip["variacion_pct"] is not None:
                extra = f" Sin esas transacciones, la variación frente al período anterior sería {'+' if sin_atip['variacion_pct'] >= 0 else '−'}{_pct(sin_atip['variacion_pct'])}."
            mensajes.append(_msg("atipicas", "aviso", f"{atip['transacciones']} transacciones marcadas como atípicas por el ETL (cantidades o importes fuera del IQR) suman {_mxn(atip['importe'])}, "
                                 f"{atip['participacion_pct']:.1f} % del importe: el total puede estar dominado por ellas.{extra}", **atip, umbral=criterios.atipicas_relevantes_pct,
                                 sin_atipicas=sin_atip))
        if estados == "todas" and no_ef["transacciones"]:
            mensajes.append(_msg("no_efectivas", "info", f"El importe incluye {no_ef['transacciones']} pedidos cancelados o devueltos ({_mxn(no_ef['importe'])}). "
                                 "Puedes excluirlos con «Solo ventas efectivas».", **no_ef))
    mensajes.append(_msg("alcance", "nota", "Estas cifras describen ventas registradas de transacciones conformes. No hay costos, márgenes ni gastos en los datos: no permiten afirmar rentabilidad ni salud financiera."))
    return {"estado": estado, "titular": titular, "mensajes": mensajes}


# ----------------------------------------------------------------------------- respuestas de los endpoints
def resumen(conn, mes, desde, hasta, canal, comparacion, estados, criterios: Criterios) -> dict:
    per = resolver_periodos(conn, mes, desde, hasta, comparacion)
    act = kpis(conn, per["actual"], canal, estados)
    ant = kpis(conn, per["anterior"], canal, estados) if per["anterior"] and per["anterior"]["cobertura"] > 0 else None
    canales = canales_periodo(conn, per["actual"], per["anterior"], estados)
    atip = atipicas(conn, per["actual"], canal, estados)
    ne = no_efectivas(conn, per["actual"], canal)
    sa = sin_atipicas(conn, per["actual"], per["anterior"], canal, estados)
    variaciones = {"importe_pct": variacion_pct(act["importe"], ant["importe"]) if ant else None,
                   "transacciones_pct": variacion_pct(act["transacciones"], ant["transacciones"]) if ant else None,
                   "ticket_promedio_pct": variacion_pct(act["ticket_promedio"], ant["ticket_promedio"]) if ant else None,
                   "promedio_diario_pct": variacion_pct(act["promedio_diario"], ant["promedio_diario"]) if ant else None}
    return {
        "filtros": {"mes": per["mes"], "desde": desde, "hasta": hasta, "canal": canal, "comparacion": comparacion, "estados": estados},
        "modo": per["modo"], "periodo": per["actual"], "anterior": per["anterior"], "homogeneo": per["homogeneo"],
        "avisos": per["avisos"], "cobertura_datos": per["cobertura_datos"],
        "actual": act, "anterior_kpis": ant, "variaciones": variaciones, "canales": canales, "atipicas": {**atip, "sin_atipicas": sa}, "no_efectivas": ne,
        "diagnostico": diagnostico(per, act, ant, canales, atip, ne, estados, canal, criterios, sa),
        "criterios": asdict(criterios),
        "definicion_importe": {"campo": f"transacciones_limpias.{CAMPO_IMPORTE}",
                               "texto": "Importes de transacciones conformes, normalizados a MXN, sin recorte estadístico.",
                               "no_es": "No es ingreso contable auditado, utilidad ni margen. No incluye transacciones en cuarentena."},
    }


def tendencia(conn, mes, desde, hasta, canal, comparacion, estados) -> dict:
    per = resolver_periodos(conn, mes, desde, hasta, comparacion)
    filtro, p = _filtro(canal, estados)

    def por_dia(periodo: Optional[dict]) -> dict[str, dict]:
        if not periodo or periodo["cobertura"] == 0:
            return {}
        rows = filas(conn, f"SELECT fecha_venta AS f, COUNT(*) AS n, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS imp, "
                           f"COALESCE(SUM(CASE WHEN origen='FISICA' THEN {CAMPO_IMPORTE} END), 0) AS fis, "
                           f"COALESCE(SUM(CASE WHEN origen='ONLINE' THEN {CAMPO_IMPORTE} END), 0) AS onl "
                           f"FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro} GROUP BY fecha_venta", [periodo["inicio"], periodo["fin"], *p])
        return {r["f"]: r for r in rows}

    cob = (_d(per["cobertura_datos"]["inicio"]), _d(per["cobertura_datos"]["fin"]))
    a, b = por_dia(per["actual"]), por_dia(per["anterior"])
    ini_a = _d(per["actual"]["inicio"])
    ini_b = _d(per["anterior"]["inicio"]) if per["anterior"] else None
    dias, acum_a, acum_b = [], 0.0, 0.0
    for k in range(per["actual"]["dias"]):
        fa = ini_a + timedelta(days=k)
        fb = ini_b + timedelta(days=k) if ini_b and k < per["anterior"]["dias"] else None
        cub_a = cob[0] <= fa <= cob[1]
        cub_b = bool(fb and cob[0] <= fb <= cob[1])
        ra, rb = a.get(fa.isoformat()), b.get(fb.isoformat()) if fb else None
        imp_a = (ra["imp"] if ra else 0.0) if cub_a else None
        imp_b = (rb["imp"] if rb else 0.0) if cub_b else None
        n_a = (ra["n"] if ra else 0) if cub_a else None
        n_b = (rb["n"] if rb else 0) if cub_b else None
        acum_a += imp_a or 0.0
        acum_b += imp_b or 0.0
        dias.append({"indice": k + 1, "fecha": fa.isoformat(), "importe": None if imp_a is None else round(imp_a, 2), "transacciones": n_a,
                     "ticket_promedio": _div(imp_a, n_a) if n_a else None, "fisica": None if not ra else round(ra["fis"], 2), "online": None if not ra else round(ra["onl"], 2),
                     "acumulado": round(acum_a, 2) if cub_a else None,
                     "fecha_anterior": fb.isoformat() if fb else None, "importe_anterior": None if imp_b is None else round(imp_b, 2), "transacciones_anterior": n_b,
                     "ticket_anterior": _div(imp_b, n_b) if n_b else None, "acumulado_anterior": round(acum_b, 2) if cub_b else None})
    return {"periodo": per["actual"], "anterior": per["anterior"], "homogeneo": per["homogeneo"], "dias": dias,
            "meses": meses_disponibles(conn, canal, estados), "avisos": per["avisos"]}


def canales(conn, mes, desde, hasta, comparacion, estados) -> dict:
    per = resolver_periodos(conn, mes, desde, hasta, comparacion)
    return {"periodo": per["actual"], "anterior": per["anterior"], "homogeneo": per["homogeneo"],
            "canales": canales_periodo(conn, per["actual"], per["anterior"], estados), "avisos": per["avisos"],
            "nota": "Muestra siempre ambos canales; el filtro de canal no se aplica aquí."}


ORDEN_PRODUCTOS = {"importe": "importe", "unidades": "unidades", "transacciones": "transacciones"}


def productos(conn, mes, desde, hasta, canal, comparacion, estados, orden: str, limite: int) -> dict:
    per = resolver_periodos(conn, mes, desde, hasta, comparacion)
    filtro, p = _filtro(canal, estados)
    args = [per["actual"]["inicio"], per["actual"]["fin"], *p]
    total = escalar(conn, f"SELECT COALESCE(SUM({CAMPO_IMPORTE}), 0) FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro}", args)
    rows = filas(conn, f"SELECT id_producto, nombre_producto, categoria, COUNT(*) AS transacciones, COALESCE(SUM(cantidad), 0) AS unidades, "
                       f"COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro} "
                       f"GROUP BY id_producto ORDER BY {ORDEN_PRODUCTOS[orden]} DESC, id_producto LIMIT ?", [*args, limite])
    cats = filas(conn, f"SELECT categoria, COUNT(*) AS transacciones, COALESCE(SUM(cantidad), 0) AS unidades, COALESCE(SUM({CAMPO_IMPORTE}), 0) AS importe "
                       f"FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro} GROUP BY categoria ORDER BY importe DESC", args)
    for r in rows + cats:
        r["importe"] = round(r["importe"], 2)
        r["participacion_pct"] = round(r["importe"] / total * 100, 2) if total else None
    productos_total = escalar(conn, f"SELECT COUNT(DISTINCT id_producto) FROM transacciones_limpias WHERE fecha_venta BETWEEN ? AND ?{filtro}", args)
    return {"periodo": per["actual"], "orden": orden, "importe_total": round(total, 2), "productos_distintos": productos_total,
            "productos": rows, "categorias": cats, "avisos": per["avisos"],
            "nota": "Unidades = cantidad real de la transacción (sin capping). Participación sobre el importe comercial del período."}


def opciones(conn) -> dict:
    cob = cobertura_datos(conn)
    meses = meses_disponibles(conn)
    return {"hay_datos": bool(meses), "cobertura": {"inicio": cob[0].isoformat() if cob[0] else None, "fin": cob[1].isoformat() if cob[1] else None},
            "meses": meses, "mes_por_defecto": meses[-1]["mes"] if meses else None,
            "canales": ["FISICA", "ONLINE"], "comparaciones": ["equivalente", "mes_anterior_completo", "ninguna"], "estados": ["todas", "efectivas"]}
