import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/** Filtros sincronizados con la URL (compartibles, y la búsqueda global puede llevar `?q=`). Cambiar un filtro vuelve a la página 1. */
export function useFiltros(porDefecto: Record<string, string>) {
  const [params, setParams] = useSearchParams();
  const valor = (k: string) => params.get(k) ?? porDefecto[k] ?? "";
  const cambiar = useCallback(
    (cambios: Record<string, string>, conservarPagina = false) => {
      setParams((prev) => {
        const n = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(cambios)) {
          if (v === "" || v === porDefecto[k]) n.delete(k);
          else n.set(k, v);
        }
        if (!conservarPagina && !("pagina" in cambios)) n.delete("pagina");
        return n;
      }, { replace: true });
    },
    [setParams, porDefecto],
  );
  const limpiar = useCallback(() => setParams({}, { replace: true }), [setParams]);
  const hayFiltros = [...params.keys()].some((k) => k !== "pagina" && params.get(k) !== (porDefecto[k] ?? ""));
  return { valor, cambiar, limpiar, hayFiltros, pagina: Math.max(1, Number(params.get("pagina") ?? 1) || 1) };
}
