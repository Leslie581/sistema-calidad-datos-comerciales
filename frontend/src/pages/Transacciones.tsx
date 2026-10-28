import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { FilterX, Route as IconoRuta } from "lucide-react";
import { AvisoSoloLectura, LadoALado, LineaTrazabilidad, PanelMoneda } from "../components/trace/Trazabilidad";
import { Encabezado, Insignia } from "../components/ui/Basicos";
import { Buscador, CampoFecha, Paginacion, Seleccion, ThOrden } from "../components/ui/Controles";
import { Drawer } from "../components/ui/Drawer";
import { EstadoError, EstadoVacio, FilasEsqueleto } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFiltros } from "../hooks/useFiltros";
import { useSistema } from "../hooks/sistema";
import { fEntero, fFecha, fMXN, fMXNCorto, fMXNp, fUSDp, nombreCanal } from "../lib/format";
import { api } from "../services/api";
import { useEffect, useState } from "react";

const DEFECTO = { orden: "fecha", direccion: "desc" };
const COLOR_SEG = { Bajo: "info", Medio: "ok", Alto: "oscuro" } as const;

export default function Transacciones() {
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
  const params = { q: qUrl, canal: f.valor("canal"), desde: f.valor("desde"), hasta: f.valor("hasta"), categoria: f.valor("categoria"),
    segmento: f.valor("segmento"), estado: f.valor("estado"), orden: f.valor("orden"), direccion: f.valor("direccion"), pagina: f.pagina, tam };
  const lista = useApi((s) => api.transacciones(params, s), [JSON.stringify(params), ciclo]);
  const facetas = useApi((s) => api.facetas(s), [ciclo]);
  const detalle = useApi(async (s) => (id ? api.transaccion(id, s) : null), [id, ciclo]);

  const ordenar = (c: string) => f.cambiar(f.valor("orden") === c ? { direccion: f.valor("direccion") === "asc" ? "desc" : "asc" } : { orden: c, direccion: c === "id" || c === "producto" ? "asc" : "desc" });
  const cerrar = () => navegar({ pathname: "/transacciones", search: busqueda.toString() });
  const d = f.valor("orden"), dir = f.valor("direccion") as "asc" | "desc";

  return (
    <div className="space-y-6">
      <Encabezado etiqueta="Datos" titulo="Transacciones">
        Registros conformes. Selecciona uno para ver su recorrido y su moneda original.
      </Encabezado>

      <section className="panel entra p-4 sm:p-5" aria-label="Filtros">
        <div className="flex flex-wrap items-end gap-3">
          <Buscador valor={texto} alCambiar={setTexto} etiqueta="Buscar por ID de transacción" placeholder="Buscar por ID: POS-2026-0031, WEB-00508…" />
          <Seleccion etiqueta="Canal" valor={f.valor("canal")} alCambiar={(v) => f.cambiar({ canal: v })} opciones={(facetas.datos?.canales ?? []).map((c) => ({ valor: c, texto: nombreCanal(c) }))} />
          <Seleccion etiqueta="Categoría" valor={f.valor("categoria")} alCambiar={(v) => f.cambiar({ categoria: v })} opciones={facetas.datos?.categorias ?? []} />
          <Seleccion etiqueta="Segmento" valor={f.valor("segmento")} alCambiar={(v) => f.cambiar({ segmento: v })} opciones={facetas.datos?.segmentos ?? []} />
          <Seleccion etiqueta="Estado" valor={f.valor("estado")} alCambiar={(v) => f.cambiar({ estado: v })} opciones={facetas.datos?.estados ?? []} />
          <CampoFecha etiqueta="Desde" valor={f.valor("desde")} alCambiar={(v) => f.cambiar({ desde: v })} min={facetas.datos?.rango_fechas[0] ?? undefined} max={f.valor("hasta") || (facetas.datos?.rango_fechas[1] ?? undefined)} />
          <CampoFecha etiqueta="Hasta" valor={f.valor("hasta")} alCambiar={(v) => f.cambiar({ hasta: v })} min={f.valor("desde") || (facetas.datos?.rango_fechas[0] ?? undefined)} max={facetas.datos?.rango_fechas[1] ?? undefined} />
          {f.hayFiltros && <button type="button" onClick={() => { f.limpiar(); setTexto(""); }} className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-bold text-petroleo hover:bg-superficie-2"><FilterX size={16} aria-hidden="true" />Limpiar</button>}
        </div>
        {lista.datos && <p className="num mt-3 text-sm text-suave" aria-live="polite"><b className="text-bosque">{fEntero(lista.datos.total)}</b> transacciones · importe con capping <b className="text-bosque">{fMXNCorto(lista.datos.resumen_filtro.importe_mxn)}</b></p>}
      </section>

      {lista.error && !lista.datos ? <EstadoError error={lista.error} alReintentar={lista.recargar} /> : (
        <section className="panel entra overflow-hidden" style={{ ["--i" as string]: 1 } as React.CSSProperties} aria-busy={lista.cargando}>
          {!lista.datos ? <FilasEsqueleto filas={10} /> : lista.datos.items.length === 0 ? (
            <div className="p-4"><EstadoVacio titulo="Ninguna transacción coincide con los filtros" accion={<button type="button" className="min-h-11 rounded-full bg-bosque px-5 text-sm font-bold text-blanco" onClick={() => { f.limpiar(); setTexto(""); }}>Quitar filtros</button>}>
              Prueba con otro ID, otro rango de fechas o quita algún filtro.</EstadoVacio></div>
          ) : (
            <div className={`scroll-fino max-h-[70vh] overflow-auto transition-opacity ${lista.cargando ? "opacity-60" : ""}`}>
              <table className="tabla min-w-[980px]">
                <caption className="sr-only">Transacciones limpias</caption>
                <thead><tr>
                  <ThOrden clave="id" orden={d} direccion={dir} alOrdenar={ordenar}>ID</ThOrden>
                  <ThOrden clave="canal" orden={d} direccion={dir} alOrdenar={ordenar}>Canal</ThOrden>
                  <ThOrden clave="fecha" orden={d} direccion={dir} alOrdenar={ordenar}>Fecha</ThOrden>
                  <ThOrden clave="producto" orden={d} direccion={dir} alOrdenar={ordenar}>Producto</ThOrden>
                  <ThOrden clave="cantidad" orden={d} direccion={dir} alOrdenar={ordenar} der>Cant.</ThOrden>
                  <ThOrden clave="precio" orden={d} direccion={dir} alOrdenar={ordenar} der>Precio unitario</ThOrden>
                  <ThOrden clave="importe" orden={d} direccion={dir} alOrdenar={ordenar} der>Importe MXN</ThOrden>
                  <ThOrden clave="segmento" orden={d} direccion={dir} alOrdenar={ordenar}>Segmento</ThOrden>
                  <th scope="col">Estado</th>
                </tr></thead>
                <tbody>
                  {lista.datos.items.map((t) => (
                    <tr key={t.id_transaccion} data-activa={t.id_transaccion === id}>
                      <td><button type="button" onClick={() => navegar({ pathname: `/transacciones/${t.id_transaccion}`, search: busqueda.toString() })}
                        className="num inline-flex min-h-9 items-center gap-1.5 font-bold text-petroleo underline-offset-2 hover:underline" aria-label={`Ver recorrido de ${t.id_transaccion}`}>
                        <IconoRuta size={14} aria-hidden="true" />{t.id_transaccion}</button></td>
                      <td><span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-full" style={{ background: t.origen === "FISICA" ? "#215548" : "#D99B45" }} aria-hidden="true" />{nombreCanal(t.origen)}</span></td>
                      <td className="num whitespace-nowrap">{fFecha(t.fecha_venta)}</td>
                      <td><span className="block max-w-[260px] truncate font-medium" title={t.nombre_producto}>{t.nombre_producto}</span><span className="text-xs text-suave">{t.id_producto} · {t.categoria}</span></td>
                      <td className="num der">{fEntero(t.cantidad)}</td>
                      <td className="num der whitespace-nowrap" data-moneda-origen={t.moneda_original}>
                        {t.moneda_original === "USD" ? (
                          <>
                            <span className="block font-bold text-ambar-texto" title="Precio unitario original en dólares">{t.precio_unitario_original == null ? "US$ sin dato" : fUSDp(t.precio_unitario_original)}</span>
                            <span className="block text-xs text-suave" title={`Convertido a pesos con el tipo de cambio oficial de ${t.tipo_cambio_aplicado ?? ""}`}>{fMXNp(t.precio_unitario_mxn)}</span>
                          </>
                        ) : <span className="block">{fMXNp(t.precio_unitario_mxn)}</span>}
                      </td>
                      <td className="num der font-bold text-bosque" title="Importe normalizado a MXN (corregido, sin recorte estadístico). El importe original está en el detalle.">{fMXN(t.monto_total_mxn)}</td>
                      <td><Insignia tono={COLOR_SEG[t.segmento_importe]}>{t.segmento_importe}</Insignia></td>
                      <td>{t.estado_pedido ? <Insignia tono={t.estado_pedido === "CANCELADO" || t.estado_pedido === "DEVUELTO" ? "aviso" : "neutro"}>{t.estado_pedido}</Insignia> : <span className="text-xs text-suave">no aplica</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {lista.datos && <Paginacion pagina={lista.datos.pagina} paginas={lista.datos.paginas} total={lista.datos.total} tam={tam} alCambiar={(p) => f.cambiar({ pagina: String(p) }, true)} />}
        </section>
      )}

      <Drawer abierto={!!id} titulo={id ?? ""} subtitulo="Recorrido de la transacción" alCerrar={cerrar}>
        {detalle.error ? <EstadoError error={detalle.error} alReintentar={detalle.recargar} /> : !detalle.datos ? <FilasEsqueleto filas={6} /> : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Insignia tono="ok">Aceptada</Insignia>
              <Insignia tono="neutro">{nombreCanal(detalle.datos.transaccion.origen)} · fila {detalle.datos.transaccion.id_fila_origen}</Insignia>
              <Insignia tono="info">{detalle.datos.transaccion.nombre_producto}</Insignia>
              <Insignia tono="oscuro">Segmento {detalle.datos.transaccion.segmento_importe}</Insignia>
            </div>
            {detalle.datos.cuarentena_relacionada.length > 0 && (
              <p className="panel-aviso p-3 text-sm">Este ID también aparece <b>{detalle.datos.cuarentena_relacionada.length}</b> vez/veces en cuarentena (repeticiones posteriores del mismo registro). Se conservó la primera aparición.
                {detalle.datos.cuarentena_relacionada.map((c) => <button key={c.id_error} type="button" className="ml-2 font-bold text-petroleo underline" onClick={() => navegar(`/cuarentena/${c.id_error}`)}>ver #{c.id_error}</button>)}</p>
            )}
            <div><h3 className="etiqueta mb-2">Moneda y conversión</h3><PanelMoneda m={detalle.datos.moneda} /></div>
            <div><h3 className="etiqueta mb-2">Lado a lado</h3><LadoALado t={detalle.datos.transaccion} /></div>
            <div><h3 className="etiqueta mb-3">Recorrido</h3><LineaTrazabilidad etapas={detalle.datos.trazabilidad} glosario={detalle.datos.glosario} /></div>
            <AvisoSoloLectura />
          </div>
        )}
      </Drawer>
    </div>
  );
}
