import { describe, expect, it } from "vitest";
import { fBytes, fDuracion, fEntero, fFecha, fFechaHora, fMXN, fMXNCorto, fPct, nombreCanal, valorTexto } from "./format";

describe("formato", () => {
  it("da formato de pesos mexicanos con centavos", () => {
    expect(fMXN(3307.01)).toBe("$3,307.01");
    expect(fMXN(826360.8)).toBe("$826,360.80");
    expect(fMXN(null)).toBe("—");
  });
  it("redondea importes grandes a pesos enteros", () => {
    expect(fMXNCorto(4585211.65)).toBe("$4,585,212");
  });
  it("separa miles y formatea porcentajes en español", () => {
    expect(fEntero(1220)).toBe("1,220");
    expect(fPct(0.9049)).toBe("90.5 %");
    expect(fPct(0.7205, 2)).toBe("72.05 %");
    expect(fPct(undefined)).toBe("—");
  });
  it("convierte fechas ISO sin desfase de zona horaria", () => {
    expect(fFecha("2026-09-01")).toBe("1 sep 2026");
    expect(fFecha("2026-10-16")).toBe("16 oct 2026");
    expect(fFechaHora("2026-10-26T00:09:10")).toBe("26 oct 2026 · 00:09");
    expect(fFecha(null)).toBe("—");
    expect(fFecha("no es fecha")).toBe("no es fecha");
  });
  it("formatea duraciones medidas", () => {
    expect(fDuracion(0.287)).toBe("287 ms");
    expect(fDuracion(1.5)).toBe("1.5 s");
    expect(fDuracion(null)).toBe("—");
  });
  it("describe tamaños, canales y valores nulos", () => {
    expect(fBytes(512)).toBe("512 B");
    expect(fBytes(2048)).toBe("2.0 KB");
    expect(nombreCanal("FISICA")).toBe("Tienda física");
    expect(nombreCanal("ONLINE")).toBe("Tienda online");
    expect(valorTexto(null)).toBe("∅");
    expect(valorTexto({ a: 1 })).toBe('{"a":1}');
  });
});
