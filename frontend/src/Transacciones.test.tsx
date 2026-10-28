import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { fMXNp, fUSDp } from "./lib/format";
import { FIX, instalarApi } from "./test/apiMock";

const renderApp = (ruta: string) => render(<MemoryRouter initialEntries={[ruta]}><App /></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());

const filaDe = (id: string) => screen.getByRole("button", { name: `Ver recorrido de ${id}` }).closest("tr") as HTMLElement;
const usd = FIX.transacciones.items.find((t) => t.moneda_original === "USD")!;
const mxn = FIX.transacciones.items.find((t) => t.moneda_original === "MXN")!;

describe("tabla de Transacciones · moneda original", () => {
  it("la fixture trae un caso USD y uno MXN reales con el precio original persistido", () => {
    expect(usd.precio_unitario_original).not.toBeNull();
    expect(usd.tipo_cambio_aplicado).toBe(19.5);
    expect(usd.precio_unitario_original).not.toBe(usd.precio_unitario_mxn);
    expect(mxn.precio_unitario_original).toBe(mxn.precio_unitario_mxn);
  });

  it("para USD muestra US$ del precio original y debajo su equivalente en MX$", async () => {
    instalarApi();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    const celda = filaDe(usd.id_transaccion).querySelector('[data-moneda-origen="USD"]') as HTMLElement;
    const lineas = Array.from(celda.querySelectorAll("span")).map((s) => s.textContent);
    expect(lineas).toEqual([fUSDp(usd.precio_unitario_original), fMXNp(usd.precio_unitario_mxn)]);
    expect(lineas[0]).toMatch(/^US\$/);
    expect(lineas[1]).toMatch(/^MX\$/);
    expect(within(celda).queryByText(/convertido de USD/)).not.toBeInTheDocument();
  });

  it("para MXN muestra únicamente el precio en pesos", async () => {
    instalarApi();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    const celda = filaDe(mxn.id_transaccion).querySelector('[data-moneda-origen="MXN"]') as HTMLElement;
    expect(celda.textContent).toBe(fMXNp(mxn.precio_unitario_mxn));
    expect(celda.textContent).not.toMatch(/US\$/);
  });

  it("conserva la columna de importe normalizado en MXN, con su aclaración", async () => {
    instalarApi();
    renderApp("/transacciones");
    await screen.findByRole("table", { name: "Transacciones limpias" });
    expect(screen.getByRole("columnheader", { name: /Precio unitario/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Importe MXN/ })).toBeInTheDocument();
    const celdaImporte = within(filaDe(usd.id_transaccion)).getByText(/^\$[\d,]+\.\d{2}$/, { selector: "td" });
    expect(celdaImporte).toHaveAttribute("title", expect.stringContaining("El importe original está en el detalle"));
  });

  it("no usa la columna para mezclar conceptos: el importe original solo aparece en el detalle", async () => {
    instalarApi({ [`/api/transacciones/${usd.id_transaccion}`]: () => FIX.transaccionUsd });
    const u = userEvent.setup();
    renderApp("/transacciones");
    const tabla = await screen.findByRole("table", { name: "Transacciones limpias" });
    expect(within(tabla).queryByText(/Importe original/)).not.toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: `Ver recorrido de ${usd.id_transaccion}` }));
    expect(await screen.findByText("Importe original reportado", {}, { timeout: 3000 })).toBeInTheDocument();
  });
});

describe("ajustes de texto en la interfaz", () => {
  it("Calidad de datos ya no muestra etiquetas que referencien reportes de la etapa de Leslie", async () => {
    instalarApi();
    renderApp("/calidad");
    expect(await screen.findByRole("heading", { level: 1, name: "Calidad de datos" })).toBeInTheDocument();
    expect(await screen.findByText(/Completitud, tipos y duplicados del archivo crudo/)).toBeInTheDocument();
    expect(screen.queryByText(/reporte de la etapa de Leslie/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/01_perfil_antes|02_faltantes|06_antes_despues/)).not.toBeInTheDocument();
    expect(screen.queryByText(/imágenes generadas por Python/i)).not.toBeInTheDocument();
  });

  it("el modal del Centro ETL usa exactamente «Además se reescribirán los reportes de salida.»", async () => {
    instalarApi();
    const u = userEvent.setup();
    renderApp("/etl");
    await u.click(await screen.findByRole("button", { name: "Ejecutar pipeline" }));
    const dialogo = await screen.findByRole("alertdialog");
    expect(within(dialogo).getByText(/^Además se reescribirán los reportes de salida\./)).toBeInTheDocument();
    expect(dialogo.textContent).not.toMatch(/salidas\/etapa_nono|etapa_nono/);
    expect(dialogo.textContent).toContain("Además se reescribirán los reportes de salida. La operación dura unos segundos");
  });
});
