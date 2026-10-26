import { useState } from "react";
import { Download, ExternalLink, FileText, ImageIcon } from "lucide-react";
import { FondoEditorial } from "../components/brand/Fondos";
import { Encabezado, Insignia } from "../components/ui/Basicos";
import { Buscador, Segmentado } from "../components/ui/Controles";
import { Drawer } from "../components/ui/Drawer";
import { EstadoError, EstadoVacio, FilasEsqueleto } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useSistema } from "../hooks/sistema";
import { fBytes, fDuracion, fEntero, fFechaHora, fPct } from "../lib/format";
import { api } from "../services/api";

const NOMBRE_CARPETA: Record<string, string> = { etapa_leslie: "Etapa 1 · Calidad (Leslie)", etapa_yerik: "Etapa 2 · Integración (Yerik)", etapa_nono: "Etapa 3 · Validación y carga (Nono)" };
const ESTILO_FASE = { COMPLETADA: "ok", FALLIDA: "alerta", PARCIAL: "aviso", NO_EJECUTADA: "neutro", SIN_DATOS: "neutro" } as const;

export default function Historial() {
  const { ciclo } = useSistema();
  const lista = useApi((s) => api.ejecuciones({}, s), [ciclo]);
  const reportes = useApi((s) => api.reportes(s), [ciclo]);
  const [lote, setLote] = useState<string | null>(null);
  const detalle = useApi(async (s) => (lote ? api.ejecucion(lote, s) : null), [lote]);
  const [carpeta, setCarpeta] = useState("etapa_nono");
  const [filtro, setFiltro] = useState("");

  const grupo = reportes.datos?.grupos.find((g) => g.carpeta === carpeta);
  const archivos = (grupo?.archivos ?? []).filter((a) => a.ruta.toLowerCase().includes(filtro.trim().toLowerCase()));

  return (
    <div className="space-y-6">
      <section className="entra relative isolate overflow-hidden rounded-[1.75rem] border border-borde bg-blanco px-6 py-8 sm:px-10">
        <FondoEditorial className="-z-10" />
        <Encabezado etiqueta="Proceso · historial y reportes" titulo="Todo lo que ha ejecutado KOVA">
          Cada ejecución del pipeline queda registrada, también las que fallaron. Los reportes son los archivos reales que generó Python; puedes verlos o descargarlos.
        </Encabezado>
      </section>

      <section className="panel entra overflow-hidden" aria-labelledby="t-ej">
        <div className="flex flex-wrap items-end justify-between gap-2 px-5 pt-5">
          <div><p className="etiqueta">Ejecuciones</p><h2 id="t-ej" className="titular mt-1 text-2xl text-bosque">Historial del pipeline</h2></div>
          {lista.datos && <p className="max-w-md text-xs text-suave">{lista.datos.nota}</p>}
        </div>
        {lista.error && !lista.datos ? <div className="p-4"><EstadoError error={lista.error} alReintentar={lista.recargar} /></div> : !lista.datos ? <FilasEsqueleto /> : lista.datos.items.length === 0 ? (
          <div className="p-4"><EstadoVacio titulo="Todavía no hay ejecuciones">Ejecuta el pipeline desde el Centro ETL y quedará registrado aquí.</EstadoVacio></div>
        ) : (
          <div className="scroll-fino mt-3 overflow-auto">
            <table className="tabla min-w-[860px]">
              <caption className="sr-only">Historial de ejecuciones</caption>
              <thead><tr><th scope="col">Ejecución</th><th scope="col">Inicio</th><th scope="col">Estado</th><th scope="col" className="der">Recibidos</th><th scope="col" className="der">Válidas</th><th scope="col" className="der">Cuarentena</th><th scope="col" className="der">Aceptación</th><th scope="col" className="der">Duración</th></tr></thead>
              <tbody>
                {lista.datos.items.map((e) => (
                  <tr key={e.lote_id}>
                    <td><button type="button" onClick={() => setLote(e.lote_id)} className="num min-h-9 text-left font-bold text-petroleo underline-offset-2 hover:underline" aria-label={`Ver detalle de la ejecución ${e.lote_id}`}>{e.lote_id}</button></td>
                    <td className="num whitespace-nowrap">{fFechaHora(e.inicio)}</td>
                    <td><Insignia tono={e.estado === "COMPLETADO" ? "ok" : "alerta"}>{e.estado === "COMPLETADO" ? "Completada" : "Fallida"}</Insignia>
                      {e.estado === "FALLIDO" && <span className="mt-1 block max-w-[240px] truncate text-xs text-coral-texto" title={e.error ?? ""}>en «{e.etapa_fallida}»</span>}</td>
                    <td className="num der">{fEntero(e.filas_entrada)}</td><td className="num der">{fEntero(e.filas_limpias)}</td><td className="num der">{fEntero(e.filas_cuarentena)}</td>
                    <td className="num der">{fPct(e.tasa_aceptacion)}</td><td className="num der">{fDuracion(e.duracion_s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel entra p-5 sm:p-6" aria-labelledby="t-rep">
        <p className="etiqueta">Reportes generados</p>
        <h2 id="t-rep" className="titular mb-4 mt-1 text-2xl text-bosque">Archivos de cada etapa</h2>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Segmentado etiqueta="Etapa" valor={carpeta} alCambiar={setCarpeta}
            opciones={(reportes.datos?.grupos ?? [{ carpeta: "etapa_nono", archivos: [] }]).map((g) => ({ valor: g.carpeta, texto: NOMBRE_CARPETA[g.carpeta]?.split(" (")[0] ?? g.carpeta }))} />
          <Buscador valor={filtro} alCambiar={setFiltro} etiqueta="Filtrar reportes por nombre" placeholder="Filtrar por nombre…" />
        </div>
        {reportes.error && !reportes.datos ? <EstadoError error={reportes.error} alReintentar={reportes.recargar} /> : !reportes.datos ? <FilasEsqueleto filas={5} /> : archivos.length === 0 ? (
          <EstadoVacio titulo="Sin reportes para mostrar">{filtro ? "Ningún archivo coincide con el filtro." : "Esta carpeta todavía no tiene reportes."}</EstadoVacio>
        ) : (
          <ul className="grid gap-2 md:grid-cols-2">
            {archivos.map((a) => (
              <li key={a.ruta} className="flex items-center gap-3 rounded-2xl border border-borde bg-blanco p-3">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-superficie-2 text-petroleo">{a.tipo === "png" ? <ImageIcon size={18} aria-hidden="true" /> : <FileText size={18} aria-hidden="true" />}</span>
                <div className="min-w-0 flex-1"><p className="truncate text-sm font-bold" title={a.ruta}>{a.ruta}</p><p className="num text-xs text-suave">{a.tipo.toUpperCase()} · {fBytes(a.bytes)}</p></div>
                <a href={a.url} target="_blank" rel="noreferrer" aria-label={`Abrir ${a.nombre}`} className="grid size-10 place-items-center rounded-full border border-borde-fuerte text-bosque hover:bg-superficie-2"><ExternalLink size={16} aria-hidden="true" /></a>
                <a href={`${a.url}?descargar=true`} aria-label={`Descargar ${a.nombre}`} className="grid size-10 place-items-center rounded-full bg-bosque text-blanco hover:bg-petroleo"><Download size={16} aria-hidden="true" /></a>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs text-suave">Solo se listan archivos de las carpetas de evidencias del proyecto (CSV, JSON, TXT, PNG, MD). La base SQLite no se descarga desde la interfaz.</p>
      </section>

      <Drawer abierto={!!lote} titulo={lote ?? ""} subtitulo="Detalle de ejecución" alCerrar={() => setLote(null)}>
        {detalle.error ? <EstadoError error={detalle.error} alReintentar={detalle.recargar} /> : !detalle.datos ? <FilasEsqueleto filas={6} /> : (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              <Insignia tono={detalle.datos.ejecucion.estado === "COMPLETADO" ? "ok" : "alerta"}>{detalle.datos.ejecucion.estado === "COMPLETADO" ? "Completada" : "Fallida"}</Insignia>
              <Insignia tono="neutro">{fFechaHora(detalle.datos.ejecucion.inicio)}</Insignia>
              <Insignia tono="neutro">{fDuracion(detalle.datos.ejecucion.duracion_s)}</Insignia>
            </div>
            {detalle.datos.ejecucion.estado === "FALLIDO" && <p role="alert" className="rounded-2xl bg-[#f9e5e1] p-4 text-sm text-coral-texto"><b>Falló en «{detalle.datos.ejecucion.etapa_fallida}».</b> {detalle.datos.ejecucion.error}</p>}
            <section><h3 className="etiqueta mb-2">Fases</h3>
              <ul className="space-y-1.5">{detalle.datos.fases.map((f) => (
                <li key={f.numero} className="flex items-center justify-between gap-3 rounded-xl bg-blanco px-3 py-2 text-sm ring-1 ring-borde"><span className="font-bold">{f.numero}. {f.nombre}</span>
                  <span className="flex items-center gap-2"><span className="num text-xs text-suave">{fDuracion(f.duracion_s)}</span><Insignia tono={ESTILO_FASE[f.estado]}>{f.estado.replace("_", " ").toLowerCase()}</Insignia></span></li>))}</ul></section>
            {Object.keys(detalle.datos.huellas_entrada).length > 0 && (
              <section><h3 className="etiqueta mb-2">Huellas SHA-256 de las fuentes</h3>
                <dl className="space-y-1.5 text-xs">{Object.entries(detalle.datos.huellas_entrada).map(([k, v]) => <div key={k} className="rounded-xl bg-blanco p-2.5 ring-1 ring-borde"><dt className="font-bold">{k}</dt><dd className="num break-all text-suave">{v}</dd></div>)}</dl></section>
            )}
            <section><h3 className="etiqueta mb-2">Entorno</h3><p className="num text-sm text-suave">{Object.entries(detalle.datos.entorno).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}</p></section>
            {detalle.datos.log && <section><h3 className="etiqueta mb-2">Log</h3><pre tabIndex={0} aria-label="Log de la ejecución" className="scroll-fino max-h-64 overflow-auto rounded-2xl bg-bosque p-4 font-mono text-xs leading-relaxed text-menta">{detalle.datos.log.join("\n")}</pre></section>}
          </div>
        )}
      </Drawer>
    </div>
  );
}
