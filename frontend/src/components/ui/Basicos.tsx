import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

/* ---------------------------------------------------------------- Botón */
type Variante = "primario" | "secundario" | "fantasma" | "peligro";
export function Boton({ variante = "primario", className = "", children, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  const estilos: Record<Variante, string> = {
    primario: "bg-bosque text-blanco hover:bg-petroleo shadow-suave",
    secundario: "bg-blanco text-bosque border border-borde-fuerte hover:bg-superficie-2",
    fantasma: "text-bosque hover:bg-bosque/8",
    peligro: "bg-coral-texto text-blanco hover:bg-[#8c3830]",
  };
  return (
    <button
      type="button"
      {...p}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-bold transition-[background-color,transform,box-shadow] duration-200 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 ${estilos[variante]} ${className}`}
    >
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------- Insignias de estado */
type Tono = "neutro" | "ok" | "aviso" | "alerta" | "info" | "oscuro";
const TONOS: Record<Tono, string> = {
  neutro: "bg-superficie-2 text-suave border-borde",
  ok: "bg-[#e3f3ea] text-menta-texto border-[#bfe3cf]",
  aviso: "bg-[#fbf0dc] text-ambar-texto border-[#ecd6b0]",
  alerta: "bg-[#f9e5e1] text-coral-texto border-[#eec3bb]",
  info: "bg-[#e6eef0] text-petroleo border-[#c8d9dc]",
  oscuro: "bg-bosque text-menta border-bosque",
};
export function Insignia({ tono = "neutro", children, className = "", title }: { tono?: Tono; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={`inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-0.5 text-left text-xs font-bold ${TONOS[tono]} ${className}`}>
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- Esqueleto de carga */
export function Esqueleto({ className = "", style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} style={style} />;
}

/* ---------------------------------------------------------------- Encabezado de sección */
export function Encabezado({ etiqueta, titulo, children, acciones }: { etiqueta?: string; titulo: string; children?: ReactNode; acciones?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {etiqueta && <p className="etiqueta mb-2">{etiqueta}</p>}
        <h1 className="titular text-[clamp(1.9rem,3.4vw,2.9rem)] text-bosque">{titulo}</h1>
        {children && <p className="lectura mt-2 text-[0.98rem] text-suave">{children}</p>}
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- Número animado (respeta reduced-motion) */
export function NumeroAnimado({ valor, formato, duracion = 900 }: { valor: number; formato: (n: number) => string; duracion?: number }) {
  const [mostrado, setMostrado] = useState(valor);
  const previo = useRef(valor);
  useEffect(() => {
    const reducido = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const desde = previo.current;
    previo.current = valor;
    if (reducido || desde === valor) {
      const t = setTimeout(() => setMostrado(valor), 0);
      return () => clearTimeout(t);
    }
    let raf = 0;
    const t0 = performance.now();
    const paso = (t: number) => {
      const k = Math.min(1, (t - t0) / duracion);
      const suave = 1 - Math.pow(1 - k, 3);
      setMostrado(desde + (valor - desde) * suave);
      if (k < 1) raf = requestAnimationFrame(paso);
    };
    raf = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(raf);
  }, [valor, duracion]);
  return <span className="num">{formato(mostrado)}</span>;
}

/* ---------------------------------------------------------------- Dato clave (compacto) */
export function Dato({ etiqueta, valor, nota, className = "" }: { etiqueta: string; valor: ReactNode; nota?: ReactNode; className?: string }) {
  return (
    <div className={className}>
      <p className="etiqueta">{etiqueta}</p>
      <p className="num mt-1 font-display text-2xl font-bold text-bosque">{valor}</p>
      {nota && <p className="mt-0.5 text-xs text-suave">{nota}</p>}
    </div>
  );
}
