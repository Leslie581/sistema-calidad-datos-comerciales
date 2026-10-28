import { useMemo } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Info, Minus, ShoppingBag, TrendingDown, TrendingUp } from "lucide-react";
import { fEntero, fFecha, fMXN, fMXNCompacto, fPct, fVariacion, nombreCanal } from "../../lib/format";
import type { CanalComercial, DiaTendencia, EstadoDiagnostico, MensajeComercial, MesComercial, PeriodoComercial } from "../../services/tipos";

const COLOR_ACTUAL = "#215548";
const COLOR_ANTERIOR = "#D99B45";

/* ------------------------------------------------------------------ variación (flecha + signo + texto: nunca solo color) */
export function Variacion({ valor, invertir = false, grande = false }: { valor: number | null; invertir?: boolean; grande?: boolean }) {
  if (valor == null) {
    return <span className={`inline-flex items-center gap-1 rounded-full bg-superficie-2 px-2.5 py-0.5 font-bold text-suave ${grande ? "text-base" : "text-xs"}`}><Minus size={grande ? 16 : 12} aria-hidden="true" />Sin comparación válida</span>;
  }
  const sube = valor > 0, baja = valor < 0;
  const bueno = invertir ? baja : sube, malo = invertir ? sube : baja;
  const tono = bueno ? "bg-[#e3f3ea] text-menta-texto" : malo ? "bg-[#f9e5e1] text-coral-texto" : "bg-superficie-2 text-suave";
  const Icono = sube ? ArrowUpRight : baja ? ArrowDownRight : Minus;
  return (
    <span className={`num inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-bold ${tono} ${grande ? "text-base" : "text-xs"}`}
      aria-label={`${sube ? "Aumento" : baja ? "Disminución" : "Sin cambio"} de ${Math.abs(valor).toFixed(1)} por ciento`}>
      <Icono size={grande ? 17 : 13} aria-hidden="true" />{fVariacion(valor)}
    </span>
  );
}

/* ------------------------------------------------------------------ diagnóstico */
const ESTILO_DIAG: Record<EstadoDiagnostico, { icono: typeof TrendingUp; tono: string; etiqueta: string }> = {
  crecimiento: { icono: TrendingUp, tono: "bg-menta text-bosque", etiqueta: "Crecimiento" },
  estable: { icono: Minus, tono: "bg-[#e6eef0] text-petroleo", etiqueta: "Estabilidad" },
  disminucion: { icono: TrendingDown, tono: "bg-[#f2b6ac] text-[#5c1c14]", etiqueta: "Disminución" },
  sin_comparacion: { icono: Info, tono: "bg-superficie-2 text-suave", etiqueta: "Sin comparación" },
  no_concluyente: { icono: AlertTriangle, tono: "bg-[#f3d9a8] text-[#4a2f06]", etiqueta: "No concluyente" },
  sin_datos: { icono: Info, tono: "bg-superficie-2 text-suave", etiqueta: "Sin datos" },
};
const ICONO_MENSAJE: Record<MensajeComercial["tipo"], typeof Info> = { tendencia: TrendingUp, canal: ShoppingBag, aviso: AlertTriangle, info: Info, nota: Info };

export function EncabezadoDiagnostico({ estado, titular }: { estado: EstadoDiagnostico; titular: string }) {
  const e = ESTILO_DIAG[estado];
  const Icono = e.icono;
  return (
    <div className="flex items-start gap-3">
      <span className={`grid size-12 shrink-0 place-items-center rounded-2xl ${e.tono}`}><Icono size={22} aria-hidden="true" /></span>
      <div className="min-w-0">
        <p className="etiqueta">{e.etiqueta}</p>
        <p className="titular text-[1.45rem] leading-tight text-bosque">{titular}</p>
      </div>
    </div>
  );
}

/** Las transacciones atípicas pueden dominar el importe: se advierte junto al titular, no al final de la página. */
export function AvisoAtipicas({ mensaje }: { mensaje: MensajeComercial }) {
  return (
    <div data-mensaje={mensaje.id} role="note" className="mt-4 flex gap-2.5 rounded-2xl bg-[#fdf6ea] p-3.5 text-sm leading-relaxed ring-1 ring-[#ecd6b0]">
      <AlertTriangle size={17} className="mt-0.5 shrink-0 text-ambar-texto" aria-hidden="true" />
      <span><b className="text-bosque">Ojo con los atípicos.</b> {mensaje.texto}</span>
    </div>
  );
}

