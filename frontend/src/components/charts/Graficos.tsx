import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fEntero, fFecha, fMXNCorto, fPct, nombreCanal } from "../../lib/format";
import type { CanalResumen, Dashboard, SaludOrigen, Segmento } from "../../services/tipos";

const COLOR_CANAL = { FISICA: "#215548", ONLINE: "#D99B45" } as const;
const COLOR_SEGMENTO: Record<Segmento, string> = { Bajo: "#B8E8CE", Medio: "#5FA586", Alto: "#17352D" };

/* ------------------------------------------------------------------ anillo de salud (SVG propio) */
export function SaludAnillo({ salud, tam = 220 }: { salud: SaludOrigen; tam?: number }) {
  const r = 82, c = 2 * Math.PI * r;
  const partes = [
    { clave: "conformes", n: salud.conformes, color: "#B8E8CE", texto: "Conformes de origen" },
    { clave: "reparados", n: salud.reparados, color: "#D99B45", texto: "Reparados y aceptados" },
    { clave: "rechazados", n: salud.rechazados, color: "#CB6F61", texto: "Rechazados (cuarentena)" },
  ];
  let acumulado = 0;
  const resumen = partes.map((p) => `${p.texto}: ${fEntero(p.n)}`).join("; ");
  return (
    <figure className="m-0" aria-label={`Composición de ${fEntero(salud.entrada)} registros de entrada. ${resumen}.`}>
      <svg width={tam} height={tam} viewBox="0 0 200 200" className="entra-suave" role="img" aria-label={`Salud de origen ${fPct(salud.valor, 1)}. ${resumen}`}>
        <circle cx="100" cy="100" r={r} fill="none" stroke="#FDFCFA" strokeOpacity="0.1" strokeWidth="18" />
        {partes.map((p) => {
          const largo = (p.n / salud.entrada) * c;
          const gap = 4;
          const nodo = (
            <circle key={p.clave} cx="100" cy="100" r={r} fill="none" stroke={p.color} strokeWidth="18" strokeLinecap="butt"
              strokeDasharray={`${Math.max(largo - gap, 0)} ${c - Math.max(largo - gap, 0)}`} strokeDashoffset={-acumulado}
              transform="rotate(-90 100 100)" />
          );
          acumulado += largo;
          return nodo;
        })}
        <text x="100" y="94" textAnchor="middle" className="num" fill="#FDFCFA" fontFamily="var(--font-display)" fontWeight="800" fontSize="38">
          {salud.valor == null ? "—" : `${Math.round(salud.valor * 100)}%`}
        </text>
        <text x="100" y="118" textAnchor="middle" fill="#B8E8CE" fontSize="11.5" fontWeight="700" letterSpacing="1.2">SALUD DE ORIGEN</text>
      </svg>
    </figure>
  );
}

/* ------------------------------------------------------------------ comparación de canales */
export function ComparacionCanales({ canales }: { canales: CanalResumen[] }) {
  return (
    <ul className="space-y-6">
      {canales.map((c) => {
        const ok = c.entrada ? (c.limpias / c.entrada) * 100 : 0;
        return (
          <li key={c.origen}>
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <p className="flex items-center gap-2 font-display text-lg font-bold text-bosque">
                <span className="size-3 rounded-full" style={{ background: COLOR_CANAL[c.origen] }} aria-hidden="true" />{nombreCanal(c.origen)}
              </p>
              <p className="num text-sm text-suave"><b className="text-bosque">{fPct(c.tasa_aceptacion)}</b> aceptación</p>
            </div>
            <div className="flex h-9 overflow-hidden rounded-full bg-superficie-2" role="img"
              aria-label={`${nombreCanal(c.origen)}: ${fEntero(c.limpias)} limpias y ${fEntero(c.cuarentena)} en cuarentena de ${fEntero(c.entrada)}`}>
              <div className="grid place-items-center bg-petroleo text-xs font-bold text-blanco transition-[width] duration-700" style={{ width: `${ok}%` }}>
                <span className="num">{fEntero(c.limpias)}</span>
              </div>
              <div className="grid flex-1 place-items-center bg-[#e8b9b1] text-xs font-bold text-[#6c241c]"><span className="num">{fEntero(c.cuarentena)}</span></div>
            </div>
            <p className="num mt-1.5 text-xs text-suave">{fEntero(c.entrada)} recibidos · {fMXNCorto(c.importe_mxn)} con capping en transacciones limpias</p>
          </li>
        );
      })}
      <li className="flex flex-wrap gap-4 text-xs font-bold text-suave" aria-hidden="true">
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-petroleo" />Limpias</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-[#e8b9b1]" />Cuarentena</span>
      </li>
    </ul>
  );
}

