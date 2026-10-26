import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "./App";
import { fEntero } from "./lib/format";
import { FIX, instalarApi, json } from "./test/apiMock";

function Ubicacion() {
  const l = useLocation();
  return <output data-testid="ubicacion">{l.pathname + l.search}</output>;
}
function renderApp(ruta = "/") {
  return render(<MemoryRouter initialEntries={[ruta]}><App /><Ubicacion /></MemoryRouter>);
}
const ubicacion = () => screen.getByTestId("ubicacion").textContent;
afterEach(() => vi.unstubAllGlobals());

describe("navegación y estructura", () => {
  it("muestra la bienvenida con la identidad y los datos reales de la última carga", async () => {
    instalarApi();
    renderApp("/");
    expect(await screen.findByRole("heading", { level: 1, name: /Inteligencia comercial/ })).toBeInTheDocument();
    expect(await screen.findByText("Originales intactos")).toBeInTheDocument();
    expect(screen.getAllByText(fEntero(FIX.dashboard.totales.entrada)).length).toBeGreaterThan(0);
    expect(screen.getByText("ventas_online.json")).toBeInTheDocument();
  });

  it("tiene regiones accesibles: enlace de salto, navegación principal y contenido", async () => {
    instalarApi();
    renderApp("/");
    expect(screen.getByRole("link", { name: /Saltar al contenido/ })).toHaveAttribute("href", "#contenido");
    const nav = screen.getByRole("navigation", { name: "Principal" });
    for (const t of ["Inicio", "Panel ejecutivo", "Centro ETL", "Calidad de datos", "Historial y reportes", "Transacciones", "Cuarentena", "Catálogo"]) {
      expect(within(nav).getByRole("link", { name: t })).toBeInTheDocument();
    }
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("search")).toBeInTheDocument();
  });

  it("navega entre secciones y marca la activa", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/");
    await u.click(within(screen.getByRole("navigation", { name: "Principal" })).getByRole("link", { name: "Cuarentena" }));
    expect(await screen.findByRole("heading", { level: 1, name: /Registros apartados/ })).toBeInTheDocument();
    expect(ubicacion()).toBe("/cuarentena");
    expect(within(screen.getByRole("navigation", { name: "Principal" })).getByRole("link", { name: "Cuarentena" })).toHaveAttribute("aria-current", "page");
  });

  it("la búsqueda global lleva a las transacciones con el ID", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/panel");
    await u.type(screen.getByRole("textbox", { name: /Buscar una transacción por ID/ }), "WEB-00508{Enter}");
    await waitFor(() => expect(ubicacion()).toBe("/transacciones?q=WEB-00508"));
  });

  it("muestra una página propia para rutas inexistentes", async () => {
    instalarApi();
    renderApp("/no-existe");
    expect(await screen.findByText("Esta página no existe en KOVA")).toBeInTheDocument();
  });
});

describe("panel ejecutivo", () => {
  it("presenta las métricas oficiales y el indicador compuesto explicado", async () => {
    instalarApi();
    renderApp("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: /Cómo están tus datos comerciales/ })).toBeInTheDocument();
    const salud = FIX.dashboard.salud!;
    expect(await screen.findByText(/¿Cómo se calcula la salud de origen\?/)).toBeInTheDocument();
    expect(screen.getByText(salud.formula, { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/Es un indicador propio de KOVA/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: new RegExp(`Salud de origen`) })).toBeInTheDocument();
    for (const m of FIX.dashboard.motivos.por_codigo) expect(screen.getAllByText(m.codigo).length).toBeGreaterThan(0);
  });

  it("aclara que una transacción con varios motivos se cuenta una vez", async () => {
    instalarApi();
    renderApp("/panel");
    expect(await screen.findByText(/se cuenta una sola vez en el total/)).toBeInTheDocument();
  });

  it("explica cómo conectar cuando la API no responde y permite reintentar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderApp("/panel");
    expect(await screen.findByText("KOVA no puede comunicarse con el servidor")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Reintentar/ }).length).toBeGreaterThan(0);
    expect(screen.getByText(/uvicorn src.api.main:app/)).toBeInTheDocument();
  });

  it("guía al Centro ETL cuando todavía no existe la base", async () => {
    instalarApi({ "/api/dashboard": () => json({ codigo: "BD_NO_ENCONTRADA", mensaje: "Todavía no existe la base de datos. Ejecuta el pipeline desde el Centro ETL." }, 503) });
    renderApp("/panel");
    expect(await screen.findByText("Todavía no hay datos procesados")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al Centro ETL" })).toHaveAttribute("href", "/etl");
  });

  it("muestra un estado vacío cuando la base existe pero no hay cargas", async () => {
    instalarApi({ "/api/dashboard": () => ({ ...FIX.dashboard, hay_datos: false, ultima_ejecucion: null }) });
    renderApp("/panel");
    expect(await screen.findByText("Aún no hay una carga completada")).toBeInTheDocument();
  });
});