export function ListaMensajes({ mensajes }: { mensajes: MensajeComercial[] }) {
  return (
    <ul className="space-y-2.5">
      {mensajes.map((m) => {
        const Icono = ICONO_MENSAJE[m.tipo];
        const aviso = m.tipo === "aviso";
        return (
          <li key={m.id} data-mensaje={m.id} className={`flex gap-3 rounded-2xl p-3.5 text-[0.93rem] leading-relaxed ${aviso ? "bg-[#fdf6ea] ring-1 ring-[#ecd6b0]" : m.tipo === "nota" ? "bg-superficie-2 text-suave" : "bg-blanco ring-1 ring-borde"}`}>
            <Icono size={17} className={`mt-1 shrink-0 ${aviso ? "text-ambar-texto" : "text-petroleo"}`} aria-hidden="true" />
            <span>{m.texto}</span>
          </li>
        );
      })}
    </ul>
  );
}

/* ------------------------------------------------------------------ serie diaria actual vs anterior */
export type MetricaSerie = "importe" | "transacciones" | "ticket" | "acumulado";
const CAMPOS: Record<MetricaSerie, { a: keyof DiaTendencia; b: keyof DiaTendencia; nombre: string }> = {
  importe: { a: "importe", b: "importe_anterior", nombre: "Importe" },
  transacciones: { a: "transacciones", b: "transacciones_anterior", nombre: "Transacciones" },
  ticket: { a: "ticket_promedio", b: "ticket_anterior", nombre: "Ticket promedio" },
  acumulado: { a: "acumulado", b: "acumulado_anterior", nombre: "Importe acumulado" },
};

export function SerieComercial({ dias, metrica, periodo, anterior }: { dias: DiaTendencia[]; metrica: MetricaSerie; periodo: PeriodoComercial; anterior: PeriodoComercial | null }) {
  const campo = CAMPOS[metrica];
  const datos = useMemo(() => dias.map((d) => ({ indice: d.indice, fecha: d.fecha, fechaAnt: d.fecha_anterior, actual: d[campo.a] as number | null, anterior: d[campo.b] as number | null })), [dias, campo]);
  const dinero = metrica !== "transacciones";
  const fmt = (v: number | null | undefined) => (v == null ? "—" : dinero ? fMXN(v) : fEntero(v));
  return (
    <div role="img" aria-label={`${campo.nombre} por día: ${periodo.etiqueta}${anterior ? ` frente a ${anterior.etiqueta}` : ""}, ${dias.length} días`} className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <LineChart data={datos} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#dcdfd3" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="indice" tick={{ fontSize: 12, fill: "#526860" }} tickLine={false} axisLine={false} minTickGap={18} tickFormatter={(i: number) => `día ${i}`} />
          <YAxis tick={{ fontSize: 12, fill: "#526860" }} tickLine={false} axisLine={false} width={dinero ? 64 : 40} tickFormatter={(v: number) => (dinero ? fMXNCompacto(v) : String(v))} />
          <Tooltip content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as (typeof datos)[number];
            return (
              <div className="rounded-2xl border border-borde bg-blanco p-3 text-sm shadow-suave">
                <p className="font-bold text-bosque">Día {p.indice}</p>
                <p className="num flex items-center gap-2"><i className="size-2.5 rounded-full" style={{ background: COLOR_ACTUAL }} />{fFecha(p.fecha)}: <b>{fmt(p.actual)}</b></p>
                {anterior && <p className="num flex items-center gap-2"><i className="size-2.5 rounded-full" style={{ background: COLOR_ANTERIOR }} />{p.fechaAnt ? fFecha(p.fechaAnt) : "—"}: <b>{fmt(p.anterior)}</b></p>}
              </div>
            );
          }} />
          <Legend verticalAlign="top" align="right" iconType="plainline" wrapperStyle={{ fontSize: 12.5, paddingBottom: 6 }} />
          {anterior && <Line type="monotone" dataKey="anterior" name={`Anterior · ${anterior.etiqueta}`} stroke={COLOR_ANTERIOR} strokeWidth={2.2} strokeDasharray="6 5" dot={false} connectNulls={false} />}
          <Line type="monotone" dataKey="actual" name={`Actual · ${periodo.etiqueta}`} stroke={COLOR_ACTUAL} strokeWidth={3} dot={false} activeDot={{ r: 5 }} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ canales */
