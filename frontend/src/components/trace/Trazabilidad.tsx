import type { ReactNode } from "react";
import { ArrowRight, Check, CircleAlert, Layers, ShieldAlert, Sparkles, Wrench } from "lucide-react";
import { Insignia } from "../ui/Basicos";
import { fMXN, valorTexto } from "../../lib/format";
import type { DetalleTransaccion, EtapaTraza, MonedaTransaccion } from "../../services/tipos";

const ESTILO: Record<EtapaTraza["estado"], { nodo: string; icono: ReactNode; texto: string; tono: "ok" | "aviso" | "alerta" | "neutro" | "info" }> = {
  ok: { nodo: "bg-petroleo text-blanco", icono: <Check size={15} />, texto: "Aplicada", tono: "info" },
  sin_cambios: { nodo: "bg-superficie-2 text-suave ring-1 ring-borde-fuerte", icono: <Layers size={15} />, texto: "Sin cambios", tono: "neutro" },
  corregido: { nodo: "bg-ambar text-bosque", icono: <Wrench size={15} />, texto: "Corregido", tono: "aviso" },
  tratado: { nodo: "bg-ambar text-bosque", icono: <Sparkles size={15} />, texto: "Tratado", tono: "aviso" },
  aceptado: { nodo: "bg-menta text-bosque", icono: <Check size={15} />, texto: "Aceptado", tono: "ok" },
  rechazado: { nodo: "bg-coral text-blanco", icono: <ShieldAlert size={15} />, texto: "Rechazado", tono: "alerta" },
};

