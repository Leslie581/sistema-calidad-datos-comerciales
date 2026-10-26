import { useEffect, useMemo, type ReactNode } from "react";
import { SistemaContext } from "../hooks/sistema";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";

/** Consulta el estado real del pipeline: cada 1.5 s mientras corre y cada 20 s en reposo. Sin progreso simulado. */
export function SistemaProvider({ children }: { children: ReactNode }) {
  const { datos, error, recargar } = useApi((s) => api.estadoPipeline(s), []);
  const ejecutando = datos?.ejecutor.estado === "EN_EJECUCION";
  useEffect(() => {
    const t = setInterval(recargar, ejecutando ? 1500 : 20000);
    return () => clearInterval(t);
  }, [ejecutando, recargar]);
  const ciclo = String(datos?.ejecutor.ultimo_resultado?.terminado_en ?? datos?.ultima?.lote_id ?? "");
  const valor = useMemo(() => ({ estado: datos, error, ciclo, refrescar: recargar }), [datos, error, ciclo, recargar]);
  return <SistemaContext.Provider value={valor}>{children}</SistemaContext.Provider>;
}
