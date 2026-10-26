import { useId } from "react";

/**
 * Isotipo KOVA: cuatro módulos que convergen en un nodo ámbar.
 * Idea: dos canales (físico y digital) × dos estados (dato original / dato confiable) que se unen en un punto de control.
 * Dibujado en SVG propio; las cuatro piezas tienen la esquina exterior redondeada y la interior casi recta, como pétalos.
 */
export function Isotipo({ tam = 40, fondo = "transparente", titulo = "KOVA", className = "" }: {
  tam?: number;
  fondo?: "transparente" | "bosque";
  titulo?: string;
  className?: string;
}) {
  const id = useId();
  const claro = fondo === "bosque" || fondo === "transparente";
  return (
    <svg width={tam} height={tam} viewBox="0 0 64 64" role="img" aria-labelledby={id} className={className}>
      <title id={id}>{titulo}</title>
      {fondo === "bosque" && <rect width="64" height="64" rx="16" fill="#17352D" />}
      <path d="M14 30V22a8 8 0 0 1 8-8h8v14a2 2 0 0 1-2 2H14z" fill={claro ? "#B8E8CE" : "#215548"} />
      <path d="M34 14h8a8 8 0 0 1 8 8v8H36a2 2 0 0 1-2-2V14z" fill={claro ? "#FDFCFA" : "#17352D"} />
      <path d="M14 34h14a2 2 0 0 1 2 2v14h-8a8 8 0 0 1-8-8v-8z" fill={claro ? "#FDFCFA" : "#17352D"} fillOpacity=".62" />
      <path d="M34 36a2 2 0 0 1 2-2h14v8a8 8 0 0 1-8 8h-8V36z" fill={claro ? "#B8E8CE" : "#215548"} fillOpacity=".62" />
      <circle cx="32" cy="32" r="4.4" fill="#D99B45" stroke={fondo === "bosque" ? "#17352D" : "#F7F6F0"} strokeWidth="2.6" />
    </svg>
  );
}

/** Wordmark: KOVA en tipografía display con interletraje abierto + el isotipo. */
export function Logotipo({ oscuro = false, compacto = false }: { oscuro?: boolean; compacto?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <Isotipo tam={compacto ? 32 : 40} fondo={oscuro ? "transparente" : "bosque"} />
      {!compacto && (
        <span className={`font-display text-[1.7rem] font-extrabold leading-none tracking-[0.14em] ${oscuro ? "text-blanco" : "text-bosque"}`}>
          KOVA
        </span>
      )}
    </span>
  );
}

/** Marca de agua decorativa: el isotipo grande y muy tenue (no interfiere con la lectura). */
export function MarcaDeAgua({ className = "", opacidad = 0.07 }: { className?: string; opacidad?: number }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none absolute select-none ${className}`} style={{ opacity: opacidad }}>
      <Isotipo tam={360} fondo="transparente" titulo="" />
    </div>
  );
}
