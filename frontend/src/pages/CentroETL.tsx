import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, CircleAlert, Download, Play, Timer } from "lucide-react";
import { FondoTrayectos } from "../components/brand/Fondos";
import { MarcaDeAgua } from "../components/brand/Marca";
import { Boton, Insignia } from "../components/ui/Basicos";
import { DialogoConfirmar } from "../components/ui/Drawer";
import { EstadoError, PantallaCarga } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useSistema } from "../hooks/sistema";
import { fDuracion, fEntero, fFechaHora, fPct, valorTexto } from "../lib/format";
import { api, ErrorApi } from "../services/api";
import type { EstadoFase, Fase } from "../services/tipos";

/** Orden en que el pipeline ejecuta las fases (la integración precede al IQR: necesita el importe en MXN). */
const ORDEN_EJECUCION = [1, 2, 4, 3, 5, 6, 7];
const CORTO: Record<string, string> = { diagnostico: "Diagnóstico", faltantes: "Faltantes", outliers: "Outliers", integracion: "Integración", transformacion: "Transformación", validacion: "Validación", carga: "Carga" };
const ESTILO_FASE: Record<EstadoFase, { relleno: string; trazo: string; texto: string; etiqueta: string }> = {
  COMPLETADA: { relleno: "#B8E8CE", trazo: "#215548", texto: "#17352D", etiqueta: "Completada" },
  FALLIDA: { relleno: "#f2b6ac", trazo: "#A2443A", texto: "#5c1c14", etiqueta: "Fallida" },
  PARCIAL: { relleno: "#f3d9a8", trazo: "#85570F", texto: "#4a2f06", etiqueta: "Parcial" },
  NO_EJECUTADA: { relleno: "#ECEDE3", trazo: "#8A9D94", texto: "#526860", etiqueta: "No ejecutada" },
  SIN_DATOS: { relleno: "#ECEDE3", trazo: "#8A9D94", texto: "#526860", etiqueta: "Sin datos" },
};
const ETIQUETAS_METRICA: Record<string, string> = {
  filas_fuentes: "Filas por fuente", integridad_originales: "Originales verificados (SHA-256)", duplicados_marcados: "Duplicados marcados",
  montos_recalculados: "Importes recalculados", etiquetas: "Etiquetas controladas", base_estadistica: "Base estadística",
  limite_superior_monto: "Límite superior del importe (MXN)", montos_recortados: "Importes con capping", filas: "Filas integradas",
  min: "Mínimo (Min-Max)", max: "Máximo (Min-Max)", cortes: "Cortes de terciles (MXN)", validos: "Transacciones válidas",
  cuarentena: "En cuarentena", errores_inesperados: "Errores inesperados", estado: "Estado de la transacción", limpias: "Filas limpias cargadas",
};

function Metrica({ k, v }: { k: string; v: unknown }) {
  let texto: string;
  if (v && typeof v === "object") texto = Object.entries(v as Record<string, unknown>).map(([a, b]) => `${a}: ${valorTexto(b)}`).join(" · ");
  else if (typeof v === "number") texto = Number.isInteger(v) ? fEntero(v) : v.toLocaleString("es-MX", { maximumFractionDigits: 2 });
  else texto = valorTexto(v);
  return <div className="rounded-xl bg-superficie-2 px-3 py-2"><dt className="text-xs font-bold text-suave">{ETIQUETAS_METRICA[k] ?? k}</dt><dd className="num break-words text-sm font-bold text-bosque">{texto}</dd></div>;
}

