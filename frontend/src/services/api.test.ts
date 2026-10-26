import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ErrorApi, querystring } from "./api";
import { FIX, instalarApi, json } from "../test/apiMock";

afterEach(() => vi.unstubAllGlobals());

describe("cliente de la API", () => {
  it("construye querystrings omitiendo valores vacíos y escapando texto", () => {
    expect(querystring({ q: "WEB 00508", canal: "", pagina: 2, vacio: undefined, nulo: null })).toBe("?q=WEB+00508&pagina=2");
    expect(querystring({})).toBe("");
    expect(querystring({ q: "'; DROP TABLE x;--" })).toContain("%27%3B");
  });

  it("devuelve datos tipados cuando la respuesta es correcta", async () => {
    const { llamadas } = instalarApi();
    const d = await api.dashboard();
    expect(d.totales.entrada).toBe(FIX.dashboard.totales.entrada);
    expect(llamadas[0].url).toBe("/api/dashboard");
  });

  it("codifica el ID de la transacción en la ruta", async () => {
    const { llamadas } = instalarApi();
    await api.transaccion("POS 2026/1");
    expect(llamadas[0].ruta).toBe("/api/transacciones/POS%202026%2F1");
  });

  it("traduce los errores {codigo, mensaje} de FastAPI", async () => {
    instalarApi({ "/api/dashboard": () => json({ codigo: "BD_NO_ENCONTRADA", mensaje: "Todavía no existe la base de datos." }, 503) });
    const e = await api.dashboard().catch((x) => x);
    expect(e).toBeInstanceOf(ErrorApi);
    expect(e).toMatchObject({ codigo: "BD_NO_ENCONTRADA", estado: 503, message: "Todavía no existe la base de datos." });
    expect(e.sinBase).toBe(true);
    expect(e.sinConexion).toBe(false);
  });

  it("distingue un servidor caído de un error de la API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const e = await api.dashboard().catch((x) => x);
    expect(e.sinConexion).toBe(true);
    expect(e.message).toMatch(/FastAPI/);
  });

  it("maneja respuestas de error que no son JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })));
    const e = await api.dashboard().catch((x) => x);
    expect(e).toMatchObject({ codigo: "ERROR_HTTP", estado: 502 });
  });

  it("no oculta los AbortError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(Object.assign(new Error("abort"), { name: "AbortError" })));
    await expect(api.dashboard()).rejects.toMatchObject({ name: "AbortError" });
  });

  it("ejecutar el pipeline envía la confirmación explícita por POST", async () => {
    const { llamadas } = instalarApi({ "POST /api/pipeline/ejecutar": () => json({ iniciado_en: "2026-10-26T01:00:00", mensaje: "ok" }, 202) });
    await api.ejecutarPipeline();
    expect(llamadas[0]).toMatchObject({ metodo: "POST", ruta: "/api/pipeline/ejecutar" });
    expect(JSON.parse(llamadas[0].cuerpo!)).toEqual({ confirmar: true });
  });
});