describe("transacciones", () => {
  it("lista las transacciones reales con formato MXN", async () => {
    instalarApi();
    renderApp("/transacciones");
    const tabla = await screen.findByRole("table", { name: "Transacciones limpias" });
    const filas = within(tabla).getAllByRole("row");
    expect(filas).toHaveLength(FIX.transacciones.items.length + 1);
    expect(within(tabla).getAllByText(/^\$[\d,]+\.\d{2}$/).length).toBeGreaterThan(5);
    expect(screen.getByText(fEntero(FIX.transacciones.total))).toBeInTheDocument();
  });

  it("filtra por canal y por texto enviando parámetros a la API", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    await u.selectOptions(screen.getByLabelText("Canal"), "ONLINE");
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/transacciones" && l.params.get("canal") === "ONLINE")).toBe(true));
    await u.type(screen.getByRole("searchbox", { name: /Buscar por ID/ }), "WEB-005");
    await waitFor(() => expect(llamadas.some((l) => l.params.get("q") === "WEB-005")).toBe(true), { timeout: 3000 });
    expect(ubicacion()).toContain("canal=ONLINE");
  });

  it("ordena al pulsar un encabezado y expone aria-sort", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    await u.click(screen.getByRole("button", { name: /Importe MXN/ }));
    await waitFor(() => expect(llamadas.some((l) => l.params.get("orden") === "importe")).toBe(true));
    expect(screen.getByRole("columnheader", { name: /Importe MXN/ })).toHaveAttribute("aria-sort", "descending");
  });

  it("avisa y permite quitar filtros cuando nada coincide", async () => {
    instalarApi({ "/api/transacciones": () => ({ ...FIX.transacciones, items: [], total: 0, paginas: 0 }) });
    renderApp("/transacciones?q=ZZZ");
    expect(await screen.findByText("Ninguna transacción coincide con los filtros")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Quitar filtros/ }).length).toBeGreaterThan(0);
  });

  it("abre el recorrido de una transacción, lo muestra lado a lado y se cierra con Escape", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    const primera = FIX.transacciones.items[0].id_transaccion;
    await u.click(screen.getByRole("button", { name: `Ver recorrido de ${primera}` }));
    const dialogo = await screen.findByRole("dialog");
    expect(ubicacion()).toBe(`/transacciones/${primera}`);
    expect(await within(dialogo).findByText("Lado a lado")).toBeInTheDocument();
    for (const e of FIX.transaccionDetalle.trazabilidad) expect(within(dialogo).getByRole("heading", { level: 3, name: (n) => n.endsWith(e.titulo) })).toBeInTheDocument();
    expect(within(dialogo).getByRole("table", { name: /valores originales, normalizados, corregidos y con capping/ })).toBeInTheDocument();
    expect(within(dialogo).getByText(/Vista de solo consulta/)).toBeInTheDocument();
    await u.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(ubicacion()).toBe("/transacciones");
  });

  it("muestra un error comprensible si el detalle no existe", async () => {
    instalarApi({ "/api/transacciones/WEB-99999": () => json({ codigo: "TRANSACCION_NO_ENCONTRADA", mensaje: "No existe la transacción limpia «WEB-99999»." }, 404) });
    renderApp("/transacciones/WEB-99999");
    expect(await screen.findByText("No existe la transacción limpia «WEB-99999».")).toBeInTheDocument();
  });
});

