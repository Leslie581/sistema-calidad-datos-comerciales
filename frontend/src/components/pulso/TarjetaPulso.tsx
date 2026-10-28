import { Link } from "react-router-dom";
import { ArrowRight, TrendingUp } from "lucide-react";
import { MarcaDeAgua } from "../brand/Marca";
import { useApi } from "../../hooks/useApi";
import { useSistema } from "../../hooks/sistema";
import { fMXNCorto } from "../../lib/format";
import { api } from "../../services/api";
import { Esqueleto } from "../ui/Basicos";
import { Variacion } from "./Pulso";

/** Resumen compacto del Pulso comercial para el Panel ejecutivo. Si no hay ventas o falla la consulta, no ocupa espacio. */
export function TarjetaPulso() {
  const { ciclo } = useSistema();
  const { datos: r, error, cargando } = useApi((s) => api.comercialResumen({}, s), [ciclo]);
  if (error && !r) return null;
  if (!r) return cargando ? <Esqueleto className="h-28" /> : null;
  return (
    <Link to="/pulso-comercial" aria-label="Abrir Pulso comercial" className="panel entra group relative flex flex-wrap items-center gap-x-8 gap-y-3 overflow-hidden px-6 py-5 transition hover:shadow-elevada" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
      <MarcaDeAgua className="-right-10 -top-28 scale-50" opacidad={0.05} />
      <span className="relative grid size-12 shrink-0 place-items-center rounded-2xl bg-bosque text-menta"><TrendingUp size={22} aria-hidden="true" /></span>
      <div className="relative min-w-[180px]">
        <p className="etiqueta">Pulso comercial · {r.periodo.etiqueta}{r.periodo.parcial ? " (parcial)" : ""}</p>
        <p className="num font-display text-3xl font-bold leading-tight text-bosque">{fMXNCorto(r.actual.importe)}</p>
      </div>
      <div className="relative"><Variacion valor={r.variaciones.importe_pct} grande /></div>
      <p className="relative min-w-[220px] flex-1 text-[0.95rem] text-suave">{r.diagnostico.titular}</p>
      <span className="relative inline-flex min-h-11 items-center gap-1.5 font-bold text-petroleo">Abrir Pulso comercial <ArrowRight size={16} className="transition group-hover:translate-x-1" aria-hidden="true" /></span>
    </Link>
  );
}
