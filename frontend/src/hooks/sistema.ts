import { createContext, useContext } from "react";
import type { ErrorApi } from "../services/api";
import type { EstadoPipeline } from "../services/tipos";

export interface Sistema {
  estado?: EstadoPipeline;
  error?: ErrorApi;
  /** Cambia cada vez que termina una ejecución del pipeline: las páginas lo usan como dependencia para volver a consultar. */
  ciclo: string;
  refrescar: () => void;
}

export const SistemaContext = createContext<Sistema>({ ciclo: "", refrescar: () => {} });
export const useSistema = () => useContext(SistemaContext);