describe("cuarentena", () => {
  it("resume los rechazos y filtra por motivo con chips accesibles", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/cuarentena");
    expect(await screen.findByText(/cada una se cuenta una vez/)).toBeInTheDocument();
    const chip = screen.getByRole("button", { name: /PRODUCTO_HUERFANO/ });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await u.click(chip);
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/cuarentena" && l.params.get("codigo") === "PRODUCTO_HUERFANO")).toBe(true));
    expect(screen.getByRole("button", { name: /PRODUCTO_HUERFANO/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("abre el detalle con todos los motivos, el registro crudo y la trazabilidad (solo lectura)", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/cuarentena");
    const tabla = await screen.findByRole("table", { name: "Registros en cuarentena" });
    const primero = FIX.cuarentena.items[0];
    await u.click(within(tabla).getByRole("button", { name: new RegExp(`error ${primero.id_error}$`) }));
    const dialogo = await screen.findByRole("dialog");
    expect(await within(dialogo).findByText("Por qué se apartó")).toBeInTheDocument();
    for (const d of FIX.cuarentenaDetalle.detalle) expect(within(dialogo).getAllByText(d.codigo).length).toBeGreaterThan(0);
    expect(within(dialogo).getByText("Registro crudo")).toBeInTheDocument();
    expect(within(dialogo).getByText(/no edita los datos oficiales ni reinserta registros/)).toBeInTheDocument();
    expect(within(dialogo).queryByRole("button", { name: /reinsert|editar|corregir/i })).not.toBeInTheDocument();
  });

  it("indica cuando ningún registro cumple los filtros", async () => {
    instalarApi({ "/api/cuarentena": () => ({ ...FIX.cuarentena, items: [], total: 0, paginas: 0 }) });
    renderApp("/cuarentena?codigo=ERROR_INESPERADO");
    expect(await screen.findByText("Sin registros con esos filtros")).toBeInTheDocument();
  });
});

describe("catálogo", () => {
  it("muestra las tarjetas del catálogo oficial sin presentar ilustraciones como fotografías", async () => {
    instalarApi();
    renderApp("/catalogo");
    expect(await screen.findByRole("heading", { level: 1, name: "Catálogo de productos" })).toBeInTheDocument();
    expect(await screen.findByText(FIX.catalogo.items[0].nombre_producto)).toBeInTheDocument();
    expect(screen.getByText(/no incluye fotografías de producto/)).toBeInTheDocument();
    expect(screen.getByText(/no existen/)).toBeInTheDocument();
  });

  it("alterna a la vista de tabla y filtra por categoría", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/catalogo");
    await screen.findByText(FIX.catalogo.items[0].nombre_producto);
    await u.click(screen.getByRole("radio", { name: /Tabla/ }));
    expect(await screen.findByRole("table", { name: "Catálogo oficial de productos" })).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: new RegExp(FIX.catalogo.por_categoria[0].categoria) }));
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/catalogo" && l.params.get("categoria") === FIX.catalogo.por_categoria[0].categoria)).toBe(true));
  });
});

