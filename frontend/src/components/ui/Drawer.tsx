import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

const FOCALIZABLES = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

/** Panel lateral modal accesible: role=dialog, Esc cierra, foco atrapado y devuelto al elemento que lo abrió. */
export function Drawer({ abierto, titulo, subtitulo, alCerrar, children, ancho = "max-w-[760px]" }: {
  abierto: boolean; titulo: string; subtitulo?: string; alCerrar: () => void; children: ReactNode; ancho?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const previo = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLElement>("[data-cerrar]")?.focus();
    const teclas = (e: KeyboardEvent) => {
      if (e.key === "Escape") return alCerrar();
      if (e.key !== "Tab" || !panel.current) return;
      const lista = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCALIZABLES));
      if (!lista.length) return;
      const primero = lista[0], ultimo = lista[lista.length - 1];
      if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
    };
    document.addEventListener("keydown", teclas);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", teclas);
      document.body.style.overflow = "";
      previo?.focus?.();
    };
  }, [abierto, alCerrar]);
  if (!abierto) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="entra-suave absolute inset-0 bg-bosque/45 backdrop-blur-[2px]" onClick={alCerrar} aria-hidden="true" />
      <div ref={panel} role="dialog" aria-modal="true" aria-label={titulo}
        className={`drawer-entra relative flex h-full w-full ${ancho} flex-col bg-crema shadow-elevada sm:rounded-l-[2rem]`}>
        <header className="flex items-start justify-between gap-4 border-b border-borde px-6 py-5">
          <div className="min-w-0">
            {subtitulo && <p className="etiqueta mb-1">{subtitulo}</p>}
            <h2 className="titular break-words text-2xl text-bosque">{titulo}</h2>
          </div>
          <button data-cerrar type="button" onClick={alCerrar} aria-label="Cerrar panel"
            className="grid size-11 shrink-0 place-items-center rounded-full border border-borde-fuerte bg-blanco text-bosque transition hover:bg-superficie-2">
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <div className="scroll-fino flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

/** Diálogo de confirmación centrado (misma accesibilidad). */
export function DialogoConfirmar({ abierto, titulo, children, textoConfirmar, alConfirmar, alCancelar, peligro = false }: {
  abierto: boolean; titulo: string; children: ReactNode; textoConfirmar: string; alConfirmar: () => void; alCancelar: () => void; peligro?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    const previo = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("[data-cancelar]")?.focus();
    const teclas = (e: KeyboardEvent) => {
      if (e.key === "Escape") return alCancelar();
      if (e.key !== "Tab" || !ref.current) return;
      const lista = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCALIZABLES));
      const primero = lista[0], ultimo = lista[lista.length - 1];
      if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
    };
    document.addEventListener("keydown", teclas);
    return () => { document.removeEventListener("keydown", teclas); previo?.focus?.(); };
  }, [abierto, alCancelar]);
  if (!abierto) return null;
  return createPortal(
    <div className="fixed inset-0 z-[60] grid place-items-center p-4">
      <div className="entra-suave absolute inset-0 bg-bosque/50 backdrop-blur-[2px]" onClick={alCancelar} aria-hidden="true" />
      <div ref={ref} role="alertdialog" aria-modal="true" aria-label={titulo} className="entra panel relative w-full max-w-md p-6 shadow-elevada">
        <h2 className="titular text-2xl text-bosque">{titulo}</h2>
        <div className="mt-3 space-y-2 text-[0.95rem] text-suave">{children}</div>
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button data-cancelar type="button" onClick={alCancelar}
            className="min-h-11 rounded-full border border-borde-fuerte bg-blanco px-5 text-sm font-bold text-bosque hover:bg-superficie-2">Cancelar</button>
          <button type="button" onClick={alConfirmar}
            className={`min-h-11 rounded-full px-5 text-sm font-bold text-blanco ${peligro ? "bg-coral-texto" : "bg-bosque hover:bg-petroleo"}`}>{textoConfirmar}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
