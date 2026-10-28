import { useState } from "react";
import { Info } from "lucide-react";
import { FondoOrden } from "../components/brand/Fondos";
import { Encabezado, Insignia } from "../components/ui/Basicos";
import { Segmentado } from "../components/ui/Controles";
import { EstadoError, EstadoVacio, PantallaCarga } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useSistema } from "../hooks/sistema";
import { fDecimal, fEntero, fMXNCorto } from "../lib/format";
import { api } from "../services/api";
import type { Json } from "../services/tipos";

/** Recta numérica del IQR: caja Q1–Q3, mediana (si existe) y límites; marca los extremos observados fuera de límites. */
const DISTINCION_CORTA: Record<string, string> = {
  originales: "Tal como llegaron.",
  corregidos: "Faltantes e importes arreglados.",
  tratados: "Atípicos recortados con IQR.",
};

function CajaIQR({ q1, q3, li, ls, minimo, maximo, etiqueta, unidad = "" }: { q1: number; q3: number; li: number; ls: number; minimo?: number; maximo?: number; etiqueta: string; unidad?: string }) {
  const lo = Math.min(li, minimo ?? li), hi = Math.max(ls, Math.min(maximo ?? ls, ls * 1.35));
  const x = (v: number) => 20 + ((v - lo) / (hi - lo || 1)) * 560;
  return (
    <svg viewBox="0 0 600 110" role="img" className="w-full"
      aria-label={`${etiqueta}: Q1 ${fDecimal(q1)}, Q3 ${fDecimal(q3)}, límite inferior ${fDecimal(li)}, límite superior ${fDecimal(ls)}${unidad}`}>
      <line x1={x(li)} x2={x(ls)} y1="50" y2="50" stroke="#8A9D94" strokeWidth="2" />
      {[li, ls].map((v, i) => <line key={i} x1={x(v)} x2={x(v)} y1="38" y2="62" stroke="#17352D" strokeWidth="3" strokeLinecap="round" />)}
      <rect x={x(q1)} y="30" width={Math.max(x(q3) - x(q1), 2)} height="40" rx="10" fill="#B8E8CE" stroke="#215548" strokeWidth="2" />
      {maximo != null && maximo > ls && <g><line x1={x(ls)} x2={x(hi)} y1="50" y2="50" stroke="#CB6F61" strokeWidth="2" strokeDasharray="3 5" />
        <circle cx={x(hi)} cy="50" r="6" fill="#CB6F61" /><text x={x(hi) - 4} y="28" textAnchor="end" fontSize="12" fontWeight="700" fill="#A2443A">máx. observado {fDecimal(maximo)}</text></g>}
      <g fontSize="12.5" fill="#202A26" fontWeight="700" className="num" textAnchor="middle">
        <text x={x(li)} y="92">LI {fDecimal(li)}</text><text x={x(q1)} y="20">Q1 {fDecimal(q1)}</text>
        <text x={x(q3)} y="92">Q3 {fDecimal(q3)}</text><text x={x(ls)} y="20" fill="#17352D">LS {fDecimal(ls)}</text>
      </g>
    </svg>
  );
}

function Seccion({ n, titulo, fuente, children, tono = "" }: { n: string; titulo: string; fuente?: string; children: React.ReactNode; tono?: string }) {
  return (
    <section className={`panel entra p-5 sm:p-6 ${tono}`} aria-label={titulo}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div><p className="etiqueta">{n}</p><h2 className="titular mt-1 text-2xl text-bosque">{titulo}</h2></div>
        {fuente && <Insignia tono="neutro" title="De dónde sale esta información">{fuente}</Insignia>}
      </div>
      {children}
    </section>
  );
}

