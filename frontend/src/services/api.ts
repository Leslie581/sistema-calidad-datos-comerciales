import type {
  Calidad, CuarentenaResumen, Dashboard, DetalleCuarentena, DetalleEjecucion, DetalleTransaccion, Ejecucion,
  EstadoPipeline, Facetas, ListaReportes, OpcionesComerciales, Pagina, PaginaCatalogo, PaginaTransacciones, ProductosComerciales,
  ResumenComercial, Salud, TendenciaComercial,
} from "./tipos";

/** Error con forma estable {codigo, mensaje}: viene de la API o describe un fallo de conexión. */
export class ErrorApi extends Error {
  codigo: string;
  estado: number;
  constructor(codigo: string, mensaje: string, estado = 0) {
    super(mensaje);
    this.codigo = codigo;
    this.estado = estado;
  }
  get sinBase() {
    return this.codigo === "BD_NO_ENCONTRADA" || this.codigo === "BD_SIN_ESQUEMA";
  }
  get sinConexion() {
    return this.codigo === "SIN_CONEXION";
  }
}

type Params = Record<string, string | number | boolean | undefined | null>;

export function querystring(params?: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function pedir<T>(ruta: string, init?: RequestInit, senal?: AbortSignal): Promise<T> {
  let r: Response;
  try {
    r = await fetch(ruta, {
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
      signal: senal,
      ...init,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ErrorApi("SIN_CONEXION", "No se pudo conectar con el servidor de KOVA. Verifica que FastAPI esté en ejecución (puerto 8000).");
  }
  if (!r.ok) {
    let cuerpo: { codigo?: string; mensaje?: string } = {};
    try {
      cuerpo = await r.json();
    } catch {
      /* la respuesta no era JSON */
    }
    throw new ErrorApi(cuerpo.codigo ?? "ERROR_HTTP", cuerpo.mensaje ?? `El servidor respondió ${r.status}.`, r.status);
  }
  return (await r.json()) as T;
}

const get = <T,>(ruta: string, params?: Params, senal?: AbortSignal) => pedir<T>(`/api${ruta}${querystring(params)}`, undefined, senal);

export const api = {
  comercialOpciones: (s?: AbortSignal) => get<OpcionesComerciales>("/comercial/opciones", undefined, s),
  comercialResumen: (p: Params, s?: AbortSignal) => get<ResumenComercial>("/comercial/resumen", p, s),
  comercialTendencia: (p: Params, s?: AbortSignal) => get<TendenciaComercial>("/comercial/tendencia", p, s),
  comercialProductos: (p: Params, s?: AbortSignal) => get<ProductosComerciales>("/comercial/productos", p, s),
  salud: (s?: AbortSignal) => get<Salud>("/salud", undefined, s),
  dashboard: (s?: AbortSignal) => get<Dashboard>("/dashboard", undefined, s),
  facetas: (s?: AbortSignal) => get<Facetas>("/facetas", undefined, s),
  transacciones: (p: Params, s?: AbortSignal) => get<PaginaTransacciones>("/transacciones", p, s),
  transaccion: (id: string, s?: AbortSignal) => get<DetalleTransaccion>(`/transacciones/${encodeURIComponent(id)}`, undefined, s),
  cuarentena: (p: Params, s?: AbortSignal) => get<Pagina<CuarentenaResumen>>("/cuarentena", p, s),
  cuarentenaDetalle: (id: number | string, s?: AbortSignal) => get<DetalleCuarentena>(`/cuarentena/${id}`, undefined, s),
  catalogo: (p: Params, s?: AbortSignal) => get<PaginaCatalogo>("/catalogo", p, s),
  calidad: (s?: AbortSignal) => get<Calidad>("/calidad", undefined, s),
  ejecuciones: (p?: Params, s?: AbortSignal) => get<{ items: Ejecucion[]; total: number; nota: string }>("/ejecuciones", p, s),
  ejecucion: (lote: string, s?: AbortSignal) => get<DetalleEjecucion>(`/ejecuciones/${encodeURIComponent(lote)}`, undefined, s),
  reportes: (s?: AbortSignal) => get<ListaReportes>("/reportes", undefined, s),
  estadoPipeline: (s?: AbortSignal) => get<EstadoPipeline>("/pipeline/estado", undefined, s),
  ejecutarPipeline: () =>
    pedir<{ iniciado_en: string; mensaje: string }>("/api/pipeline/ejecutar", { method: "POST", body: JSON.stringify({ confirmar: true }) }),
};
