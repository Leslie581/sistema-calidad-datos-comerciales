import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Info } from "lucide-react";
import { BarrasMotivos, ComparacionCanales, SaludAnillo, SegmentosCanal, SerieDiaria } from "../components/charts/Graficos";
import { FondoCanales } from "../components/brand/Fondos";
import { MarcaDeAgua } from "../components/brand/Marca";
import { Encabezado, Insignia, NumeroAnimado } from "../components/ui/Basicos";
import { Segmentado } from "../components/ui/Controles";
import { EstadoError, EstadoVacio, PantallaCarga } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useSistema } from "../hooks/sistema";
import { fDuracion, fEntero, fFechaHora, fMXN, fMXNCorto, fPct } from "../lib/format";
import { api } from "../services/api";

export default function Panel() {
  const { ciclo } = useSistema();
  const { datos, error, recargar } = useApi((s) => api.dashboard(s), [ciclo]);
  const [metrica, setMetrica] = useState<"importe" | "n">("importe");
  const navegar = useNavigate();
  if (error && !datos) return <EstadoError error={error} alReintentar={recargar} />;
  if (!datos) return <PantallaCarga />;
  if (!datos.hay_datos) {
    return <EstadoVacio titulo="Aún no hay una carga completada" accion={<Link to="/etl" className="inline-flex min-h-11 items-center rounded-full bg-bosque px-5 text-sm font-bold text-blanco">Ir al Centro ETL</Link>}>
      Cuando el pipeline termine una ejecución, aquí verás la salud de los datos, los canales y los motivos de rechazo.</EstadoVacio>;
  }
  const { totales: t, salud, ultima_ejecucion: u, indicadores: ind } = datos;
  const topCategoria = datos.categorias[0];

  return (
    <div className="space-y-6">
      <Encabezado etiqueta="Panel ejecutivo" titulo="Cómo están tus datos comerciales"
        acciones={<Insignia tono="info">Última carga · {fFechaHora(u?.fin)}</Insignia>}>
        Visión de la última ejecución completada: qué entró, qué quedó listo para analizar y qué se apartó, con sus razones.
      </Encabezado>

      {/* Bloque protagonista */}
      <section className="panel-bosque entra relative isolate overflow-hidden p-6 sm:p-8" style={{ ["--i" as string]: 0 } as React.CSSProperties}>
        <FondoCanales className="-z-10 opacity-70" />
        <MarcaDeAgua className="-right-20 -top-16" opacidad={0.06} />
        <div className="grid items-center gap-8 md:grid-cols-[auto_1fr]">
          {salud && <div className="mx-auto"><SaludAnillo salud={salud} /></div>}
          <div>
            <p className="etiqueta !text-menta/80">Salud de los datos</p>
            <p className="titular mt-2 text-[clamp(1.6rem,3vw,2.4rem)] leading-tight text-blanco">
              {salud?.valor != null ? <>{fPct(salud.valor, 0)} de lo que llegó estaba bien <span className="text-menta">desde el origen</span></> : "Sin indicador disponible"}
            </p>
            <dl className="num mt-6 grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
              {[["Recibidos", <NumeroAnimado key="e" valor={t.entrada} formato={(n) => fEntero(Math.round(n))} />, ""],
                ["Válidas", <NumeroAnimado key="l" valor={t.limpias} formato={(n) => fEntero(Math.round(n))} />, "text-menta"],
                ["Cuarentena", <NumeroAnimado key="c" valor={t.cuarentena} formato={(n) => fEntero(Math.round(n))} />, "text-[#f2b6ac]"],
                ["Aceptación", fPct(t.tasa_aceptacion), "text-ambar"]].map(([et, val, cl]) => (
                <div key={String(et)}><dt className="text-xs font-bold uppercase tracking-[0.1em] text-menta/70">{et}</dt>
                  <dd className={`font-display text-3xl font-bold ${cl || "text-blanco"}`}>{val}</dd></div>
              ))}
            </dl>
            {salud && (
              <details className="group mt-5 rounded-2xl bg-bosque-2/70 p-4 ring-1 ring-menta/15">
                <summary className="flex min-h-9 cursor-pointer list-none items-center gap-2 text-sm font-bold text-menta">
                  <Info size={16} aria-hidden="true" /> ¿Cómo se calcula la salud de origen?
                  <ChevronDown size={16} className="ml-auto transition group-open:rotate-180" aria-hidden="true" />
                </summary>
                <div className="mt-3 space-y-2 text-sm leading-relaxed text-menta/90">
                  <p><b className="text-blanco">Fórmula:</b> {salud.formula}.</p>
                  <p className="num"><b className="text-blanco">En esta carga:</b> {fEntero(salud.conformes)} ÷ {fEntero(salud.entrada)} = {fPct(salud.valor, 2)} ({fEntero(salud.conformes)} conformes · {fEntero(salud.reparados)} reparados y aceptados · {fEntero(salud.rechazados)} rechazados).</p>
                  <p>{salud.detalle}</p>
                </div>
              </details>
            )}
          </div>
        </div>
      </section>

      {/* Composición editorial */}
      <div className="grid gap-5 lg:grid-cols-12">
        <section className="panel entra p-6 lg:col-span-5" style={{ ["--i" as string]: 1 } as React.CSSProperties} aria-labelledby="t-canales">
          <p className="etiqueta">Canales</p>
          <h2 id="t-canales" className="titular mb-5 mt-1 text-2xl text-bosque">Física frente a online</h2>
          <ComparacionCanales canales={datos.canales} />
        </section>

        <section className="panel entra p-6 lg:col-span-7" style={{ ["--i" as string]: 2 } as React.CSSProperties} aria-labelledby="t-serie">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div><p className="etiqueta">Distribución comercial</p>
              <h2 id="t-serie" className="titular mt-1 text-2xl text-bosque">Ventas por día y canal</h2></div>
            <Segmentado etiqueta="Métrica de la serie" valor={metrica} alCambiar={setMetrica}
              opciones={[{ valor: "importe", texto: "Importe MXN" }, { valor: "n", texto: "Transacciones" }]} />
          </div>
          <SerieDiaria datos={datos.por_dia} metrica={metrica} />
          <p className="mt-2 text-xs text-suave">Importe con capping estadístico (monto_total_mxn_cap) de transacciones válidas, del {datos.indicadores.fecha_min as string} al {datos.indicadores.fecha_max as string}.</p>
        </section>

        {/* tarjetas compactas con jerarquías distintas */}
        <section className="grid gap-4 sm:grid-cols-3 lg:col-span-12" aria-label="Indicadores secundarios">
          <div className="panel entra p-5" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
            <p className="etiqueta">Importe procesado</p>
            <p className="num mt-1 font-display text-3xl font-bold text-bosque">{fMXNCorto(ind.importe_total_mxn as number)}</p>
            <p className="mt-1 text-sm text-suave">Ticket medio {fMXN(ind.ticket_medio_mxn as number)}</p>
          </div>
          <div className="panel entra p-5" style={{ ["--i" as string]: 4 } as React.CSSProperties}>
            <p className="etiqueta">Normalizadas a MXN</p>
            <p className="num mt-1 font-display text-3xl font-bold text-bosque">{fEntero(ind.convertidas_usd as number)}</p>
            <p className="mt-1 text-sm text-suave">pedidos en USD convertidos a $19.50</p>
          </div>
          <div className="panel entra p-5" style={{ ["--i" as string]: 5 } as React.CSSProperties}>
            <p className="etiqueta">Atípicos tratados</p>
            <p className="num mt-1 font-display text-3xl font-bold text-bosque">{fEntero((ind.outliers_monto as number) + (ind.outliers_cantidad as number))}</p>
            <p className="mt-1 text-sm text-suave">{fEntero(ind.outliers_monto as number)} importes y {fEntero(ind.outliers_cantidad as number)} cantidades con capping</p>
          </div>
        </section>

        <section className="panel entra p-6 lg:col-span-4" style={{ ["--i" as string]: 6 } as React.CSSProperties} aria-labelledby="t-seg">
          <p className="etiqueta">Segmentos de importe</p>
          <h2 id="t-seg" className="titular mb-5 mt-1 text-2xl text-bosque">Bajo · Medio · Alto</h2>
          <SegmentosCanal segmentos={datos.segmentos} />
          <p className="mt-4 text-xs text-suave">Terciles calculados sobre la base estadística; consulta los cortes en Calidad de datos.</p>
        </section>

        <section className="panel-aviso entra p-6 lg:col-span-8" style={{ ["--i" as string]: 7 } as React.CSSProperties} aria-labelledby="t-mot">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div><p className="etiqueta !text-ambar-texto">Principales motivos de rechazo</p>
              <h2 id="t-mot" className="titular mt-1 text-2xl text-bosque">{fEntero(datos.motivos.total_registros)} registros apartados</h2></div>
            <Link to="/cuarentena" className="inline-flex min-h-11 items-center gap-1 font-bold text-petroleo hover:underline">Abrir cuarentena <ArrowUpRight size={16} aria-hidden="true" /></Link>
          </div>
          <BarrasMotivos motivos={datos.motivos.por_codigo} alElegir={(c) => navegar(`/cuarentena?codigo=${c}`)} />
          <p className="mt-4 text-xs text-suave">Un registro con varios motivos aparece en cada barra, pero se cuenta una sola vez en el total
            ({fEntero(datos.motivos.con_varios_motivos)} registros tienen más de un motivo).</p>
        </section>

        <section className="panel entra p-6 lg:col-span-6" style={{ ["--i" as string]: 8 } as React.CSSProperties} aria-labelledby="t-an">
          <p className="etiqueta">Anomalías por revisar</p>
          <h2 id="t-an" className="titular mb-3 mt-1 text-2xl text-bosque">Registros con más motivos</h2>
          <ul className="divide-y divide-borde">
            {datos.anomalias.map((a) => (
              <li key={a.id_error}>
                <Link to={`/cuarentena/${a.id_error}`} className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 rounded-lg py-2 hover:bg-superficie-2">
                  <span className="num font-bold text-bosque">{a.id_registro ?? "(sin ID)"}</span>
                  <span className="flex flex-wrap gap-1">{a.codigos.map((c) => <Insignia key={c} tono="aviso">{c}</Insignia>)}</span>
                </Link>
              </li>
            ))}
          </ul>
          {topCategoria && <p className="mt-3 border-t border-borde pt-3 text-sm text-suave">Categoría líder en importe: <b className="text-bosque">{topCategoria.categoria}</b> ({fMXNCorto(topCategoria.importe_mxn)}).</p>}
        </section>

        <section className="panel entra p-6 lg:col-span-6" style={{ ["--i" as string]: 9 } as React.CSSProperties} aria-labelledby="t-act">
          <p className="etiqueta">Actividad reciente</p>
          <h2 id="t-act" className="titular mb-3 mt-1 text-2xl text-bosque">Últimas ejecuciones</h2>
          <ul className="divide-y divide-borde">
            {datos.actividad_reciente.map((e) => (
              <li key={e.lote_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div className="min-w-0"><p className="num truncate text-sm font-bold text-bosque">{e.lote_id}</p><p className="text-xs text-suave">{fFechaHora(e.inicio)} · {fDuracion(e.duracion_s)}</p></div>
                <Insignia tono={e.estado === "COMPLETADO" ? "ok" : "alerta"}>{e.estado === "COMPLETADO" ? "Completada" : "Fallida"}</Insignia>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-borde pt-3 text-xs text-suave">{datos.nota_historial}</p>
        </section>
      </div>
    </div>
  );
}
