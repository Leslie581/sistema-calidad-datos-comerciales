import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, CircleAlert, ShieldAlert, Workflow } from "lucide-react";
import { FondoCanales } from "../components/brand/Fondos";
import { IlustracionConvergencia } from "../components/brand/Ilustraciones";
import { MarcaDeAgua } from "../components/brand/Marca";
import { Insignia } from "../components/ui/Basicos";
import { EstadoError, EstadoVacio, PantallaCarga } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useSistema } from "../hooks/sistema";
import { fDuracion, fEntero, fFechaHora, fPct } from "../lib/format";
import { api } from "../services/api";
import type { EstadoFase } from "../services/tipos";

const COLOR_FASE: Record<EstadoFase, string> = {
  COMPLETADA: "bg-menta", FALLIDA: "bg-coral", PARCIAL: "bg-ambar", NO_EJECUTADA: "bg-salvia/50", SIN_DATOS: "bg-salvia/50",
};

export default function Inicio() {
  const { ciclo, estado } = useSistema();
  const { datos, error, recargar } = useApi((s) => api.dashboard(s), [ciclo]);
  if (error && !datos) return <EstadoError error={error} alReintentar={recargar} />;
  if (!datos) return <PantallaCarga />;
  const { totales: t, ultima_ejecucion: u } = datos;
  const fis = datos.canales.find((c) => c.origen === "FISICA"), onl = datos.canales.find((c) => c.origen === "ONLINE");
  const integridad = estado?.fases[0]?.metricas?.integridad_originales as Record<string, boolean> | undefined;

  return (
    <div className="space-y-6">
      <section className="panel-bosque entra relative isolate overflow-hidden px-6 py-10 sm:px-10 lg:py-14" style={{ ["--i" as string]: 0 } as React.CSSProperties}>
        <FondoCanales className="-z-10" />
        <MarcaDeAgua className="-bottom-20 left-1/3" opacidad={0.05} />
        <div className="grid items-center gap-8 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="etiqueta !text-menta/80">Plataforma de inteligencia y calidad de datos comerciales</p>
            <h1 className="titular mt-4 text-[clamp(2.4rem,5.4vw,4.4rem)] leading-[1.02] text-blanco">
              Inteligencia comercial,<br /><span className="text-menta">datos confiables.</span>
            </h1>
            <p className="lectura mt-5 text-lg leading-relaxed text-menta/90">
              KOVA convierte información de tienda física y online —dispersa e inconsistente— en datos trazables que sí
              sirven para decidir. Cada registro cuenta su historia: de dónde vino, qué se corrigió y por qué fue aceptado o apartado.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/panel" className="inline-flex min-h-12 items-center gap-2 rounded-full bg-ambar px-6 font-bold text-bosque transition hover:brightness-105 active:scale-[0.98]">
                Abrir panel ejecutivo <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link to="/etl" className="inline-flex min-h-12 items-center gap-2 rounded-full px-6 font-bold text-blanco ring-1 ring-menta/40 transition hover:bg-menta/10">
                <Workflow size={18} aria-hidden="true" /> Ir al Centro ETL
              </Link>
            </div>
          </div>
          <IlustracionConvergencia className="mx-auto w-full max-w-[560px]" fisica={fis?.entrada} online={onl?.entrada} limpias={t.limpias} cuarentena={t.cuarentena} />
        </div>
      </section>

      {!datos.hay_datos ? (
        <EstadoVacio titulo="KOVA está lista para procesar" accion={<Link to="/etl" className="inline-flex min-h-11 items-center rounded-full bg-bosque px-5 text-sm font-bold text-blanco">Ejecutar el pipeline</Link>}>
          La base de datos todavía no tiene una carga completada. Ejecuta el pipeline desde el Centro ETL.
        </EstadoVacio>
      ) : (
        <div className="grid gap-5 lg:grid-cols-12">
          <article className="panel entra p-6 lg:col-span-5" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
            <div className="flex items-start justify-between gap-3">
              <div><p className="etiqueta">Última ejecución completada</p>
                <h2 className="titular mt-1 text-2xl text-bosque">{u ? fFechaHora(u.fin) : "—"}</h2></div>
              {u && <Insignia tono="ok"><CheckCircle2 size={13} aria-hidden="true" />Completada</Insignia>}
            </div>
            <dl className="num mt-6 grid grid-cols-2 gap-x-6 gap-y-5">
              <div><dt className="etiqueta">Recibidos</dt><dd className="font-display text-3xl font-bold text-bosque">{fEntero(t.entrada)}</dd></div>
              <div><dt className="etiqueta">Aceptación</dt><dd className="font-display text-3xl font-bold text-menta-texto">{fPct(t.tasa_aceptacion)}</dd></div>
              <div><dt className="etiqueta">Válidas</dt><dd className="font-display text-3xl font-bold text-bosque">{fEntero(t.limpias)}</dd></div>
              <div><dt className="etiqueta">En cuarentena</dt><dd className="font-display text-3xl font-bold text-coral-texto">{fEntero(t.cuarentena)}</dd></div>
            </dl>
            <p className="mt-5 border-t border-borde pt-4 text-sm text-suave">
              Duración medida: <b className="num text-bosque">{fDuracion(u?.duracion_s)}</b> · lote <span className="num">{u?.lote_id}</span>
            </p>
          </article>

          <article className="panel entra p-6 lg:col-span-4" style={{ ["--i" as string]: 2 } as React.CSSProperties}>
            <p className="etiqueta">Integridad de las fuentes</p>
            <h2 className="titular mt-1 text-2xl text-bosque">Originales intactos</h2>
            <p className="mt-2 text-sm text-suave">Cada ejecución compara la huella SHA-256 de los archivos oficiales con la registrada en el diagnóstico.</p>
            <ul className="mt-4 space-y-2.5">
              {integridad ? Object.entries(integridad).map(([archivo, ok]) => (
                <li key={archivo} className="flex items-center gap-2.5 rounded-xl bg-superficie-2 px-3 py-2 text-sm">
                  {ok ? <CheckCircle2 size={17} className="shrink-0 text-menta-texto" aria-hidden="true" /> : <CircleAlert size={17} className="shrink-0 text-coral-texto" aria-hidden="true" />}
                  <span className="min-w-0 truncate font-medium">{archivo}</span>
                  <span className="sr-only">{ok ? "verificado" : "modificado"}</span>
                </li>
              )) : <li className="text-sm text-suave">Sin verificación registrada en la última ejecución.</li>}
            </ul>
          </article>

          <article className="panel entra relative flex flex-col justify-between overflow-hidden p-6 lg:col-span-3" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
            <div>
              <p className="etiqueta">Las siete fases</p>
              <h2 className="titular mt-1 text-2xl text-bosque">Un recorrido</h2>
              <div className="mt-4 flex gap-1.5" role="img" aria-label={`Estado de las siete fases: ${estado?.fases.map((f) => `${f.nombre} ${f.estado.toLowerCase()}`).join(", ") ?? "sin datos"}`}>
                {(estado?.fases ?? Array.from({ length: 7 }, () => null)).map((f, i) => (
                  <span key={i} className={`h-9 flex-1 rounded-lg ${f ? COLOR_FASE[f.estado] : "skeleton"}`} title={f ? `${f.numero}. ${f.nombre}` : undefined} />
                ))}
              </div>
              <p className="mt-3 text-sm text-suave">Diagnóstico, faltantes, outliers, integración, transformación, validación y carga.</p>
            </div>
            <Link to="/etl" className="mt-5 inline-flex min-h-11 items-center gap-1.5 font-bold text-petroleo hover:underline">Ver el flujo completo <ArrowRight size={16} aria-hidden="true" /></Link>
          </article>

          <Link to="/cuarentena" className="panel-aviso entra group relative flex items-center justify-between gap-4 overflow-hidden p-6 transition hover:shadow-suave lg:col-span-12" style={{ ["--i" as string]: 4 } as React.CSSProperties}>
            <div className="flex items-center gap-4">
              <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-[#fbf0dc] text-ambar-texto"><ShieldAlert aria-hidden="true" /></span>
              <p className="text-[1.02rem]"><b className="font-display text-xl text-bosque">{fEntero(t.cuarentena)} registros</b> fueron apartados en cuarentena con sus motivos y su registro original. Nada se elimina en silencio.</p>
            </div>
            <ArrowRight className="shrink-0 text-ambar-texto transition group-hover:translate-x-1" aria-hidden="true" />
          </Link>
        </div>
      )}
    </div>
  );
}
