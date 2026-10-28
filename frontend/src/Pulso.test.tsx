import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import App from "./App";
import { Variacion } from "./components/pulso/Pulso";
import { fEntero, fMXN } from "./lib/format";
import { FIX, instalarApi, json } from "./test/apiMock";

function Ubicacion() {
  const l = useLocation();
  return <output data-testid="ubicacion">{l.pathname + l.search}</output>;
}
function renderApp(ruta: string) {
  return render(<MemoryRouter initialEntries={[ruta]}><App /><Ubicacion /></MemoryRouter>);
}
const ubicacion = () => screen.getByTestId("ubicacion").textContent;
const R = FIX.comercialResumen;
afterEach(() => vi.unstubAllGlobals());

describe("Pulso comercial · contenido", () => {
  it("muestra importe, fechas efectivas, período parcial y comparación con datos reales", async () => {
    instalarApi();
    renderApp("/pulso-comercial");
    expect(await screen.findByRole("heading", { level: 1, name: "Pulso comercial" })).toBeInTheDocument();
    const fechas = await screen.findByLabelText("Fechas efectivas");
    expect(within(fechas).getByText(R.periodo.etiqueta)).toBeInTheDocument();
    expect(within(fechas).getByText(/Período parcial/)).toBeInTheDocument();
    expect(within(fechas).getByText(new RegExp(`frente a ${R.anterior!.etiqueta}`))).toBeInTheDocument();
    expect(await screen.findByText(R.diagnostico.titular)).toBeInTheDocument();
    expect(screen.getAllByText(/antes \$/).length).toBeGreaterThan(0);
  });

  it("explica el importe: conformes, normalizado a MXN y sin recorte estadístico, y que no es contable", async () => {
    instalarApi();
    renderApp("/pulso-comercial");
    expect(await screen.findByText(/Importes de transacciones conformes, normalizados a MXN, sin recorte estadístico/)).toBeInTheDocument();
    expect(screen.getByText(/No es ingreso contable auditado, utilidad ni margen/)).toBeInTheDocument();
    expect(screen.getByText(/transacciones_limpias.monto_total_mxn/)).toBeInTheDocument();
  });

  it("presenta los mensajes interpretativos con sus cifras y el aviso de alcance (sin afirmar rentabilidad)", async () => {
    instalarApi();
    renderApp("/pulso-comercial");
    const lista = await screen.findByRole("region", { name: "Interpretación" });
    const ids = R.diagnostico.mensajes.map((m) => m.id);
    for (const id of ids) expect(document.querySelector(`[data-mensaje="${id}"]`)).not.toBeNull();
    expect(lista.querySelector('[data-mensaje="atipicas"]')).toBeNull();                     // el aviso de atípicos va junto al titular, no al final
    expect(within(lista).getByText(/No hay costos, márgenes ni gastos en los datos/)).toBeInTheDocument();
    expect(within(lista).queryByText(/rentable|ganancia/i)).not.toBeInTheDocument();
    expect(ids).toContain("tendencia");
  });

  it("documenta cómo se determinó la tendencia con los criterios propios de KOVA", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/pulso-comercial");
    await u.click(await screen.findByText("Cómo se determinó"));
    expect(screen.getByText(/\(\(importe actual − importe anterior\) ÷ importe anterior\) × 100/)).toBeInTheDocument();
    expect(screen.getByText(/propios de KOVA/)).toBeInTheDocument();
    expect(screen.getByText(/no son estándares oficiales/)).toBeInTheDocument();
  });

  it("muestra indicadores, canales, meses y productos reales", async () => {
    instalarApi();
    renderApp("/pulso-comercial");
    expect(await screen.findByText("Ticket promedio")).toBeInTheDocument();
    expect(screen.getByText(fEntero(R.actual.transacciones))).toBeInTheDocument();
    for (const c of R.canales) expect(document.querySelector(`[data-canal="${c.canal}"]`)).not.toBeNull();
    expect(document.querySelectorAll("[data-mes]").length).toBe(FIX.comercialTendencia.meses.length);
    expect(screen.getByText(/PARCIAL/)).toBeInTheDocument();
    const tabla = await screen.findByRole("table", { name: "Productos destacados del período" });
    expect(within(tabla).getAllByRole("row")).toHaveLength(FIX.comercialProductos.productos.length + 1);
    expect(within(tabla).getByText(FIX.comercialProductos.productos[0].nombre_producto)).toBeInTheDocument();
    expect(screen.getByText("Categorías con mayor participación")).toBeInTheDocument();
  });

  it("la gráfica diaria tiene descripción accesible y control de métrica", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/pulso-comercial");
    expect(await screen.findByRole("img", { name: /Importe por día/ })).toBeInTheDocument();
    await u.click(screen.getByRole("radio", { name: "Ticket" }));
    expect(await screen.findByRole("img", { name: /Ticket promedio por día/ })).toBeInTheDocument();
  });
});