function Diagrama({ fases, ejecutando, seleccion, alElegir, limpias, cuarentena }: {
  fases: Fase[]; ejecutando: boolean; seleccion: number; alElegir: (n: number) => void; limpias?: number | null; cuarentena?: number | null;
}) {
  const filas = (fases[0]?.metricas?.filas_fuentes ?? {}) as Record<string, number>;
  const cuenta = (n?: number) => (n == null ? "sin datos" : `${fEntero(n)} filas`);
  const porNumero = new Map(fases.map((f) => [f.numero, f]));
  const x0 = 250, paso = 122;
  return (
    <div className="scroll-fino overflow-x-auto rounded-3xl">
      <svg viewBox="0 0 1420 330" className="min-w-[1180px]" role="group" aria-label="Flujo del pipeline: fuentes, siete fases, bifurcación y carga">
        {/* fuentes */}
        {[["Tienda física", `CSV · ${cuenta(filas.fisica)}`, 40], ["Tienda online", `JSON · ${cuenta(filas.online)}`, 125], ["Catálogo", `CSV · ${cuenta(filas.catalogo)}`, 210]].map(([t, s, y]) => (
          <g key={String(t)} transform={`translate(10 ${y})`}>
            <rect width="150" height="68" rx="20" fill="#FDFCFA" fillOpacity="0.1" stroke="#B8E8CE" strokeOpacity="0.4" />
            <text x="18" y="29" fill="#FDFCFA" fontSize="15" fontWeight="700" fontFamily="inherit">{t}</text>
            <text x="18" y="50" fill="#B8E8CE" fontSize="12.5" fontWeight="600" fontFamily="inherit">{s}</text>
            <path d={`M150 34 C 190 34, 190 ${165 - Number(y)}, 232 ${165 - Number(y)}`} fill="none" stroke="#B8E8CE" strokeOpacity="0.55" strokeWidth="2" className={ejecutando ? "flujo-animado" : ""} />
          </g>
        ))}
        {/* conectores entre fases */}
        {ORDEN_EJECUCION.slice(0, -1).map((_, i) => (
          <line key={i} x1={x0 + i * paso + 98} y1="165" x2={x0 + (i + 1) * paso} y2="165" stroke="#B8E8CE" strokeOpacity="0.7" strokeWidth="2.4" className={ejecutando ? "flujo-animado" : ""} />
        ))}
        {/* fases */}
        {ORDEN_EJECUCION.map((n, i) => {
          const f = porNumero.get(n);
          const est = ESTILO_FASE[ejecutando ? "SIN_DATOS" : f?.estado ?? "SIN_DATOS"];
          const activo = seleccion === n;
          return (
            <g key={n} transform={`translate(${x0 + i * paso} 100)`} role="button" tabIndex={0} aria-pressed={activo}
              aria-label={`Fase ${n}, ${f?.nombre ?? ""}: ${ejecutando ? "ejecutando" : est.etiqueta.toLowerCase()}${f?.duracion_s != null ? `, ${fDuracion(f.duracion_s)}` : ""}`}
              onClick={() => alElegir(n)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alElegir(n); } }} style={{ cursor: "pointer", outline: "none" }}>
              <rect width="98" height="130" rx="26" fill={est.relleno} stroke={activo ? "#D99B45" : est.trazo} strokeWidth={activo ? 4 : 1.5} />
              {activo && <rect x="-6" y="-6" width="110" height="142" rx="31" fill="none" stroke="#D99B45" strokeOpacity="0.45" strokeWidth="2" />}
              <circle cx="49" cy="34" r="19" fill="#17352D" />
              <text x="49" y="40.5" textAnchor="middle" fill="#FDFCFA" fontSize="18" fontWeight="800" fontFamily="inherit">{n}</text>
              <text x="49" y="78" textAnchor="middle" fill={est.texto} fontSize="12.5" fontWeight="800" fontFamily="inherit">{CORTO[f?.clave ?? ""] ?? ""}</text>
              <text x="49" y="100" textAnchor="middle" fill={est.texto} fontSize="12" fontWeight="600" className="num" fontFamily="inherit">{ejecutando ? "…" : f?.duracion_s != null ? fDuracion(f.duracion_s) : "—"}</text>
              <text x="49" y="119" textAnchor="middle" fill={est.texto} fontSize="10.5" fontWeight="700" fontFamily="inherit" opacity="0.85">{ejecutando ? "EN CURSO" : est.etiqueta.toUpperCase()}</text>
            </g>
          );
        })}
        {/* bifurcación */}
        <line x1={x0 + 6 * paso + 98} y1="165" x2="1148" y2="165" stroke="#B8E8CE" strokeOpacity="0.7" strokeWidth="2.4" />
        <circle cx="1166" cy="165" r="17" fill="#D99B45" stroke="#17352D" strokeWidth="5" />
        <path d="M1182 165 C 1230 165, 1228 78, 1270 78" fill="none" stroke="#B8E8CE" strokeWidth="2.6" className={ejecutando ? "flujo-animado" : ""} />
        <path d="M1182 165 C 1230 165, 1228 252, 1270 252" fill="none" stroke="#D99B45" strokeWidth="2.6" className={ejecutando ? "flujo-animado" : ""} />
        <g transform="translate(1270 28)">
          <rect width="140" height="100" rx="26" fill="#B8E8CE" />
          <text x="70" y="40" textAnchor="middle" fill="#17352D" fontSize="13" fontWeight="800" fontFamily="inherit">SQLite · limpias</text>
          <text x="70" y="76" textAnchor="middle" fill="#17352D" fontSize="30" fontWeight="800" className="num" fontFamily="var(--font-display)">{limpias != null ? fEntero(limpias) : "—"}</text>
        </g>
        <g transform="translate(1270 202)">
          <rect width="140" height="100" rx="26" fill="#D99B45" />
          <text x="70" y="40" textAnchor="middle" fill="#17352D" fontSize="13" fontWeight="800" fontFamily="inherit">SQLite · cuarentena</text>
          <text x="70" y="76" textAnchor="middle" fill="#17352D" fontSize="30" fontWeight="800" className="num" fontFamily="var(--font-display)">{cuarentena != null ? fEntero(cuarentena) : "—"}</text>
        </g>
      </svg>
    </div>
  );
}

