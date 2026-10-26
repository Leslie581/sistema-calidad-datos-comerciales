import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { FilterX, ScanLine } from "lucide-react";
import { FondoAislamiento } from "../components/brand/Fondos";
import { MarcaDeAgua } from "../components/brand/Marca";
import { AvisoSoloLectura, LineaTrazabilidad } from "../components/trace/Trazabilidad";
import { Encabezado, Insignia, NumeroAnimado } from "../components/ui/Basicos";
import { Buscador, Paginacion, Seleccion, ThOrden } from "../components/ui/Controles";
import { Drawer } from "../components/ui/Drawer";
import { EstadoError, EstadoVacio, FilasEsqueleto } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFiltros } from "../hooks/useFiltros";
import { useSistema } from "../hooks/sistema";
import { fEntero, fFechaHora, nombreCanal, valorTexto } from "../lib/format";
import { api } from "../services/api";

const DEFECTO = { orden: "registro", direccion: "asc" };
const ETAPAS = [{ valor: "FASE_PREVIA", texto: "Fase previa (banderas)" }, { valor: "PYDANTIC", texto: "Validación Pydantic" }, { valor: "ERROR_INESPERADO", texto: "Error inesperado" }];

export default function Cuarentena() {
  const { id } = useParams();
  const navegar = useNavigate();
  const [busqueda] = useSearchParams();
  const { ciclo } = useSistema();
  const f = useFiltros(DEFECTO);
  const qUrl = f.valor("q");
  const [texto, setTexto] = useState(qUrl);
  const q = useDebounce(texto, 350);
  const { cambiar } = f;
  useEffect(() => { if (q !== qUrl) cambiar({ q }); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const tam = 20;
  const params = { q: qUrl, canal: f.valor("canal"), codigo: f.valor("codigo"), etapa: f.valor("etapa"), orden: f.valor("orden"), direccion: f.valor("direccion"), pagina: f.pagina, tam };
  const lista = useApi((s) => api.cuarentena(params, s), [JSON.stringify(params), ciclo]);
  const resumen = useApi((s) => api.dashboard(s), [ciclo]);
  const facetas = useApi((s) => api.facetas(s), [ciclo]);
  const detalle = useApi(async (s) => (id ? api.cuarentenaDetalle(id, s) : null), [id, ciclo]);

  const ordenar = (c: string) => f.cambiar(f.valor("orden") === c ? { direccion: f.valor("direccion") === "asc" ? "desc" : "asc" } : { orden: c, direccion: c === "motivos" ? "desc" : "asc" });
  const cerrar = () => navegar({ pathname: "/cuarentena", search: busqueda.toString() });
  const m = resumen.datos?.motivos;
  const totalRechazados = resumen.datos?.totales.cuarentena;

  return (
    <div className="space-y-6">
      <section className="panel-aviso entra relative isolate overflow-hidden px-6 py-8 sm:px-10">
        <FondoAislamiento className="-z-10" />
        <MarcaDeAgua className="-right-24 -top-24" opacidad={0.05} />
        <Encabezado etiqueta="Datos · zona de cuarentena" titulo="Registros apartados, con su explicación">
          Aquí no hay datos «perdidos»: cada transacción rechazada conserva su registro original, todos sus motivos y la fase que la detectó. Es una zona de consulta.
        </Encabezado>
        {m && totalRechazados != null && (
          <div className="mt-6 grid gap-6 lg:grid-cols-[auto_1fr]">
            <div className="rounded-3xl bg-bosque px-7 py-5 text-blanco shadow-elevada">
              <p className="etiqueta !text-menta/70">Transacciones rechazadas</p>
              <p className="num font-display text-6xl font-extrabold text-ambar"><NumeroAnimado valor={totalRechazados} formato={(n) => fEntero(Math.round(n))} /></p>
              <p className="text-sm text-menta/80">{fEntero(m.con_varios_motivos)} con más de un motivo · cada una se cuenta una vez</p>
            </div>
            <div>
              <p className="etiqueta mb-2">Filtrar por causa (un registro puede tener varias)</p>
              <ul className="flex flex-wrap gap-2">
                {m.por_codigo.map((c) => (
                  <li key={c.codigo}>
                    <button type="button" aria-pressed={f.valor("codigo") === c.codigo} onClick={() => f.cambiar({ codigo: f.valor("codigo") === c.codigo ? "" : c.codigo })}
                      className={`inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-bold transition ${f.valor("codigo") === c.codigo ? "border-bosque bg-bosque text-blanco" : "border-[#ecd6b0] bg-blanco text-bosque hover:bg-[#fbf0dc]"}`}>
                      {c.codigo}<span className={`num rounded-full px-2 py-0.5 text-xs ${f.valor("codigo") === c.codigo ? "bg-menta/20" : "bg-[#fbf0dc] text-ambar-texto"}`}>{fEntero(c.registros)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-suave">
                {m.por_canal.map((c) => <span key={c.origen}><b className="num text-bosque">{fEntero(c.registros)}</b> {nombreCanal(c.origen).toLowerCase()}</span>)}
                {m.por_etapa.map((e) => <span key={e.etapa}><b className="num text-bosque">{fEntero(e.registros)}</b> detectados en {e.etapa.replace(";", " + ").toLowerCase().replace("_", " ")}</span>)}
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="panel entra p-4 sm:p-5" aria-label="Filtros de cuarentena">
        <div className="flex flex-wrap items-end gap-3">
          <Buscador valor={texto} alCambiar={setTexto} etiqueta="Buscar por ID de transacción" placeholder="Buscar por ID de transacción…" />
          <Seleccion etiqueta="Canal" valor={f.valor("canal")} alCambiar={(v) => f.cambiar({ canal: v })} opciones={[{ valor: "FISICA", texto: "Tienda física" }, { valor: "ONLINE", texto: "Tienda online" }]} />
          <Seleccion etiqueta="Motivo" valor={f.valor("codigo")} alCambiar={(v) => f.cambiar({ codigo: v })} opciones={facetas.datos?.codigos_rechazo ?? []} />
          <Seleccion etiqueta="Detectado en" valor={f.valor("etapa")} alCambiar={(v) => f.cambiar({ etapa: v })} opciones={ETAPAS} />
          {f.hayFiltros && <button type="button" onClick={() => { f.limpiar(); setTexto(""); }} className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-bold text-petroleo hover:bg-superficie-2"><FilterX size={16} aria-hidden="true" />Limpiar</button>}
        </div>
        {lista.datos && <p className="num mt-3 text-sm text-suave" aria-live="polite"><b className="text-bosque">{fEntero(lista.datos.total)}</b> registros en cuarentena con estos filtros</p>}
      </section>

      {lista.error && !lista.datos ? <EstadoError error={lista.error} alReintentar={lista.recargar} /> : (
        <section className="panel entra overflow-hidden" aria-busy={lista.cargando}>
          {!lista.datos ? <FilasEsqueleto filas={10} /> : lista.datos.items.length === 0 ? (
            <div className="p-4"><EstadoVacio titulo="Sin registros con esos filtros" icono={<ScanLine aria-hidden="true" />} accion={<button type="button" className="min-h-11 rounded-full bg-bosque px-5 text-sm font-bold text-blanco" onClick={() => { f.limpiar(); setTexto(""); }}>Quitar filtros</button>}>
              Ningún registro apartado cumple la combinación elegida.</EstadoVacio></div>
          ) : (
            <div className={`scroll-fino max-h-[70vh] overflow-auto transition-opacity ${lista.cargando ? "opacity-60" : ""}`}>
              <table className="tabla min-w-[900px]">
                <caption className="sr-only">Registros en cuarentena</caption>
                <thead><tr>
                  <ThOrden clave="id" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>ID</ThOrden>
                  <ThOrden clave="canal" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>Canal</ThOrden>
                  <ThOrden clave="fila" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>Fila</ThOrden>
                  <ThOrden clave="codigos" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>Motivos</ThOrden>
                  <ThOrden clave="motivos" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>#</ThOrden>
                  <th scope="col">Detectado en</th>
                </tr></thead>
                <tbody>
                  {lista.datos.items.map((r) => (
                    <tr key={r.id_error} data-activa={String(r.id_error) === id}>
                      <td><button type="button" onClick={() => navegar({ pathname: `/cuarentena/${r.id_error}`, search: busqueda.toString() })} aria-label={`Ver detalle de ${r.id_registro ?? "registro sin ID"}, error ${r.id_error}`}
                        className="num min-h-9 font-bold text-petroleo underline-offset-2 hover:underline">{r.id_registro ?? "(sin ID)"}</button></td>
                      <td>{nombreCanal(r.origen)}</td>
                      <td className="num der">{fEntero(r.id_fila_origen)}</td>
                      <td><span className="flex flex-wrap gap-1">{r.codigos.map((c) => <Insignia key={c} tono="aviso">{c}</Insignia>)}</span></td>
                      <td className="num der">{r.num_motivos}</td>
                      <td className="text-xs text-suave">{r.etapas.map((e) => e.toLowerCase().replace("_", " ")).join(" + ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {lista.datos && <Paginacion pagina={lista.datos.pagina} paginas={lista.datos.paginas} total={lista.datos.total} tam={tam} alCambiar={(p) => f.cambiar({ pagina: String(p) }, true)} />}
        </section>
      )}

      <Drawer abierto={!!id} titulo={detalle.datos?.registro.id_registro ?? `Registro #${id ?? ""}`} subtitulo="Detalle de cuarentena" alCerrar={cerrar}>
        {detalle.error ? <EstadoError error={detalle.error} alReintentar={detalle.recargar} /> : !detalle.datos ? <FilasEsqueleto filas={6} /> : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Insignia tono="alerta">Rechazada · {detalle.datos.registro.num_motivos} motivo(s)</Insignia>
              <Insignia tono="neutro">{nombreCanal(detalle.datos.registro.origen)} · fila {detalle.datos.registro.id_fila_origen}</Insignia>
              <Insignia tono="neutro">{fFechaHora(detalle.datos.registro.fecha_cuarentena)}</Insignia>
            </div>
            {detalle.datos.hay_limpia_con_mismo_id && detalle.datos.registro.id_registro && (
              <p className="panel-aviso p-3 text-sm">Existe una transacción <b>limpia</b> con este mismo ID (la primera aparición se conservó).
                <Link className="ml-2 font-bold text-petroleo underline" to={`/transacciones/${detalle.datos.registro.id_registro}`}>ver su recorrido</Link></p>
            )}
            <section>
              <h3 className="etiqueta mb-2">Por qué se apartó</h3>
              <ul className="space-y-2">
                {detalle.datos.detalle.map((d, i) => (
                  <li key={i} className="rounded-2xl border border-[#ecd6b0] bg-[#fdf6ea] p-3.5">
                    <div className="flex flex-wrap items-center gap-2"><Insignia tono="aviso">{d.codigo}</Insignia><span className="text-xs text-suave">{d.etapa === "FASE_PREVIA" ? "detectado en una fase previa" : d.etapa === "PYDANTIC" ? "detectado por Pydantic" : "error inesperado"}{d.campo ? ` · campo ${d.campo}` : ""}</span></div>
                    <p className="mt-1.5 text-sm text-grafito">{d.mensaje}</p>
                    {d.descripcion && <p className="mt-0.5 text-xs text-suave">{d.descripcion}</p>}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h3 className="etiqueta mb-2">Registro crudo</h3>
              {typeof detalle.datos.registro_original === "object" ? (
                <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 rounded-2xl border border-borde bg-blanco p-4 text-sm">
                  {Object.entries(detalle.datos.registro_original).map(([k, v]) => (<div key={k} className="contents"><dt className="font-bold text-suave">{k}</dt><dd className="num break-all">{valorTexto(v)}</dd></div>))}
                </dl>
              ) : <pre className="scroll-fino overflow-x-auto rounded-2xl border border-borde bg-blanco p-4 text-xs">{detalle.datos.registro_original}</pre>}
            </section>
            <section><h3 className="etiqueta mb-3">Trazabilidad</h3><LineaTrazabilidad etapas={detalle.datos.trazabilidad} glosario={detalle.datos.glosario} /></section>
            <AvisoSoloLectura />
          </div>
        )}
      </Drawer>
    </div>
  );
}