/* ------------------------------------------------------------------ serie diaria (Recharts) */
export function SerieDiaria({ datos, metrica }: { datos: Dashboard["por_dia"]; metrica: "importe" | "n" }) {
  const filas = useMemo(() => {
    const m = new Map<string, { fecha: string; FISICA: number; ONLINE: number }>();
    for (const d of datos) {
      const f = m.get(d.fecha) ?? { fecha: d.fecha, FISICA: 0, ONLINE: 0 };
      f[d.origen] = metrica === "importe" ? d.importe_mxn : d.n;
      m.set(d.fecha, f);
    }
    return [...m.values()].sort((a, b) => a.fecha.localeCompare(b.fecha));
  }, [datos, metrica]);
  const fmt = (v: number) => (metrica === "importe" ? fMXNCorto(v) : fEntero(v));
  return (
    <div role="img" aria-label={`Serie diaria de ${metrica === "importe" ? "importe en MXN" : "transacciones"} por canal, ${filas.length} días`} className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <AreaChart data={filas} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            {(["FISICA", "ONLINE"] as const).map((k) => (
              <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor={COLOR_CANAL[k]} stopOpacity={0.55} /><stop offset="1" stopColor={COLOR_CANAL[k]} stopOpacity={0.04} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid stroke="#dcdfd3" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="fecha" tickFormatter={(f: string) => fFecha(f).slice(0, -5)} tick={{ fontSize: 12, fill: "#526860" }} tickLine={false} axisLine={false} minTickGap={28} />
          <YAxis tickFormatter={(v: number) => (metrica === "importe" ? `${Math.round(v / 1000)} k` : String(v))} tick={{ fontSize: 12, fill: "#526860" }} tickLine={false} axisLine={false} width={metrica === "importe" ? 52 : 36} />
          <Tooltip formatter={(v, nombre) => [fmt(Number(v)), nombreCanal(String(nombre))]} labelFormatter={(l) => fFecha(String(l))}
            contentStyle={{ borderRadius: 14, border: "1px solid #dcdfd3", boxShadow: "0 8px 24px -12px rgb(23 53 45 / .3)", fontFamily: "inherit" }} />
          <Area type="monotone" dataKey="FISICA" stackId="1" stroke={COLOR_CANAL.FISICA} strokeWidth={2} fill="url(#g-FISICA)" isAnimationActive />
          <Area type="monotone" dataKey="ONLINE" stackId="1" stroke={COLOR_CANAL.ONLINE} strokeWidth={2} fill="url(#g-ONLINE)" isAnimationActive />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ segmentos por canal */
export function SegmentosCanal({ segmentos }: { segmentos: Dashboard["segmentos"] }) {
  const canales = ["FISICA", "ONLINE"] as const;
  return (
    <div className="space-y-5">
      {canales.map((canal) => {
        const filas = (["Bajo", "Medio", "Alto"] as const).map((s) => ({ s, n: segmentos.find((x) => x.origen === canal && x.segmento === s)?.n ?? 0 }));
        const total = filas.reduce((a, b) => a + b.n, 0) || 1;
        return (
          <div key={canal}>
            <p className="mb-1.5 text-sm font-bold text-bosque">{nombreCanal(canal)}</p>
            <div className="flex h-8 overflow-hidden rounded-full" role="img" aria-label={filas.map((f) => `${f.s}: ${f.n}`).join(", ")}>
              {filas.map((f) => (
                <div key={f.s} className="grid place-items-center text-xs font-bold transition-[width] duration-700"
                  style={{ width: `${(f.n / total) * 100}%`, background: COLOR_SEGMENTO[f.s], color: f.s === "Bajo" ? "#17352D" : "#FDFCFA" }}>
                  <span className="num">{f.n}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
      <p className="flex gap-4 text-xs font-bold text-suave" aria-hidden="true">
        {(["Bajo", "Medio", "Alto"] as const).map((s) => <span key={s} className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm" style={{ background: COLOR_SEGMENTO[s] }} />{s}</span>)}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ barras de motivos */
export function BarrasMotivos({ motivos, alElegir }: { motivos: Dashboard["motivos"]["por_codigo"]; alElegir?: (codigo: string) => void }) {
  const max = Math.max(...motivos.map((m) => m.registros), 1);
  return (
    <ul className="space-y-3">
      {motivos.map((m) => {
        const contenido = (
          <>
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-bold text-bosque">{m.codigo}</span>
              <span className="num font-bold text-coral-texto">{fEntero(m.registros)}</span>
            </span>
            <span className="mt-1 block h-2.5 overflow-hidden rounded-full bg-[#f3e1dc]">
              <span className="block h-full rounded-full bg-gradient-to-r from-ambar to-coral transition-[width] duration-700" style={{ width: `${(m.registros / max) * 100}%` }} />
            </span>
            {m.descripcion && <span className="mt-1 block text-xs text-suave">{m.descripcion}</span>}
          </>
        );
        return <li key={m.codigo}>{alElegir ? <button type="button" onClick={() => alElegir(m.codigo)} className="block w-full rounded-lg text-left">{contenido}</button> : contenido}</li>;
      })}
    </ul>
  );
}

