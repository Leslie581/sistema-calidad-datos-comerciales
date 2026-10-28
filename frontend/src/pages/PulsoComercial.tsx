import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, FilterX, Info } from "lucide-react";
import { FondoPulso } from "../components/brand/Fondos";
import { IconoCategoria } from "../components/brand/Ilustraciones";
import { MarcaDeAgua } from "../components/brand/Marca";
import { AvisoAtipicas, CanalesPulso, ComparacionMeses, EncabezadoDiagnostico, ListaMensajes, SerieComercial, Variacion, type MetricaSerie } from "../components/pulso/Pulso";
import { Insignia, NumeroAnimado } from "../components/ui/Basicos";
import { CampoFecha, Segmentado } from "../components/ui/Controles";
import { EstadoError, EstadoVacio, PantallaCarga } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useFiltros } from "../hooks/useFiltros";
import { useSistema } from "../hooks/sistema";
import { fEntero, fFecha, fMXN, fMXNCorto } from "../lib/format";
import { api, ErrorApi } from "../services/api";
import type { ModoComparacion } from "../services/tipos";

const DEFECTO = { comparacion: "equivalente", estados: "todas" };

function SelectorSimple({ etiqueta, valor, alCambiar, opciones }: { etiqueta: string; valor: string; alCambiar: (v: string) => void; opciones: { valor: string; texto: string }[] }) {
  const id = useId();
  return (
    <div className="flex min-w-[210px] flex-col gap-1">
      <label htmlFor={id} className="etiqueta">{etiqueta}</label>
      <select id={id} value={valor} onChange={(e) => alCambiar(e.target.value)} className="h-11 rounded-full border border-borde-fuerte bg-blanco px-4 text-sm font-medium text-grafito focus:border-petroleo">
        {opciones.map((o) => <option key={o.valor} value={o.valor}>{o.texto}</option>)}
      </select>
    </div>
  );
}

