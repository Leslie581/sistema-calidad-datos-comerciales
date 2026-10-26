const mxn = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 2 });
const mxnEntero = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
const entero = new Intl.NumberFormat("es-MX");
const decimal = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 });

export const fMXN = (v: number | null | undefined) => (v == null ? "—" : mxn.format(v));
export const fMXNCorto = (v: number | null | undefined) => (v == null ? "—" : mxnEntero.format(v));
export const fEntero = (v: number | null | undefined) => (v == null ? "—" : entero.format(v));
export const fDecimal = (v: number | null | undefined) => (v == null ? "—" : decimal.format(v));
export const fPct = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : `${(v * 100).toLocaleString("es-MX", { minimumFractionDigits: d, maximumFractionDigits: d })} %`;

/** «2026-10-12» → «12 oct 2026» sin pasar por Date (evita desfases de zona horaria). */
export function fFecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${Number(m[3])} ${meses[Number(m[2]) - 1]} ${m[1]}`;
}
export function fFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? `${fFecha(iso)} · ${m[1]}` : fFecha(iso);
}
export const fDuracion = (s: number | null | undefined) =>
  s == null ? "—" : s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toLocaleString("es-MX", { maximumFractionDigits: 2 })} s`;
export const fBytes = (b: number) => (b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`);

export const nombreCanal = (c: string | null | undefined) => (c === "FISICA" ? "Tienda física" : c === "ONLINE" ? "Tienda online" : "—");
export const valorTexto = (v: unknown): string =>
  v === null || v === undefined ? "∅" : typeof v === "object" ? JSON.stringify(v) : String(v);