describe("centro ETL", () => {
  it("representa las siete fases con su estado y duración medidos", async () => {
    instalarApi();
    renderApp("/etl");
    expect(await screen.findByRole("heading", { level: 1, name: /recorrido completo de tus datos/ })).toBeInTheDocument();
    const diagrama = screen.getByRole("group", { name: /Flujo del pipeline/ });
    expect(within(diagrama).getAllByRole("button")).toHaveLength(7);
    for (const f of FIX.estadoPipeline.fases) expect(within(diagrama).getByRole("button", { name: new RegExp(`Fase ${f.numero},.*completada`, "i") })).toBeInTheDocument();
    expect(screen.getByText(/no emite progreso|no simula progreso/)).toBeInTheDocument();
  });

  it("al elegir una fase muestra sus métricas verificables", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/etl");
    const diagrama = await screen.findByRole("group", { name: /Flujo del pipeline/ });
    await u.click(within(diagrama).getByRole("button", { name: /Fase 6/ }));
    expect(await screen.findByRole("heading", { level: 2, name: "Pydantic y cuarentena" })).toBeInTheDocument();
    expect(screen.getByText("Transacciones válidas")).toBeInTheDocument();
  });

  it("pide confirmación antes de ejecutar y envía la solicitud real", async () => {
    const { llamadas } = instalarApi({ "POST /api/pipeline/ejecutar": () => json({ iniciado_en: "2026-10-26T01:00:00", mensaje: "ok" }, 202) });
    const u = userEvent.setup();
    renderApp("/etl");
    await u.click(await screen.findByRole("button", { name: "Ejecutar pipeline" }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(within(dialogo).getByText(/reemplazará/)).toBeInTheDocument();
    expect(llamadas.some((l) => l.metodo === "POST")).toBe(false);          // todavía no se ejecutó nada
    await u.click(within(dialogo).getByRole("button", { name: "Cancelar" }));
    expect(llamadas.some((l) => l.metodo === "POST")).toBe(false);
    await u.click(screen.getByRole("button", { name: "Ejecutar pipeline" }));
    await u.click(await within(await screen.findByRole("alertdialog")).findByRole("button", { name: "Sí, ejecutar" }));
    await waitFor(() => expect(llamadas.filter((l) => l.metodo === "POST")).toHaveLength(1));
    expect(JSON.parse(llamadas.find((l) => l.metodo === "POST")!.cuerpo!)).toEqual({ confirmar: true });
  });

  it("muestra el rechazo cuando ya hay una ejecución en curso", async () => {
    instalarApi({ "POST /api/pipeline/ejecutar": () => json({ codigo: "PIPELINE_EN_EJECUCION", mensaje: "Ya hay una ejecución en curso. Espera a que termine." }, 409) });
    const u = userEvent.setup();
    renderApp("/etl");
    await u.click(await screen.findByRole("button", { name: "Ejecutar pipeline" }));
    await u.click(await screen.findByRole("button", { name: "Sí, ejecutar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ya hay una ejecución en curso");
  });

  it("deshabilita el botón y no inventa progreso mientras el pipeline corre", async () => {
    instalarApi({ "/api/pipeline/estado": () => ({ ...FIX.estadoPipeline, ejecutor: { estado: "EN_EJECUCION", iniciado_en: new Date().toISOString(), lote_en_curso: null, ultimo_resultado: null } }) });
    renderApp("/etl");
    expect(await screen.findByRole("button", { name: "Ejecutando…" })).toBeDisabled();
    expect(screen.getByText(/no emite progreso por fase/)).toBeInTheDocument();
    expect(screen.queryByText(/\d+\s?%\s+completado/i)).not.toBeInTheDocument();
  });

  it("informa el resultado real cuando termina una ejecución, también si falló", async () => {
    instalarApi({ "/api/pipeline/estado": () => ({ ...FIX.estadoPipeline, ejecutor: { estado: "INACTIVO", iniciado_en: null, lote_en_curso: "L1", ultimo_resultado: {
      estado: "FALLIDO", etapa_fallida: "1. Extracción", error: "ventas_online.json no es un JSON válido", terminado_en: "2026-10-26T01:00:03" } } }) });
    renderApp("/etl");
    expect(await screen.findByText(/La ejecución falló en «1. Extracción»: ventas_online.json no es un JSON válido/)).toBeInTheDocument();
  });
});

describe("historial, reportes y calidad", () => {
  it("lista las ejecuciones y no muestra una fallida como exitosa", async () => {
    const base = FIX.ejecuciones.items[0];
    const fallida = { ...base, lote_id: "L20261026-010101-ffff", estado: "FALLIDO", etapa_fallida: "1. Extracción", error: "JSON roto", filas_limpias: null, filas_cuarentena: null, tasa_aceptacion: null, duracion_s: 0.05 };
    instalarApi({ "/api/ejecuciones": () => ({ ...FIX.ejecuciones, items: [fallida, base], total: 2 }) });
    renderApp("/historial");
    const tabla = await screen.findByRole("table", { name: "Historial de ejecuciones" });
    const fila = within(tabla).getByText("L20261026-010101-ffff").closest("tr")!;
    expect(within(fila).getByText("Fallida")).toBeInTheDocument();
    expect(within(fila).queryByText("Completada")).not.toBeInTheDocument();
    expect(within(fila).getByText(/en «1. Extracción»/)).toBeInTheDocument();
  });

  it("permite ver y descargar los reportes reales de una etapa", async () => {
    instalarApi();
    renderApp("/historial");
    const archivo = FIX.reportes.grupos.find((g) => g.carpeta === "etapa_nono")!.archivos[0];
    const abrir = await screen.findByRole("link", { name: `Abrir ${archivo.nombre}` });
    expect(abrir).toHaveAttribute("href", archivo.url);
    expect(screen.getByRole("link", { name: `Descargar ${archivo.nombre}` })).toHaveAttribute("href", `${archivo.url}?descargar=true`);
  });

  it("la pantalla de calidad advierte que MCAR no está demostrado de forma absoluta y separa original, corregido y tratado", async () => {
    instalarApi();
    renderApp("/calidad");
    expect(await screen.findByText(/COMPATIBLES con MCAR/)).toBeInTheDocument();
    expect(screen.getByText(/no demuestra MCAR|no demuestra/)).toBeInTheDocument();
    for (const t of ["Originales", "Corregidos", "Tratados"]) expect(screen.getByText(t)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Importe MXN: Q1/ })).toBeInTheDocument();
    expect(screen.getAllByRole("img").some((i) => i.getAttribute("src")?.includes("boxplot_importe_mxn.png"))).toBe(true);
  });

  it("sigue funcionando sin los reportes de la etapa de Leslie", async () => {
    instalarApi({ "/api/calidad": () => ({ ...FIX.calidad, perfil_antes: null, faltantes: null, antes_despues: null, graficas: [] }) });
    renderApp("/calidad");
    expect(await screen.findByText(/Lo que se corrigió, sin borrar el original/)).toBeInTheDocument();
    expect(screen.queryByText("Antes y después")).not.toBeInTheDocument();
  });
});
