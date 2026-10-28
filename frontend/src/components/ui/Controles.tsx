import { useId, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, ChevronsUpDown, ArrowDown, ArrowUp, Search, X } from "lucide-react";
import { fEntero } from "../../lib/format";

export function Buscador({ valor, alCambiar, etiqueta, placeholder }: { valor: string; alCambiar: (v: string) => void; etiqueta: string; placeholder?: string }) {
  const id = useId();
  return (
    <div className="relative min-w-[220px] flex-1">
      <label htmlFor={id} className="sr-only">{etiqueta}</label>
      <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-suave" />
      <input id={id} type="search" value={valor} onChange={(e) => alCambiar(e.target.value)} placeholder={placeholder}
        className="h-11 w-full rounded-full border border-borde-fuerte bg-blanco pl-11 pr-10 text-sm text-grafito placeholder:text-suave/80 focus:border-petroleo" />
      {valor && (
        <button type="button" onClick={() => alCambiar("")} aria-label="Limpiar búsqueda"
          className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-full text-suave hover:bg-superficie-2"><X size={15} aria-hidden="true" /></button>
      )}
    </div>
  );
}

export function Seleccion({ etiqueta, valor, alCambiar, opciones, todas = "Todas" }: {
  etiqueta: string; valor: string; alCambiar: (v: string) => void; opciones: { valor: string; texto?: string }[] | string[]; todas?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="etiqueta">{etiqueta}</label>
      <select id={id} value={valor} onChange={(e) => alCambiar(e.target.value)}
        className="h-11 rounded-full border border-borde-fuerte bg-blanco px-4 text-sm font-medium text-grafito focus:border-petroleo">
        <option value="">{todas}</option>
        {opciones.map((o) => { const x = typeof o === "string" ? { valor: o } : o; return <option key={x.valor} value={x.valor}>{x.texto ?? x.valor}</option>; })}
      </select>
    </div>
  );
}

export function CampoFecha({ etiqueta, valor, alCambiar, min, max }: { etiqueta: string; valor: string; alCambiar: (v: string) => void; min?: string; max?: string }) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="etiqueta">{etiqueta}</label>
      <input id={id} type="date" value={valor} min={min} max={max} onChange={(e) => alCambiar(e.target.value)}
        className="h-11 rounded-full border border-borde-fuerte bg-blanco px-4 text-sm text-grafito focus:border-petroleo" />
    </div>
  );
}

/** Control segmentado (radiogroup accesible): ej. canal o vista tarjetas/tabla. */
export function Segmentado<T extends string>({ etiqueta, valor, alCambiar, opciones }: {
  etiqueta: string; valor: T; alCambiar: (v: T) => void; opciones: { valor: T; texto: ReactNode; aria?: string }[];
}) {
  return (
    <div role="radiogroup" aria-label={etiqueta} className="inline-flex max-w-full flex-wrap rounded-[1.4rem] border border-borde-fuerte bg-blanco p-1">
      {opciones.map((o) => (
        <button key={o.valor} type="button" role="radio" aria-checked={valor === o.valor} aria-label={o.aria} onClick={() => alCambiar(o.valor)}
          className={`min-h-9 rounded-full px-3 text-sm font-bold transition-colors sm:px-4 ${valor === o.valor ? "bg-bosque text-blanco" : "text-suave hover:text-bosque"}`}>
          {o.texto}
        </button>
      ))}
    </div>
  );
}

export function Paginacion({ pagina, paginas, total, tam, alCambiar }: { pagina: number; paginas: number; total: number; tam: number; alCambiar: (p: number) => void }) {
  if (!total) return null;
  const desde = (pagina - 1) * tam + 1, hasta = Math.min(total, pagina * tam);
  return (
    <nav aria-label="Paginación" className="flex flex-wrap items-center justify-between gap-3 border-t border-borde px-4 py-3 text-sm">
      <p className="num text-suave" aria-live="polite">{fEntero(desde)}–{fEntero(hasta)} de {fEntero(total)}</p>
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => alCambiar(pagina - 1)} disabled={pagina <= 1} aria-label="Página anterior"
          className="grid size-10 place-items-center rounded-full border border-borde-fuerte bg-blanco text-bosque disabled:opacity-40"><ChevronLeft size={18} aria-hidden="true" /></button>
        <span className="num min-w-24 text-center font-bold text-bosque">Página {pagina} / {Math.max(paginas, 1)}</span>
        <button type="button" onClick={() => alCambiar(pagina + 1)} disabled={pagina >= paginas} aria-label="Página siguiente"
          className="grid size-10 place-items-center rounded-full border border-borde-fuerte bg-blanco text-bosque disabled:opacity-40"><ChevronRight size={18} aria-hidden="true" /></button>
      </div>
    </nav>
  );
}

/** Encabezado de tabla ordenable (botón con aria-sort en la celda). */
export function ThOrden({ clave, orden, direccion, alOrdenar, children, der = false }: {
  clave: string; orden: string; direccion: "asc" | "desc"; alOrdenar: (c: string) => void; children: ReactNode; der?: boolean;
}) {
  const activo = orden === clave;
  const Icono = !activo ? ChevronsUpDown : direccion === "asc" ? ArrowUp : ArrowDown;
  return (
    <th scope="col" aria-sort={activo ? (direccion === "asc" ? "ascending" : "descending") : "none"} className={der ? "der" : ""}>
      <button type="button" onClick={() => alOrdenar(clave)} className={`inline-flex items-center gap-1 uppercase tracking-[0.08em] ${activo ? "text-bosque" : ""}`}>
        {children}<Icono size={13} aria-hidden="true" className={activo ? "" : "opacity-50"} />
      </button>
    </th>
  );
}