export default function Calidad() {
  const { ciclo } = useSistema();
  const { datos, error, recargar } = useApi((s) => api.calidad(s), [ciclo]);
  const [fuente, setFuente] = useState("fisica");
  if (error && !datos) return <EstadoError error={error} alReintentar={recargar} />;
  if (!datos) return <PantallaCarga />;
  const { limpieza, iqr, transformacion, perfil_antes: perfil, faltantes } = datos;
  if (!limpieza && !perfil) return <EstadoVacio titulo="Sin resultados de calidad todavía">Ejecuta el pipeline para generar el análisis de calidad.</EstadoVacio>;

  const per = perfil?.[fuente] as Json | undefined;
  const nulos: [string, number, number][] = per ? Object.keys(per.nulos).map((c) => [c, per.nulos[c], per.pct_nulos[c]]) : [];
  const mont = iqr?.monto_mxn as Json | undefined;

  return (
    <div className="space-y-6">
      <section className="panel entra relative isolate overflow-hidden px-6 py-8 sm:px-10">
        <FondoOrden className="-z-10" />
        <Encabezado etiqueta="Proceso" titulo="Calidad de datos">
          Qué se corrigió y qué se trató estadísticamente, con resultados reales del pipeline.
        </Encabezado>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {Object.entries(DISTINCION_CORTA).map(([k, v], i) => (
            <div key={k} className="rounded-2xl border border-borde bg-blanco/90 p-4">
              <p className="flex items-center gap-2 font-display font-bold text-bosque"><i className={`size-3 rounded-full ${["bg-salvia", "bg-ambar", "bg-petroleo"][i]}`} aria-hidden="true" />{k[0].toUpperCase() + k.slice(1)}</p>
              <p className="mt-0.5 text-sm text-suave">{v}</p>
            </div>
          ))}
        </div>
      </section>

      {per && (
        <Seccion n="1 · Diagnóstico inicial" titulo="Completitud, tipos y duplicados del archivo crudo">
          <div className="mb-4"><Segmentado etiqueta="Fuente de datos" valor={fuente} alCambiar={setFuente} opciones={[{ valor: "fisica", texto: "Tienda física" }, { valor: "online", texto: "Tienda online" }, { valor: "catalogo", texto: "Catálogo" }]} /></div>
          <dl className="num mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div><dt className="etiqueta">Filas × columnas</dt><dd className="font-display text-2xl font-bold text-bosque">{fEntero(per.filas)} × {per.columnas}</dd></div>
            <div><dt className="etiqueta">Completitud global</dt><dd className="font-display text-2xl font-bold text-menta-texto">{fDecimal(per.completitud_global_pct)} %</dd></div>
            <div><dt className="etiqueta">Duplicados exactos</dt><dd className="font-display text-2xl font-bold text-bosque">{fEntero(per.duplicados_exactos)}</dd></div>
            <div><dt className="etiqueta">Columnas con faltantes</dt><dd className="font-display text-2xl font-bold text-bosque">{nulos.filter((n) => n[1] > 0).length}</dd></div>
          </dl>
          <div className="scroll-fino overflow-x-auto rounded-2xl border border-borde">
            <table className="tabla">
              <caption className="sr-only">Completitud por columna</caption>
              <thead><tr><th scope="col">Columna</th><th scope="col">Tipo detectado</th><th scope="col" className="der">Nulos</th><th scope="col" style={{ minWidth: 180 }}>% de faltantes</th></tr></thead>
              <tbody>{nulos.map(([c, n, pct]) => (
                <tr key={c}><th scope="row" className="!static !bg-transparent !text-[0.9rem] !normal-case !tracking-normal !text-bosque">{c}</th><td>{per.tipos[c]}</td><td className="num der">{fEntero(n)}</td>
                  <td><span className="flex items-center gap-2"><span className="h-2.5 flex-1 overflow-hidden rounded-full bg-superficie-2"><span className={`block h-full rounded-full ${n ? "bg-ambar" : "bg-menta"}`} style={{ width: `${Math.max(pct, n ? 3 : 0)}%` }} /></span><span className="num w-14 text-right text-xs">{fDecimal(pct)} %</span></span></td></tr>))}</tbody>
            </table>
          </div>
          {per.tipos?.order_timestamp && <p className="mt-3 text-xs text-suave">Nota: en el JSON online <code>order_timestamp</code> mezcla texto y números epoch; por eso se normaliza con parseo explícito por formato.</p>}
        </Seccion>
      )}

      {limpieza && (
        <Seccion n="2 · Faltantes e imputación" titulo="Lo que se corrigió, sin borrar el original" fuente={`bitácora del lote ${datos.lote_id}`}>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl bg-superficie-2 p-4"><p className="etiqueta">Duplicados exactos marcados</p><p className="num font-display text-3xl font-bold">{fEntero(limpieza.duplicados_exactos)}</p><p className="mt-1 text-xs text-suave">Se conserva la primera aparición; las demás van a cuarentena (no se borran).</p></div>
            <div className="rounded-2xl bg-superficie-2 p-4"><p className="etiqueta">Importes recalculados</p>
              <p className="num font-display text-3xl font-bold">{fEntero(limpieza.reconstruccion_montos.recalculados_nulo + limpieza.reconstruccion_montos.recalculados_inconsistente)}</p>
              <p className="mt-1 text-xs text-suave">{fEntero(limpieza.reconstruccion_montos.recalculados_nulo)} vacíos + {fEntero(limpieza.reconstruccion_montos.recalculados_inconsistente)} inconsistentes (factor {Object.keys(limpieza.reconstruccion_montos.factores_inconsistencia).join(", ")}×).</p></div>
            <div className="rounded-2xl bg-superficie-2 p-4"><p className="etiqueta">Cantidad imputada con mediana</p><p className="num font-display text-3xl font-bold">{fEntero(limpieza.imputacion_mediana.imputados)}</p>
              <p className="mt-1 text-xs text-suave">Medianas por canal: física {limpieza.imputacion_mediana.medianas_por_canal.FISICA}, online {limpieza.imputacion_mediana.medianas_por_canal.ONLINE}.</p></div>
          </div>
          <h3 className="etiqueta mb-2 mt-5">Etiquetas controladas</h3>
          <ul className="flex flex-wrap gap-2">{Object.entries(limpieza.imputacion_categoricas as Record<string, number>).map(([k, v]) => <li key={k}><Insignia tono="aviso"><span className="num">{fEntero(v)}</span> · {k.replace("→", " → ")}</Insignia></li>)}</ul>
          <p className="mt-3 text-xs text-suave">Los faltantes categóricos no se «inventan»: se rotulan con etiquetas controladas (ANONIMO, SIN_CORREO, SIN_DIRECCION) que indican que el dato no existía.</p>
        </Seccion>
      )}

      {Array.isArray(faltantes) && (
        <Seccion n="3 · MCAR / MAR" titulo="¿Por qué faltan los datos?">
          <p className="mb-4 flex items-start gap-3 rounded-2xl bg-[#e6eef0] p-4 text-sm leading-relaxed text-petroleo"><Info size={18} className="mt-0.5 shrink-0" aria-hidden="true" /><span>{datos.nota_mcar}</span></p>
          <div className="scroll-fino overflow-x-auto rounded-2xl border border-borde">
            <table className="tabla min-w-[760px]">
              <caption className="sr-only">Pruebas de independencia χ² de los faltantes</caption>
              <thead><tr><th scope="col">Canal</th><th scope="col">Columna</th><th scope="col" className="der">Faltantes</th><th scope="col">Comparada con</th><th scope="col" className="der">χ²</th><th scope="col" className="der">gl</th><th scope="col" className="der">p</th><th scope="col">Resultado</th></tr></thead>
              <tbody>{faltantes.flatMap((r: Json) => r.pruebas.map((p: Json, i: number) => (
                <tr key={`${r.origen}-${r.columna}-${p.vs}`}>
                  {i === 0 && <td rowSpan={r.pruebas.length}>{r.origen === "FISICA" ? "Física" : "Online"}</td>}
                  {i === 0 && <td rowSpan={r.pruebas.length} className="font-bold text-bosque">{r.columna}</td>}
                  {i === 0 && <td rowSpan={r.pruebas.length} className="num der">{fEntero(r.faltantes)} ({fDecimal(r.pct_faltantes)} %)</td>}
                  <td>{p.vs}</td><td className="num der">{fDecimal(p.chi2)}</td><td className="num der">{p.gl}</td><td className="num der font-bold">{p.p_valor}</td>
                  <td>{p.p_valor >= 0.05 ? <Insignia tono="info">compatible con MCAR</Insignia> : <Insignia tono="aviso">posible MAR</Insignia>}{p.esperados_menores_5 > 0 && <span className="mt-1 block text-xs text-ambar-texto">{p.esperados_menores_5} celdas con esperado &lt; 5</span>}</td>
                </tr>)))}</tbody>
            </table>
          </div>
        </Seccion>
      )}

      {iqr && (
        <Seccion n="4 · Outliers" titulo="IQR con factor 1.5 y capping" fuente={`bitácora del lote ${datos.lote_id}`}>
          <p className="mb-4 text-sm text-suave">Los límites se calculan solo con la base estadística (<b className="num text-bosque">{fEntero(iqr.base_estadistica.total)}</b> registros sin duplicado, con cantidad &gt; 0, en catálogo y con precio válido). El valor atípico se recorta en una columna aparte; el real se conserva.</p>
          <div className="grid gap-5 lg:grid-cols-2">
            {mont && <div className="rounded-2xl border border-borde p-4"><h3 className="font-display text-lg font-bold text-bosque">Importe MXN unificado</h3>
              <CajaIQR q1={mont.Q1} q3={mont.Q3} li={mont.LI} ls={mont.LS} minimo={mont.min} maximo={mont.max} etiqueta="Importe MXN" unidad=" pesos" />
              <p className="num text-sm text-suave">{fEntero(mont.outliers_superiores)} sobre el límite en la base · {fEntero(mont.recortados)} importes con capping (todas las filas con cantidad &gt; 0). Mediana {fMXNCorto(mont.mediana)}, asimetría {fDecimal(mont.asimetria)}.</p></div>}
            {(["FISICA", "ONLINE"] as const).map((c) => { const q = iqr.cantidad?.[c] as Json; return q && (
              <div key={c} className="rounded-2xl border border-borde p-4"><h3 className="font-display text-lg font-bold text-bosque">Cantidad · {c === "FISICA" ? "tienda física" : "tienda online"}</h3>
                <CajaIQR q1={q.Q1} q3={q.Q3} li={q.LI} ls={q.LS} minimo={q.min} maximo={q.max} etiqueta={`Cantidad ${c}`} unidad=" unidades" />
                <p className="num text-sm text-suave">{q.tope_entero != null ? `Tope entero ${q.tope_entero}` : "Sin tope"} · {fEntero(q.recortados ?? 0)} cantidades recortadas · máximo original {fDecimal(q.max)}.</p></div>); })}
          </div>
        </Seccion>
      )}

      {datos.antes_despues && (
        <Seccion n="5 · Comparación" titulo="Antes y después">
          <div className="scroll-fino overflow-x-auto rounded-2xl border border-borde">
            <table className="tabla min-w-[760px]"><caption className="sr-only">Comparación de calidad antes y después</caption>
              <thead><tr><th scope="col">Métrica</th><th scope="col">Base</th><th scope="col" className="der">Antes</th><th scope="col" className="der">Después</th><th scope="col">Cómo se logró</th></tr></thead>
              <tbody>{datos.antes_despues.map((r) => (
                <tr key={r.metrica}><th scope="row" className="!static !bg-transparent !text-[0.9rem] !normal-case !tracking-normal !text-bosque">{r.metrica}</th><td className="text-xs text-suave">{r.base}</td>
                  <td className="num der">{fDecimal(Number(r.antes))}</td><td className="num der font-bold text-bosque">{fDecimal(Number(r.despues))}</td><td className="text-xs text-suave">{r.como_se_logro}</td></tr>))}</tbody>
            </table>
          </div>
        </Seccion>
      )}

      {transformacion && (
        <Seccion n="6 · Transformación" titulo="Escala Min-Max y segmentos por terciles" fuente={`bitácora del lote ${datos.lote_id}`}>
          <dl className="num grid gap-4 sm:grid-cols-4">
            <div><dt className="etiqueta">Mínimo (→ 0)</dt><dd className="font-display text-2xl font-bold">{fMXNCorto(transformacion.minmax.min)}</dd></div>
            <div><dt className="etiqueta">Máximo (→ 1)</dt><dd className="font-display text-2xl font-bold">{fMXNCorto(transformacion.minmax.max)}</dd></div>
            <div><dt className="etiqueta">Bajo ≤</dt><dd className="font-display text-2xl font-bold">{fMXNCorto(transformacion.segmentos.corte_bajo_medio)}</dd></div>
            <div><dt className="etiqueta">Medio ≤</dt><dd className="font-display text-2xl font-bold">{fMXNCorto(transformacion.segmentos.corte_medio_alto)}</dd></div>
          </dl>
          <p className="mt-3 text-sm text-suave">Calculados sobre {fEntero(transformacion.minmax.n_base)} registros de la base estadística, con el importe ya recortado. Base: {Object.entries(transformacion.segmentos.conteo_base as Record<string, number>).map(([k, v]) => `${k} ${v}`).join(" · ")}.</p>
        </Seccion>
      )}

      {datos.graficas.length > 0 && (
        <Seccion n="7 · Gráficas del análisis" titulo="Capping, visto en los datos">
          <div className="grid gap-5 lg:grid-cols-2">
            {datos.graficas.map((g) => (
              <figure key={g.id} className="m-0 rounded-2xl border border-borde bg-blanco p-3">
                <img src={g.url} alt={`${g.titulo}. ${g.descripcion}`} loading="lazy" className="w-full rounded-xl" />
                <figcaption className="mt-2 px-1 text-sm"><b className="text-bosque">{g.titulo}.</b> <span className="text-suave">{g.descripcion}</span></figcaption>
              </figure>))}
          </div>
        </Seccion>
      )}
      <p className="text-xs text-suave">{datos.fuentes.nota}</p>
    </div>
  );
}
