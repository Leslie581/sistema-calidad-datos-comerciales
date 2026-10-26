import { vi } from "vitest";
import calidad from "./fixtures/calidad.json";
import catalogo from "./fixtures/catalogo.json";
import cuarentena from "./fixtures/cuarentena.json";
import cuarentenaDetalle from "./fixtures/cuarentena_detalle.json";
import dashboard from "./fixtures/dashboard.json";
import ejecucionDetalle from "./fixtures/ejecucion_detalle.json";
import ejecuciones from "./fixtures/ejecuciones.json";
import estadoPipeline from "./fixtures/estado_pipeline.json";
import facetas from "./fixtures/facetas.json";
import reportes from "./fixtures/reportes.json";
import salud from "./fixtures/salud.json";
import transaccionDetalle from "./fixtures/transaccion_detalle.json";
import transacciones from "./fixtures/transacciones.json";

/** Respuestas REALES de la API (generadas por scripts/generar_fixtures_frontend.py), no datos inventados a mano. */
export const FIX = { calidad, catalogo, cuarentena, cuarentenaDetalle, dashboard, ejecucionDetalle, ejecuciones, estadoPipeline, facetas, reportes, salud, transaccionDetalle, transacciones };

export interface Llamada { url: string; ruta: string; params: URLSearchParams; metodo: string; cuerpo?: string }
export type Manejador = (llamada: Llamada) => unknown | Response | undefined;

export const json = (cuerpo: unknown, estado = 200) => new Response(JSON.stringify(cuerpo), { status: estado, headers: { "Content-Type": "application/json" } });

/** Sustituye fetch por un servidor simulado con los fixtures. `sobrescribir` permite cambiar rutas concretas (errores, estados). */
export function instalarApi(sobrescribir: Record<string, Manejador> = {}) {
  const llamadas: Llamada[] = [];
  const rutas: Record<string, Manejador> = {
    "/api/salud": () => FIX.salud,
    "/api/dashboard": () => FIX.dashboard,
    "/api/facetas": () => FIX.facetas,
    "/api/transacciones": () => FIX.transacciones,
    "/api/cuarentena": () => FIX.cuarentena,
    "/api/catalogo": () => FIX.catalogo,
    "/api/calidad": () => FIX.calidad,
    "/api/ejecuciones": () => FIX.ejecuciones,
    "/api/reportes": () => FIX.reportes,
    "/api/pipeline/estado": () => FIX.estadoPipeline,
    ...sobrescribir,
  };
  const mock = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit) => {
    const u = new URL(String(entrada), "http://localhost");
    const llamada: Llamada = { url: u.pathname + u.search, ruta: u.pathname, params: u.searchParams, metodo: init?.method ?? "GET", cuerpo: init?.body as string | undefined };
    llamadas.push(llamada);
    let manejador = rutas[`${llamada.metodo} ${u.pathname}`] ?? rutas[u.pathname];
    if (!manejador && /^\/api\/transacciones\/[^/]+$/.test(u.pathname)) manejador = () => FIX.transaccionDetalle;
    if (!manejador && /^\/api\/cuarentena\/\d+$/.test(u.pathname)) manejador = () => FIX.cuarentenaDetalle;
    if (!manejador && /^\/api\/ejecuciones\/L[^/]+$/.test(u.pathname)) manejador = () => FIX.ejecucionDetalle;
    if (!manejador) return json({ codigo: "RUTA_NO_ENCONTRADA", mensaje: `sin manejador para ${u.pathname}` }, 404);
    const r = manejador(llamada);
    return r instanceof Response ? r : json(r);
  });
  vi.stubGlobal("fetch", mock);
  return { llamadas, mock };
}