export default function PulsoComercial() {
  const { ciclo } = useSistema();
  const f = useFiltros(DEFECTO);
  const [metrica, setMetrica] = useState<MetricaSerie>("importe");
  const [ordenProd, setOrdenProd] = useState<"importe" | "unidades" | "transacciones">("importe");

  const personalizado = !!(f.valor("desde") && f.valor("hasta"));
  const params = {
    mes: personalizado ? undefined : f.valor("mes") || undefined,
    desde: personalizado ? f.valor("desde") : undefined,
    hasta: personalizado ? f.valor("hasta") : undefined,
    canal: f.valor("canal") || undefined,
    comparacion: personalizado && f.valor("comparacion") === "mes_anterior_completo" ? "equivalente" : f.valor("comparacion"),
    estados: f.valor("estados"),
  };
  const clave = JSON.stringify(params);
  const opc = useApi((s) => api.comercialOpciones(s), [ciclo]);
  const res = useApi((s) => api.comercialResumen(params, s), [clave, ciclo]);
  const tend = useApi((s) => api.comercialTendencia(params, s), [clave, ciclo]);
  const prod = useApi((s) => api.comercialProductos({ ...params, orden: ordenProd, limite: 8 }, s), [clave, ordenProd, ciclo]);

  const reiniciar = () => f.limpiar();
  const r = res.datos;
  const errorFatal = res.error && !r ? res.error : null;
  const atipicas = r?.diagnostico.mensajes.find((m) => m.id === "atipicas");

  const cambiarPeriodo = (v: string) => {
    if (v === "personalizado") {
      f.cambiar({ mes: "", desde: r?.periodo.inicio ?? opc.datos?.cobertura.inicio ?? "", hasta: r?.periodo.fin ?? opc.datos?.cobertura.fin ?? "" });
    } else f.cambiar({ mes: v, desde: "", hasta: "" });
  };
  const opcionesComparacion: { valor: ModoComparacion; texto: string }[] = personalizado
    ? [{ valor: "equivalente", texto: "Período inmediato anterior" }, { valor: "ninguna", texto: "Sin comparación" }]
    : [{ valor: "equivalente", texto: "Mismos días del mes anterior" }, { valor: "mes_anterior_completo", texto: "Mes anterior completo" }, { valor: "ninguna", texto: "Sin comparación" }];

  return (
    <div className="space-y-6">
      <section className="panel-bosque entra relative isolate overflow-hidden px-6 py-8 sm:px-10">
        <FondoPulso className="-z-10" />
        <MarcaDeAgua className="-right-24 -top-28" opacidad={0.06} />
        <p className="etiqueta !text-menta/80">Resumen · ventas</p>
        <h1 className="titular mt-2 text-[clamp(2rem,4vw,3.2rem)] text-blanco">Pulso comercial</h1>
        <p className="lectura mt-2 text-menta/90">Cómo se comportan las ventas de las transacciones conformes: importe, ritmo, canales y productos.</p>
        {r && (
          <p className="mt-4 text-sm leading-relaxed text-menta/80" aria-label="Fechas efectivas">
            <strong className="font-bold text-blanco">{r.periodo.etiqueta}</strong>
            <span className="num"> · {r.periodo.dias} días, del {fFecha(r.actual.primera_venta)} al {fFecha(r.actual.ultima_venta)}</span>
            {r.periodo.parcial && <span className="font-bold text-ambar"> · Período parcial{r.periodo.dias_calendario_mes ? ` (${r.periodo.dias} de ${r.periodo.dias_calendario_mes} días del mes)` : ""}</span>}
            {r.anterior && <span className="block">frente a {r.anterior.etiqueta}{r.homogeneo ? " · comparación homogénea" : " · NO homogénea"}</span>}
          </p>
        )}
      </section>

      <section className="panel entra p-4 sm:p-5" aria-label="Filtros del pulso comercial" style={{ ["--i" as string]: 1 } as React.CSSProperties}>
        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          <SelectorSimple etiqueta="Período" valor={personalizado ? "personalizado" : f.valor("mes") || opc.datos?.mes_por_defecto || ""} alCambiar={cambiarPeriodo}
            opciones={[...(opc.datos?.meses ?? []).map((m) => ({ valor: m.mes, texto: `${m.etiqueta}${m.parcial ? " (parcial)" : ""}` })), { valor: "personalizado", texto: "Rango personalizado" }]} />
          {personalizado && (
            <>
              <CampoFecha etiqueta="Desde" valor={f.valor("desde")} alCambiar={(v) => f.cambiar({ desde: v })} min={opc.datos?.cobertura.inicio ?? undefined} max={f.valor("hasta") || opc.datos?.cobertura.fin || undefined} />
              <CampoFecha etiqueta="Hasta" valor={f.valor("hasta")} alCambiar={(v) => f.cambiar({ hasta: v })} min={f.valor("desde") || opc.datos?.cobertura.inicio || undefined} max={opc.datos?.cobertura.fin ?? undefined} />
            </>
          )}
          <SelectorSimple etiqueta="Comparar con" valor={params.comparacion} alCambiar={(v) => f.cambiar({ comparacion: v })} opciones={opcionesComparacion} />
          <div className="flex flex-col gap-1"><span className="etiqueta" id="lbl-canal">Canal</span>
            <Segmentado etiqueta="Canal" valor={f.valor("canal") || "ambos"} alCambiar={(v) => f.cambiar({ canal: v === "ambos" ? "" : v })}
              opciones={[{ valor: "ambos", texto: "Ambos" }, { valor: "FISICA", texto: "Física" }, { valor: "ONLINE", texto: "Online" }]} /></div>
          <div className="flex flex-col gap-1"><span className="etiqueta" id="lbl-estados">Ventas</span>
            <Segmentado etiqueta="Qué pedidos cuentan" valor={f.valor("estados")} alCambiar={(v) => f.cambiar({ estados: v })}
              opciones={[{ valor: "todas", texto: "Todas las conformes" }, { valor: "efectivas", texto: "Solo efectivas", aria: "Solo ventas efectivas: excluye pedidos cancelados y devueltos" }]} /></div>
          {f.hayFiltros && <button type="button" onClick={reiniciar} className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-bold text-petroleo hover:bg-superficie-2"><FilterX size={16} aria-hidden="true" />Restablecer</button>}
        </div>
        {opc.datos && <p className="mt-3 text-xs text-suave">Datos disponibles del {fFecha(opc.datos.cobertura.inicio)} al {fFecha(opc.datos.cobertura.fin)}. Por omisión se muestra el último mes con información, no el mes actual del sistema.</p>}
      </section>

      {errorFatal ? (
        <ErrorSeleccion error={errorFatal} alRestablecer={reiniciar} alReintentar={res.recargar} />
      ) : !r ? <PantallaCarga etiqueta="Calculando el pulso comercial" /> : (
        <div className={`space-y-6 transition-opacity ${res.cargando ? "opacity-60" : ""}`} aria-busy={res.cargando}>
          {r.actual.transacciones === 0 && <EstadoVacio titulo="Sin ventas en este período">No hay transacciones conformes en {r.periodo.etiqueta} con los filtros elegidos. Prueba con otro período o canal.</EstadoVacio>}

          <div className="grid gap-5 lg:grid-cols-12">
            <section className="panel entra relative overflow-hidden p-6 sm:p-8 lg:col-span-7" aria-labelledby="t-importe" style={{ ["--i" as string]: 2 } as React.CSSProperties}>
              <MarcaDeAgua className="-bottom-24 -right-16" opacidad={0.045} />
              <p className="etiqueta">Importe vendido en MXN</p>
              <h2 id="t-importe" className="sr-only">Importe vendido</h2>
              <p className="num mt-2 font-display text-[clamp(2.6rem,6vw,4.6rem)] font-extrabold leading-none tracking-tight text-bosque">
                <NumeroAnimado valor={r.actual.importe} formato={(n) => fMXNCorto(n)} />
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Variacion valor={r.variaciones.importe_pct} grande />
                {r.anterior_kpis && <span className="num text-sm text-suave">antes {fMXN(r.anterior_kpis.importe)} · {r.anterior?.etiqueta}</span>}
              </div>
              <p className="mt-5 flex items-start gap-2 text-xs text-suave"><Info size={14} className="mt-0.5 shrink-0" aria-hidden="true" /><span>{r.definicion_importe.texto} {r.definicion_importe.no_es}</span></p>
            </section>

            <section className="panel entra p-6 lg:col-span-5" aria-labelledby="t-diag" style={{ ["--i" as string]: 3 } as React.CSSProperties}>
              <p className="etiqueta mb-3" id="t-diag">¿Cómo va mi negocio?</p>
              <EncabezadoDiagnostico estado={r.diagnostico.estado} titular={r.diagnostico.titular} />
              {atipicas && <AvisoAtipicas mensaje={atipicas} />}
              <details className="group mt-4 rounded-2xl bg-superficie-2 p-3.5">
                <summary className="flex min-h-9 cursor-pointer list-none items-center gap-2 text-sm font-bold text-petroleo"><Info size={15} aria-hidden="true" />Cómo se determinó<ChevronDown size={15} className="ml-auto transition group-open:rotate-180" aria-hidden="true" /></summary>
                <div className="mt-2 space-y-1.5 text-sm leading-relaxed text-suave">
                  <p><b className="text-bosque">Variación</b> = ((importe actual − importe anterior) ÷ importe anterior) × 100, solo si ambos períodos son homogéneos (mismos días, con datos completos) y el anterior es mayor que cero.</p>
                  <p>Criterios <b className="text-bosque">propios de KOVA</b> (no son estándares oficiales; configurables): aumento si ≥ +{r.criterios.umbral_crecimiento_pct} %, disminución si ≤ {String(r.criterios.umbral_disminucion_pct).replace("-", "−")} %, estable entre ambos; conclusión solo con al menos {r.criterios.min_transacciones_periodo} transacciones por período; canal «concentra» desde {r.criterios.participacion_dominante_pct} %; «mejor desempeño» con una brecha de {r.criterios.brecha_canales_pp} puntos; alerta de atípicas desde {r.criterios.atipicas_relevantes_pct} % del importe.</p>
                </div>
              </details>
            </section>
          </div>

          <section aria-label="Interpretación" className="entra" style={{ ["--i" as string]: 4 } as React.CSSProperties}>
            <ListaMensajes mensajes={r.diagnostico.mensajes.filter((m) => m.id !== "atipicas")} />
          </section>

          <section className="grid gap-4 sm:grid-cols-3" aria-label="Indicadores comparados">
            {[
              { et: "Transacciones conformes", v: fEntero(r.actual.transacciones), ant: r.anterior_kpis ? fEntero(r.anterior_kpis.transacciones) : null, var: r.variaciones.transacciones_pct },
              { et: "Ticket promedio", v: fMXN(r.actual.ticket_promedio), ant: r.anterior_kpis ? fMXN(r.anterior_kpis.ticket_promedio) : null, var: r.variaciones.ticket_promedio_pct },
              { et: "Promedio diario", v: fMXNCorto(r.actual.promedio_diario), ant: r.anterior_kpis ? fMXNCorto(r.anterior_kpis.promedio_diario) : null, var: r.variaciones.promedio_diario_pct },
            ].map((k, i) => (
              <div key={k.et} className="panel entra p-5" style={{ ["--i" as string]: 5 + i } as React.CSSProperties}>
                <p className="etiqueta">{k.et}</p>
                <p className="num mt-1 font-display text-3xl font-bold text-bosque">{k.v}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2"><Variacion valor={k.var} />{k.ant && <span className="num text-xs text-suave">antes {k.ant}</span>}</div>
              </div>
            ))}
          </section>

          <section className="panel entra p-5 sm:p-6" aria-labelledby="t-serie" style={{ ["--i" as string]: 6 } as React.CSSProperties}>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <div><p className="etiqueta">Evolución</p><h2 id="t-serie" className="titular mt-1 text-2xl text-bosque">Ventas por día</h2></div>
              <Segmentado etiqueta="Métrica de la gráfica" valor={metrica} alCambiar={setMetrica}
                opciones={[{ valor: "importe", texto: "Importe" }, { valor: "transacciones", texto: "Transacciones" }, { valor: "ticket", texto: "Ticket" }, { valor: "acumulado", texto: "Acumulado" }]} />
            </div>
            {tend.datos ? <SerieComercial dias={tend.datos.dias} metrica={metrica} periodo={tend.datos.periodo} anterior={tend.datos.anterior} /> : tend.error ? <EstadoError error={tend.error} alReintentar={tend.recargar} /> : <PantallaCarga etiqueta="Cargando la serie diaria" />}
            <p className="mt-2 text-xs text-suave">Los días se alinean por posición dentro del período (día 1 con día 1). Los días sin ventas dentro de los datos aparecen en cero; los días fuera de la cobertura no se dibujan.</p>
          </section>

          <div className="grid gap-5 lg:grid-cols-12">
            <section className="panel entra p-6 lg:col-span-7" aria-labelledby="t-canal" style={{ ["--i" as string]: 7 } as React.CSSProperties}>
              <p className="etiqueta">Canales</p><h2 id="t-canal" className="titular mb-4 mt-1 text-2xl text-bosque">Física frente a online</h2>
              <CanalesPulso canales={r.canales} />
              {f.valor("canal") && <p className="mt-3 text-xs text-suave">Esta comparación muestra siempre ambos canales, aunque filtres uno arriba.</p>}
            </section>
            <section className="panel entra p-6 lg:col-span-5" aria-labelledby="t-mes" style={{ ["--i" as string]: 8 } as React.CSSProperties}>
              <p className="etiqueta">Comparación por mes</p><h2 id="t-mes" className="titular mb-4 mt-1 text-2xl text-bosque">Meses disponibles</h2>
              {tend.datos ? <ComparacionMeses meses={tend.datos.meses} seleccionado={opc.datos?.mes_por_defecto && !personalizado ? f.valor("mes") || opc.datos.mes_por_defecto : null} /> : <PantallaCarga etiqueta="Cargando meses" />}
            </section>
          </div>

          <section className="panel entra p-5 sm:p-6" aria-labelledby="t-prod" style={{ ["--i" as string]: 9 } as React.CSSProperties}>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div><p className="etiqueta">Productos destacados</p><h2 id="t-prod" className="titular mt-1 text-2xl text-bosque">Quién aporta más</h2></div>
              <Segmentado etiqueta="Ordenar productos por" valor={ordenProd} alCambiar={setOrdenProd} opciones={[{ valor: "importe", texto: "Importe" }, { valor: "unidades", texto: "Unidades" }, { valor: "transacciones", texto: "Transacciones" }]} />
            </div>
            {prod.error && !prod.datos ? <EstadoError error={prod.error} alReintentar={prod.recargar} /> : !prod.datos ? <PantallaCarga etiqueta="Cargando productos" /> : (
              <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
                <div className="scroll-fino overflow-x-auto rounded-2xl border border-borde">
                  <table className="tabla min-w-[620px]">
                    <caption className="sr-only">Productos destacados del período</caption>
                    <thead><tr><th scope="col">#</th><th scope="col">Producto</th><th scope="col" className="der">Importe MXN</th><th scope="col" className="der">Unid.</th><th scope="col" className="der">Trans.</th><th scope="col" style={{ minWidth: 130 }}>Participación</th></tr></thead>
                    <tbody>
                      {prod.datos.productos.map((p, i) => (
                        <tr key={p.id_producto}>
                          <td className="num text-suave">{i + 1}</td>
                          <td><span className="flex items-center gap-2.5"><IconoCategoria categoria={p.categoria} tam={30} /><span className="min-w-0"><span className="block truncate font-bold text-bosque">{p.nombre_producto}</span><span className="num text-xs text-suave">{p.id_producto} · {p.categoria}</span></span></span></td>
                          <td className="num der font-bold text-bosque">{fMXN(p.importe)}</td><td className="num der">{fEntero(p.unidades)}</td><td className="num der">{fEntero(p.transacciones)}</td>
                          <td><span className="flex items-center gap-2"><span className="h-2.5 flex-1 overflow-hidden rounded-full bg-superficie-2"><span className="block h-full rounded-full bg-petroleo" style={{ width: `${p.participacion_pct ?? 0}%` }} /></span><span className="num w-12 text-right text-xs">{p.participacion_pct?.toFixed(1)} %</span></span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <h3 className="etiqueta mb-3">Categorías con mayor participación</h3>
                  <ul className="space-y-3">
                    {prod.datos.categorias.map((c) => (
                      <li key={c.categoria}>
                        <div className="flex items-center justify-between gap-2 text-sm"><span className="flex items-center gap-2 font-bold text-bosque"><IconoCategoria categoria={c.categoria} tam={24} />{c.categoria}</span><span className="num text-suave">{fMXNCorto(c.importe)} · <b className="text-bosque">{c.participacion_pct?.toFixed(1)} %</b></span></div>
                        <span className="mt-1 block h-2 overflow-hidden rounded-full bg-superficie-2"><span className="block h-full rounded-full bg-ambar" style={{ width: `${c.participacion_pct ?? 0}%` }} /></span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-xs text-suave">{fEntero(prod.datos.productos_distintos)} productos distintos vendidos. {prod.datos.nota}</p>
                </div>
              </div>
            )}
          </section>

          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-suave">
            <Insignia tono="neutro">Campo: {r.definicion_importe.campo}</Insignia>
            <span>Para evaluar calidad de datos o distribuciones con recorte estadístico, usa el <Link to="/panel" className="font-bold text-petroleo underline">Panel ejecutivo</Link>.</span>
          </p>
        </div>
      )}
    </div>
  );
}

function ErrorSeleccion({ error, alRestablecer, alReintentar }: { error: ErrorApi; alRestablecer: () => void; alReintentar: () => void }) {
  const filtroInvalido = error.codigo === "MES_SIN_DATOS" || error.codigo === "PARAMETRO_INVALIDO";
  return (
    <div className="space-y-3">
      <EstadoError error={error} alReintentar={alReintentar} />
      {filtroInvalido && <div className="text-center"><button type="button" onClick={alRestablecer} className="min-h-11 rounded-full bg-bosque px-5 text-sm font-bold text-blanco">Restablecer filtros</button></div>}
    </div>
  );
}