describe("Pulso comercial · filtros", () => {
  it("pide el último mes con datos por omisión, no el mes del sistema", async () => {
    const { llamadas } = instalarApi();
    renderApp("/pulso-comercial");
    await screen.findByRole("heading", { level: 1, name: "Pulso comercial" });
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/comercial/resumen")).toBe(true));
    const l = llamadas.find((x) => x.ruta === "/api/comercial/resumen")!;
    expect(l.params.get("mes")).toBeNull();
    expect(l.params.get("comparacion")).toBe("equivalente");
  });

  it("cambia de mes, canal, comparación y tipo de ventas enviando los parámetros a la API", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/pulso-comercial");
    await screen.findByText("Ticket promedio");
    const mes = FIX.comercialOpciones.meses[0].mes;
    await u.selectOptions(screen.getByLabelText("Período"), mes);
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/comercial/resumen" && l.params.get("mes") === mes)).toBe(true));
    await u.click(screen.getByRole("radio", { name: "Online" }));
    await waitFor(() => expect(llamadas.some((l) => l.params.get("canal") === "ONLINE")).toBe(true));
    await u.selectOptions(screen.getByLabelText("Comparar con"), "mes_anterior_completo");
    await waitFor(() => expect(llamadas.some((l) => l.params.get("comparacion") === "mes_anterior_completo")).toBe(true));
    await u.click(screen.getByRole("radio", { name: /Solo ventas efectivas/ }));
    await waitFor(() => expect(llamadas.some((l) => l.params.get("estados") === "efectivas")).toBe(true));
    expect(ubicacion()).toContain("canal=ONLINE");
  });

  it("permite un rango personalizado con fechas y compara con el período inmediato anterior", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/pulso-comercial");
    await screen.findByText("Ticket promedio");
    await u.selectOptions(screen.getByLabelText("Período"), "personalizado");
    expect(await screen.findByLabelText("Desde")).toBeInTheDocument();
    expect(screen.getByLabelText("Hasta")).toBeInTheDocument();
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/comercial/resumen" && l.params.get("desde") === R.periodo.inicio && l.params.get("hasta") === R.periodo.fin)).toBe(true));
    expect(screen.getByRole("option", { name: "Período inmediato anterior" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Mes anterior completo" })).not.toBeInTheDocument();
  });

  it("ordena los productos por unidades", async () => {
    const { llamadas } = instalarApi();
    const u = userEvent.setup();
    renderApp("/pulso-comercial");
    await screen.findByRole("table", { name: "Productos destacados del período" });
    await u.click(screen.getByRole("radio", { name: "Unidades" }));
    await waitFor(() => expect(llamadas.some((l) => l.ruta === "/api/comercial/productos" && l.params.get("orden") === "unidades")).toBe(true));
  });
});

describe("Pulso comercial · casos límite y errores", () => {
  const sinComparacion = {
    ...R, anterior: null, anterior_kpis: null, homogeneo: false, canales: R.canales.map((c) => ({ ...c, importe_anterior: null, transacciones_anterior: null, variacion_importe_pct: null })), variaciones: { importe_pct: null, transacciones_pct: null, ticket_promedio_pct: null, promedio_diario_pct: null },
    diagnostico: { estado: "sin_comparacion", titular: "No hay información suficiente para evaluar una tendencia.", mensajes: [{ id: "sin_comparacion", tipo: "info", texto: "No se solicitó una comparación o no existe un período anterior: no hay información suficiente para evaluar una tendencia.", evidencia: {} }] },
  };

  it("no inventa una variación cuando no existe período anterior comparable", async () => {
    instalarApi({ "/api/comercial/resumen": () => sinComparacion });
    renderApp("/pulso-comercial");
    expect(await screen.findAllByText("Sin comparación válida")).not.toHaveLength(0);
    expect(screen.getAllByText("No hay información suficiente para evaluar una tendencia.").length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/[+−]\d+\.\d %/)).toHaveLength(0);
  });

  it("advierte cuando los períodos no son homogéneos", async () => {
    instalarApi({ "/api/comercial/resumen": () => ({ ...R, homogeneo: false }) });
    renderApp("/pulso-comercial");
    expect(await screen.findByText(/NO homogénea/)).toBeInTheDocument();
  });

  it("muestra un estado vacío cuando el período no tiene transacciones", async () => {
    const vacio = { ...R.actual, transacciones: 0, importe: 0, unidades: 0, ticket_promedio: null, promedio_diario: 0, dias_con_ventas: 0, primera_venta: null, ultima_venta: null };
    instalarApi({ "/api/comercial/resumen": () => ({ ...R, actual: vacio, diagnostico: { estado: "sin_datos", titular: "No hay transacciones conformes en el período seleccionado.", mensajes: [] } }) });
    renderApp("/pulso-comercial");
    expect(await screen.findByText("Sin ventas en este período")).toBeInTheDocument();
  });

  it("muestra el mensaje de la API y permite restablecer cuando el mes no existe", async () => {
    instalarApi({ "/api/comercial/resumen": () => json({ codigo: "MES_SIN_DATOS", mensaje: "No hay transacciones conformes en Julio 2026." }, 422) });
    const u = userEvent.setup();
    renderApp("/pulso-comercial?mes=2026-07");
    expect(await screen.findByText("No hay transacciones conformes en Julio 2026.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Restablecer filtros" }));
    await waitFor(() => expect(ubicacion()).toBe("/pulso-comercial"));
  });

  it("guía al Centro ETL si todavía no existe la base", async () => {
    instalarApi({ "/api/comercial/resumen": () => json({ codigo: "BD_NO_ENCONTRADA", mensaje: "Todavía no existe la base de datos." }, 503) });
    renderApp("/pulso-comercial");
    expect(await screen.findByText("Todavía no hay datos procesados")).toBeInTheDocument();
  });

  it("indica el fallo de conexión con el servidor", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderApp("/pulso-comercial");
    expect(await screen.findByText("KOVA no puede comunicarse con el servidor")).toBeInTheDocument();
  });
});