export function CanalesPulso({ canales }: { canales: CanalComercial[] }) {
  const total = canales.reduce((a, c) => a + c.importe, 0);
  return (
    <div className="space-y-5">
      <div className="flex h-12 overflow-hidden rounded-2xl" role="img" aria-label={canales.map((c) => `${nombreCanal(c.canal)} ${fPct((c.participacion_pct ?? 0) / 100)}`).join(", ")}>
        {canales.map((c) => (
          <div key={c.canal} className="grid place-items-center px-1 text-sm font-bold transition-[width] duration-700" style={{ width: `${total ? (c.importe / total) * 100 : 0}%`, background: c.canal === "FISICA" ? "#215548" : "#D99B45", color: c.canal === "FISICA" ? "#FDFCFA" : "#17352D", minWidth: c.importe ? "2.5rem" : 0 }}>
            <span className="num">{c.participacion_pct != null ? `${c.participacion_pct.toFixed(0)} %` : ""}</span>
          </div>
        ))}
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {canales.map((c) => (
          <li key={c.canal} className="rounded-2xl border border-borde bg-blanco p-4" data-canal={c.canal}>
            <p className="flex items-center gap-2 font-display text-lg font-bold text-bosque"><i className="size-3 rounded-full" style={{ background: c.canal === "FISICA" ? "#215548" : "#D99B45" }} aria-hidden="true" />{nombreCanal(c.canal)}</p>
            <p className="num mt-1 font-display text-2xl font-bold text-bosque">{fMXN(c.importe)}</p>
            <p className="num text-sm text-suave">{fEntero(c.transacciones)} transacciones · ticket {fMXN(c.ticket_promedio)}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-suave"><Variacion valor={c.variacion_importe_pct} />{c.importe_anterior != null && <span className="num">antes {fMXN(c.importe_anterior)}</span>}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ comparación por mes (parciales marcados) */
export function ComparacionMeses({ meses, seleccionado }: { meses: MesComercial[]; seleccionado: string | null }) {
  const max = Math.max(...meses.map((m) => m.importe), 1);
  const maxDiario = Math.max(...meses.map((m) => m.promedio_diario ?? 0), 1);
  return (
    <ul className="space-y-5">
      {meses.map((m) => (
        <li key={m.mes} data-mes={m.mes}>
          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
            <p className="font-display text-lg font-bold text-bosque">{m.etiqueta}{m.mes === seleccionado && <span className="ml-2 rounded-full bg-menta px-2 py-0.5 align-middle text-[0.68rem] font-bold text-bosque">en vista</span>}</p>
            <p className="num text-xs text-suave">{m.dias_cubiertos} de {m.dias_mes} días con datos{m.parcial ? " · PARCIAL" : ""}</p>
          </div>
          <div className="h-5 overflow-hidden rounded-full bg-superficie-2" role="img" aria-label={`${m.etiqueta}: ${fMXN(m.importe)}${m.parcial ? ", mes parcial" : ""}`}>
            <div className="h-full rounded-full" style={{ width: `${(m.importe / max) * 100}%`, background: m.parcial ? "repeating-linear-gradient(135deg, #5FA586 0 8px, #B8E8CE 8px 16px)" : "#215548" }} />
          </div>
          <p className="num mt-1 text-sm"><b className="text-bosque">{fMXN(m.importe)}</b> <span className="text-suave">· {fEntero(m.transacciones)} transacciones</span></p>
          <div className="mt-1.5 flex items-center gap-2 text-xs text-suave">
            <span className="w-28 shrink-0">Promedio diario</span>
            <span className="h-2 flex-1 overflow-hidden rounded-full bg-superficie-2"><span className="block h-full rounded-full bg-ambar" style={{ width: `${((m.promedio_diario ?? 0) / maxDiario) * 100}%` }} /></span>
            <span className="num w-24 text-right font-bold text-bosque">{fMXN(m.promedio_diario)}</span>
          </div>
        </li>
      ))}
      <li className="text-xs text-suave">Los meses parciales no son comparables por total: usa el promedio diario o el intervalo equivalente.</li>
    </ul>
  );
}