export default function CentroETL() {
  const { estado, error, refrescar, ciclo } = useSistema();
  const [confirmar, setConfirmar] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [falloArranque, setFalloArranque] = useState<ErrorApi | null>(null);
  const [sel, setSel] = useState(1);
  const [ahora, setAhora] = useState(() => Date.now());
  const ejecutando = estado?.ejecutor.estado === "EN_EJECUCION";
  useEffect(() => {
    if (!ejecutando) return;
    const t = setInterval(() => setAhora(Date.now()), 500);
    return () => clearInterval(t);
  }, [ejecutando]);

  const lote = estado?.ultima?.lote_id;
  const detalle = useApi(async (s) => (lote ? api.ejecucion(lote, s) : null), [lote, ciclo]);
  const lista = useApi((s) => api.ejecuciones({}, s), [ciclo]);

  if (error && !estado) return <EstadoError error={error} alReintentar={refrescar} />;
  if (!estado) return <PantallaCarga />;

  const ultima = estado.ultima;
  const res = estado.ejecutor.ultimo_resultado as null | { estado?: string; duracion_s?: number; error?: string; etapa_fallida?: string; lote_id?: string; terminado_en?: string; validacion?: { validos: number; cuarentena: number } | null };
  const fase = estado.fases.find((f) => f.numero === sel) ?? estado.fases[0];
  const transcurrido = ejecutando && estado.ejecutor.iniciado_en ? Math.max(0, Math.round((ahora - new Date(estado.ejecutor.iniciado_en).getTime()) / 1000)) : 0;
  const maxDur = Math.max(...estado.fases.map((f) => f.duracion_s ?? 0), 0.001);

  const lanzar = async () => {
    setEnviando(true); setFalloArranque(null);
    try { await api.ejecutarPipeline(); setConfirmar(false); refrescar(); }
    catch (e) { setConfirmar(false); setFalloArranque(e instanceof ErrorApi ? e : new ErrorApi("ERROR", String(e))); refrescar(); }
    finally { setEnviando(false); }
  };

  return (
    <div className="space-y-6">
      <section className="panel-bosque entra relative isolate overflow-hidden px-6 py-8 sm:px-10">
        <FondoTrayectos className="-z-10" />
        <MarcaDeAgua className="-right-16 -top-24" opacidad={0.06} />
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="etiqueta !text-menta/80">Centro ETL</p>
            <h1 className="titular mt-2 text-[clamp(1.9rem,3.6vw,3rem)] text-blanco">El recorrido completo de tus datos</h1>
            <p className="lectura mt-2 text-menta/90">Siete fases oficiales, un solo flujo. Los estados y tiempos que ves son los medidos en la última ejecución real; KOVA no simula progreso.</p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <Boton onClick={() => setConfirmar(true)} disabled={ejecutando || enviando} className="!bg-ambar !text-bosque hover:!brightness-105">
              <Play size={17} aria-hidden="true" />{ejecutando ? "Ejecutando…" : "Ejecutar pipeline"}
            </Boton>
            <p className="text-xs text-menta/70">{ejecutando ? <span className="num">En ejecución desde hace {transcurrido} s · estado general</span> : "Reemplaza el contenido de la base con una carga nueva."}</p>
          </div>
        </div>
        <div className="mt-6" aria-live="polite">
          {ejecutando && <p className="flex items-center gap-2 rounded-2xl bg-ambar/20 px-4 py-3 text-sm font-bold text-ambar"><Timer size={17} className="pulso" aria-hidden="true" />El pipeline está corriendo. Este pipeline no emite progreso por fase: verás el resultado completo al terminar.</p>}
          {!ejecutando && res?.terminado_en && (
            <p className={`flex flex-wrap items-center gap-2 rounded-2xl px-4 py-3 text-sm font-bold ${res.estado === "COMPLETADO" ? "bg-menta/20 text-menta" : "bg-coral/25 text-[#ffd6cf]"}`}>
              {res.estado === "COMPLETADO" ? <CheckCircle2 size={17} aria-hidden="true" /> : <CircleAlert size={17} aria-hidden="true" />}
              {res.estado === "COMPLETADO"
                ? <>Ejecución completada en {fDuracion(res.duracion_s)} · {fEntero(res.validacion?.validos)} válidas y {fEntero(res.validacion?.cuarentena)} en cuarentena.</>
                : <>La ejecución falló en «{res.etapa_fallida ?? "?"}»: {res.error}</>}
            </p>
          )}
          {falloArranque && <p role="alert" className="mt-2 rounded-2xl bg-coral/25 px-4 py-3 text-sm font-bold text-[#ffd6cf]">{falloArranque.message}</p>}
        </div>
      </section>

      <section className="panel-bosque entra relative isolate overflow-hidden p-4 sm:p-6" style={{ ["--i" as string]: 1 } as React.CSSProperties} aria-labelledby="t-flujo">
        <h2 id="t-flujo" className="sr-only">Diagrama del pipeline</h2>
        <Diagrama fases={estado.fases} ejecutando={!!ejecutando} seleccion={sel} alElegir={setSel} limpias={ultima?.filas_limpias} cuarentena={ultima?.filas_cuarentena} />
        <p className="mt-2 text-xs text-menta/70">Los números identifican la fase oficial; el flujo sigue el orden de ejecución: la integración (4) corre antes que los outliers (3) porque el IQR necesita el importe ya convertido a MXN.</p>
      </section>

      <div className="grid gap-5 lg:grid-cols-12">
        <section className="panel entra p-6 lg:col-span-7" style={{ ["--i" as string]: 2 } as React.CSSProperties} aria-labelledby="t-fase">
          <p className="etiqueta">Fase {fase.numero} · responsable {fase.responsable}</p>
          <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
            <h2 id="t-fase" className="titular text-2xl text-bosque">{fase.nombre}</h2>
            <Insignia tono={fase.estado === "COMPLETADA" ? "ok" : fase.estado === "FALLIDA" ? "alerta" : "neutro"}>{ESTILO_FASE[fase.estado].etiqueta}</Insignia>
          </div>
          <p className="mt-2 text-sm text-suave">Etapas internas: {fase.etapas_internas.join(" · ")}. Duración medida: <b className="num text-bosque">{fDuracion(fase.duracion_s)}</b>.</p>
          {fase.nota && <p className="mt-2 rounded-xl bg-superficie-2 px-3 py-2 text-sm text-suave">{fase.nota}</p>}
          {Object.keys(fase.metricas).length > 0
            ? <dl className="mt-4 grid gap-2 sm:grid-cols-2">{Object.entries(fase.metricas).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => <Metrica key={k} k={k} v={v} />)}</dl>
            : <p className="mt-4 text-sm text-suave">Sin métricas verificables para esta fase en la última ejecución.</p>}
        </section>

        <section className="panel entra p-6 lg:col-span-5" style={{ ["--i" as string]: 3 } as React.CSSProperties} aria-labelledby="t-dur">
          <p className="etiqueta">Última ejecución</p>
          <h2 id="t-dur" className="titular mt-1 text-2xl text-bosque">{ultima ? fFechaHora(ultima.inicio) : "Sin ejecuciones"}</h2>
          {ultima && (
            <>
              <dl className="num mt-3 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="etiqueta">Estado</dt><dd><Insignia tono={ultima.estado === "COMPLETADO" ? "ok" : "alerta"}>{ultima.estado === "COMPLETADO" ? "Completada" : "Fallida"}</Insignia></dd></div>
                <div><dt className="etiqueta">Duración</dt><dd className="font-bold text-bosque">{fDuracion(ultima.duracion_s)}</dd></div>
                <div><dt className="etiqueta">Procesados</dt><dd className="font-bold text-bosque">{fEntero(ultima.filas_entrada)}</dd></div>
                <div><dt className="etiqueta">Aceptación</dt><dd className="font-bold text-bosque">{fPct(ultima.tasa_aceptacion)}</dd></div>
              </dl>
              {ultima.estado === "FALLIDO" && <p role="alert" className="mt-3 rounded-xl bg-[#f9e5e1] p-3 text-sm text-coral-texto">Falló en «{ultima.etapa_fallida}»: {ultima.error}</p>}
            </>
          )}
          <h3 className="etiqueta mb-2 mt-5">Tiempo por fase (medido)</h3>
          <ul className="space-y-2">
            {estado.fases.map((f) => (
              <li key={f.numero} className="grid grid-cols-[7.5rem_1fr_4rem] items-center gap-2 text-sm">
                <span className="truncate font-medium">{f.numero}. {CORTO[f.clave]}</span>
                <span className="h-2.5 overflow-hidden rounded-full bg-superficie-2"><span className="block h-full rounded-full bg-petroleo transition-[width] duration-700" style={{ width: `${((f.duracion_s ?? 0) / maxDur) * 100}%` }} /></span>
                <span className="num text-right text-xs text-suave">{fDuracion(f.duracion_s)}</span>
              </li>
            ))}
          </ul>
        </section>

        {(ultima?.advertencias.length ?? 0) > 0 && (
          <section className="panel-aviso entra p-5 lg:col-span-12" role="status"><p className="etiqueta !text-ambar-texto">Advertencias</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{ultima!.advertencias.map((a) => <li key={a}>{a}</li>)}</ul></section>
        )}

        <section className="panel entra p-6 lg:col-span-7" style={{ ["--i" as string]: 4 } as React.CSSProperties} aria-labelledby="t-log">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><p className="etiqueta">Registro del proceso</p><h2 id="t-log" className="titular mt-1 text-2xl text-bosque">Log de la última ejecución</h2></div>
            {lote && detalle.datos?.bitacora_disponible && (
              <a href={`/api/reportes/etapa_nono/bitacoras/bitacora_${lote}.json?descargar=true`} className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-borde-fuerte bg-blanco px-4 text-sm font-bold text-bosque hover:bg-superficie-2"><Download size={15} aria-hidden="true" />Bitácora JSON</a>
            )}
          </div>
          {detalle.datos?.log?.length
            ? <pre tabIndex={0} aria-label="Líneas del log" className="scroll-fino mt-3 max-h-72 overflow-auto rounded-2xl bg-bosque p-4 font-mono text-xs leading-relaxed text-menta">{detalle.datos.log.join("\n")}</pre>
            : <p className="mt-3 text-sm text-suave">{!lote ? "Todavía no hay ejecuciones registradas." : detalle.datos ? "No hay un archivo de log disponible para esta ejecución." : "Cargando…"}</p>}
        </section>

        <section className="panel entra p-6 lg:col-span-5" style={{ ["--i" as string]: 5 } as React.CSSProperties} aria-labelledby="t-hist">
          <p className="etiqueta">Historial</p>
          <h2 id="t-hist" className="titular mb-3 mt-1 text-2xl text-bosque">Ejecuciones recientes</h2>
          <ul className="divide-y divide-borde">
            {lista.datos?.items.slice(0, 5).map((e) => (
              <li key={e.lote_id} className="flex items-center justify-between gap-2 py-2.5">
                <div className="min-w-0"><p className="num truncate text-sm font-bold">{e.lote_id}</p><p className="text-xs text-suave">{fFechaHora(e.inicio)}</p></div>
                <Insignia tono={e.estado === "COMPLETADO" ? "ok" : "alerta"}>{e.estado === "COMPLETADO" ? "Completada" : "Fallida"}</Insignia>
              </li>
            ))}
          </ul>
          <Link to="/historial" className="mt-3 inline-flex min-h-11 items-center font-bold text-petroleo hover:underline">Ver historial y reportes</Link>
        </section>
      </div>

      <DialogoConfirmar abierto={confirmar} titulo="¿Ejecutar el pipeline completo?" textoConfirmar={enviando ? "Iniciando…" : "Sí, ejecutar"} alConfirmar={lanzar} alCancelar={() => setConfirmar(false)}>
        <p>KOVA volverá a procesar los tres archivos oficiales (verificando su huella SHA-256) y <b>reemplazará</b> el contenido de la base SQLite con el resultado. El historial de ejecuciones se conserva.</p>
        <p>Además se reescribirán los reportes de <span className="font-mono text-xs">salidas/etapa_nono</span>. La operación dura unos segundos y no se puede ejecutar dos veces a la vez.</p>
      </DialogoConfirmar>
    </div>
  );
}