/** Línea de tiempo del recorrido de un registro: solo muestra etapas que el backend pudo documentar con datos reales. */
export function LineaTrazabilidad({ etapas, glosario }: { etapas: EtapaTraza[]; glosario: Record<string, string | null> }) {
  return (
    <ol className="relative space-y-4 pl-1" aria-label="Recorrido del registro">
      {etapas.map((e, i) => {
        const est = ESTILO[e.estado];
        const cambios = e.campos.filter((c) => c.cambio || e.clave === "original" || e.clave === "transformacion" || e.clave === "deteccion");
        return (
          <li key={e.clave} className="relative grid grid-cols-[2.25rem_1fr] gap-3">
            {i < etapas.length - 1 && <span aria-hidden="true" className="absolute left-[1.05rem] top-9 h-[calc(100%-1rem)] w-0.5 bg-borde-fuerte" />}
            <span className={`relative z-10 grid size-9 place-items-center rounded-full ${est.nodo}`} aria-hidden="true">{est.icono}</span>
            <div className="min-w-0 rounded-2xl border border-borde bg-blanco p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-display text-lg font-bold text-bosque">{i + 1}. {e.titulo}</h3>
                <Insignia tono={est.tono}>{est.texto}</Insignia>
              </div>
              <p className="mt-1 text-sm text-suave">{e.descripcion}</p>
              {e.codigos.length > 0 && (
                <ul className="mt-2.5 flex flex-wrap gap-1.5">
                  {e.codigos.map((c) => <li key={c}><Insignia tono={e.estado === "rechazado" ? "alerta" : "aviso"} title={glosario[c] ?? undefined}>{c}</Insignia></li>)}
                </ul>
              )}
              {e.codigos.some((c) => glosario[c]) && (
                <ul className="mt-2 space-y-1 text-xs text-suave">{e.codigos.filter((c) => glosario[c]).map((c) => <li key={c}><b className="text-bosque">{c}:</b> {glosario[c]}</li>)}</ul>
              )}
              {cambios.length > 0 && (
                <div className="scroll-fino mt-3 overflow-x-auto">
                  <table className="tabla !text-[0.85rem]">
                    <caption className="sr-only">Campos de la etapa {e.titulo}</caption>
                    <thead><tr><th scope="col">Campo</th><th scope="col">{e.clave === "original" ? "Valor" : e.clave === "deteccion" ? "Valor detectado" : "Antes"}</th>
                      {e.clave !== "original" && <th scope="col">{e.clave === "deteccion" ? "Motivo" : "Después"}</th>}</tr></thead>
                    <tbody>
                      {cambios.map((c, k) => (
                        <tr key={`${c.campo}-${k}`}>
                          <th scope="row" className="!static !bg-transparent !p-0 !pr-3 !py-2 !text-[0.85rem] !normal-case !tracking-normal !text-grafito align-top font-bold">{c.campo}</th>
                          <td className="num break-all">{e.clave === "original" ? valorTexto(c.antes) : <span className={c.cambio ? "text-suave line-through decoration-coral/60" : ""}>{valorTexto(c.antes)}</span>}</td>
                          {e.clave !== "original" && (
                            <td className="num break-words">
                              <span className="inline-flex items-start gap-1.5">
                                {c.cambio && <ArrowRight size={14} className="mt-1 shrink-0 text-ambar-texto" aria-hidden="true" />}
                                <span className={c.cambio ? "font-bold text-bosque" : ""}>{valorTexto(c.despues)}</span>
                              </span>
                              {c.nota && <span className="mt-0.5 block text-xs text-suave">{c.nota}</span>}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/** Comparación lado a lado: original · normalizado · corregido · con capping · final. */
export function LadoALado({ t }: { t: DetalleTransaccion["transaccion"] }) {
  const moneda = t.moneda_original as string;
  const f = (v: unknown) => (typeof v === "number" ? v : null);
  const filas: { campo: string; original: ReactNode; normalizado: ReactNode; corregido: ReactNode; capping: ReactNode; final: ReactNode }[] = [
    { campo: "Fecha", original: valorTexto(t.fecha_cruda), normalizado: valorTexto(t.fecha_venta), corregido: "—", capping: "—", final: valorTexto(t.fecha_venta) },
    { campo: "Cantidad", original: valorTexto(t.cantidad_origen), normalizado: "—", corregido: valorTexto(t.cantidad), capping: valorTexto(t.cantidad_cap), final: valorTexto(t.cantidad_cap) },
    { campo: "Precio unitario", original: `${fMXN(f(t.precio_unitario_original)).replace("MX$", "").trim()} ${moneda}`, normalizado: fMXN(f(t.precio_unitario_mxn)), corregido: "—", capping: "—", final: fMXN(f(t.precio_unitario_mxn)) },
    { campo: "Importe", original: `${valorTexto(t.monto_total_origen)} ${moneda}`, normalizado: "—", corregido: fMXN(f(t.monto_total_mxn)), capping: fMXN(f(t.monto_total_mxn_cap)), final: fMXN(f(t.monto_total_mxn_cap)) },
    { campo: "Escala · segmento", original: "—", normalizado: "—", corregido: "—", capping: "—", final: `${valorTexto(t.monto_minmax)} · ${valorTexto(t.segmento_importe)}` },
  ];
  const cabeceras = ["Campo", "Original", "Normalizado", "Corregido", "Con capping", "Resultado final"];
  return (
    <div className="scroll-fino overflow-x-auto rounded-2xl border border-borde bg-blanco">
      <table className="tabla">
        <caption className="sr-only">Comparación de valores originales, normalizados, corregidos y con capping</caption>
        <thead><tr>{cabeceras.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>
          {filas.map((r) => (
            <tr key={r.campo}>
              <th scope="row" className="!static !bg-transparent !text-[0.9rem] !normal-case !tracking-normal !text-bosque">{r.campo}</th>
              <td className="num">{r.original}</td><td className="num">{r.normalizado}</td><td className="num">{r.corregido}</td>
              <td className="num">{r.capping}</td><td className="num font-bold text-bosque">{r.final}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const usd = { format: (n: number) => n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) };

/** Conceptos monetarios separados: original en la moneda de origen → tipo de cambio → normalizado a MXN → con capping. */
export function PanelMoneda({ m }: { m: MonedaTransaccion }) {
  if (!m.es_usd) {
    return (
      <p className="rounded-2xl border border-borde bg-blanco p-4 text-sm text-suave" data-moneda="MXN">
        <b className="text-bosque">Registrada originalmente en MXN.</b> No hay conversión de moneda: el precio original ({fMXN(m.precio_original)}) ya está en pesos.
        {m.capping_aplicado && <> El importe con capping ({fMXN(m.importe_mxn_capping)}) difiere del importe normalizado ({fMXN(m.importe_mxn)}).</>}
      </p>
    );
  }
  const filas: { concepto: string; valor: string; nota?: string; destacado?: boolean }[] = [
    { concepto: "Precio original", valor: `$${usd.format(m.precio_original ?? 0)} USD` },
    { concepto: "Importe original reportado", valor: `$${usd.format(m.importe_original ?? 0)} USD`,
      nota: m.importe_original_corregido ? `No coincidía con cantidad × precio ($${usd.format(m.importe_original_coherente ?? 0)} USD); el ETL lo recalculó y conservó el original.` : undefined },
    { concepto: "Tipo de cambio oficial", valor: `1 USD = ${fMXN(m.tipo_cambio)}`, nota: "Paridad fijada por el profesor." },
    { concepto: "Precio convertido", valor: fMXN(m.precio_mxn), nota: "precio USD × tipo de cambio, redondeado a centavos" },
    { concepto: "Importe normalizado a MXN", valor: fMXN(m.importe_mxn), nota: "cantidad × precio convertido (importe comercial)", destacado: true },
    { concepto: "Importe con capping", valor: m.capping_aplicado ? fMXN(m.importe_mxn_capping) : "Sin recorte", nota: m.capping_aplicado ? "Recorte estadístico IQR; no es el importe comercial." : "El importe no superó el límite del IQR." },
  ];
  return (
    <div className="rounded-2xl border border-borde bg-blanco p-4" data-moneda="USD">
      <p className="mb-3 text-sm text-suave"><b className="text-bosque">Registrada originalmente en dólares (USD).</b> Se convirtió a MXN con la paridad oficial; el valor original se conserva.</p>
      <dl className="grid gap-2.5 sm:grid-cols-2">
        {filas.map((f) => (
          <div key={f.concepto} className={`rounded-xl p-3 ${f.destacado ? "bg-[#e3f3ea] ring-1 ring-[#bfe3cf]" : "bg-superficie-2"}`}>
            <dt className="etiqueta">{f.concepto}</dt>
            <dd className="num font-display text-xl font-bold text-bosque">{f.valor}</dd>
            {f.nota && <dd className="mt-0.5 text-xs text-suave">{f.nota}</dd>}
          </div>
        ))}
      </dl>
      {m.formula && <p className="mt-3 text-xs text-suave">{m.formula}.</p>}
    </div>
  );
}

export function AvisoSoloLectura() {
  return (
    <p className="flex items-start gap-2 rounded-xl bg-superficie-2 px-3 py-2 text-xs text-suave">
      <CircleAlert size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
      Vista de solo consulta: KOVA no edita los datos oficiales ni reinserta registros manualmente.
    </p>
  );
}