describe("tarjeta en el Panel ejecutivo y navegación", () => {
  it("el Panel conserva su contenido y agrega el resumen del Pulso comercial", async () => {
    instalarApi();
    renderApp("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: "Panel ejecutivo" })).toBeInTheDocument();
    const tarjeta = await screen.findByRole("link", { name: "Abrir Pulso comercial" });
    expect(tarjeta).toHaveAttribute("href", "/pulso-comercial");
    expect(within(tarjeta).getByText(R.diagnostico.titular)).toBeInTheDocument();
    expect(screen.getByText(/¿Cómo se calcula la salud de origen\?/)).toBeInTheDocument();       // el dashboard de calidad sigue intacto
  });

  it("pulsar la tarjeta abre la página y el menú la marca como activa", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/panel");
    await u.click(await screen.findByRole("link", { name: "Abrir Pulso comercial" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Pulso comercial" })).toBeInTheDocument();
    expect(ubicacion()).toBe("/pulso-comercial");
    expect(within(screen.getByRole("navigation", { name: "Principal" })).getByRole("link", { name: "Pulso comercial" })).toHaveAttribute("aria-current", "page");
  });

  it("si el pulso no puede calcularse, el Panel no se rompe ni muestra la tarjeta", async () => {
    instalarApi({ "/api/comercial/resumen": () => json({ codigo: "SIN_VENTAS", mensaje: "La base no tiene transacciones conformes." }, 404) });
    renderApp("/panel");
    expect(await screen.findByRole("heading", { level: 1, name: "Panel ejecutivo" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Abrir Pulso comercial" })).not.toBeInTheDocument();
  });
});

describe("moneda original en el detalle de una transacción", () => {
  it("muestra los seis conceptos de una venta en USD sin mezclarlos", async () => {
    instalarApi({ "/api/transacciones/WEB-00237": () => FIX.transaccionUsd });
    renderApp("/transacciones/WEB-00237");
    const panel = await waitFor(() => { const e = document.querySelector('[data-moneda="USD"]'); expect(e).not.toBeNull(); return e as HTMLElement; });
    const m = FIX.transaccionUsd.moneda;
    for (const c of ["Precio original", "Importe original reportado", "Tipo de cambio oficial", "Precio convertido", "Importe normalizado a MXN", "Importe con capping"]) expect(within(panel).getByText(c)).toBeInTheDocument();
    expect(within(panel).getByText(/Registrada originalmente en dólares/)).toBeInTheDocument();
    expect(within(panel).getByText("1 USD = $19.50")).toBeInTheDocument();
    expect(within(panel).getAllByText(fMXN(m.importe_mxn)).length).toBeGreaterThan(0);
    expect(within(panel).getByText("$216.31 USD")).toBeInTheDocument();
    expect(within(panel).getByText(/Sin recorte/)).toBeInTheDocument();
    expect(within(panel).getByText(/No coincidía con cantidad × precio/)).toBeInTheDocument();
  });

  it("para una venta en MXN no inventa una conversión", async () => {
    instalarApi();
    renderApp("/transacciones/WEB-00508");
    const panel = await waitFor(() => { const e = document.querySelector('[data-moneda="MXN"]'); expect(e).not.toBeNull(); return e as HTMLElement; });
    expect(within(panel).getByText(/Registrada originalmente en MXN/)).toBeInTheDocument();
    expect(screen.queryByText("Tipo de cambio oficial")).not.toBeInTheDocument();
    expect(screen.queryByText(/1 USD =/)).not.toBeInTheDocument();
  });
});

describe("encabezados homogéneos y catálogo simplificado", () => {
  it.each([
    ["/calidad", "Calidad de datos"], ["/etl", "Centro ETL"], ["/historial", "Historial de ejecuciones"], ["/transacciones", "Transacciones"],
    ["/cuarentena", "Cuarentena"], ["/catalogo", "Catálogo de productos"], ["/pulso-comercial", "Pulso comercial"], ["/panel", "Panel ejecutivo"],
  ])("%s tiene el título «%s»", async (ruta, titulo) => {
    instalarApi();
    renderApp(ruta);
    expect(await screen.findByRole("heading", { level: 1, name: titulo })).toBeInTheDocument();
  });

  it("el catálogo conserva filtros y funciones pero ya no repite descripciones largas", async () => {
    instalarApi();
    renderApp("/catalogo");
    await screen.findByText(FIX.catalogo.items[0].nombre_producto);
    expect(screen.queryByText(/Los 50 productos oficiales son la/)).not.toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Productos por categoría" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: /Buscar producto/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Tabla/ })).toBeInTheDocument();
    expect(screen.getByText(/no incluye fotografías de producto/)).toBeInTheDocument();
  });
});

describe("componente Variacion", () => {
  it("usa flecha, signo y texto (no solo color) y no inventa porcentajes", () => {
    const { rerender } = render(<Variacion valor={74.31} />);
    expect(screen.getByLabelText("Aumento de 74.3 por ciento")).toHaveTextContent("+74.3 %");
    rerender(<Variacion valor={-8.76} />);
    expect(screen.getByLabelText("Disminución de 8.8 por ciento")).toHaveTextContent("−8.8 %");
    rerender(<Variacion valor={null} />);
    expect(screen.getByText("Sin comparación válida")).toBeInTheDocument();
    rerender(<Variacion valor={0} />);
    expect(screen.getByLabelText("Sin cambio de 0.0 por ciento")).toBeInTheDocument();
  });
});
