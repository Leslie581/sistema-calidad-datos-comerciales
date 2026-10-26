import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FilterX, LayoutGrid, Rows3, TriangleAlert } from "lucide-react";
import { FondoCatalogo } from "../components/brand/Fondos";
import { IconoCategoria } from "../components/brand/Ilustraciones";
import { Encabezado, Insignia } from "../components/ui/Basicos";
import { Buscador, Paginacion, Segmentado, Seleccion, ThOrden } from "../components/ui/Controles";
import { EstadoError, EstadoVacio, FilasEsqueleto } from "../components/ui/Estados";
import { useApi } from "../hooks/useApi";
import { useDebounce } from "../hooks/useDebounce";
import { useFiltros } from "../hooks/useFiltros";
import { useSistema } from "../hooks/sistema";
import { fEntero, fMXN, fMXNCorto } from "../lib/format";
import { api } from "../services/api";

const DEFECTO = { orden: "id", direccion: "asc", vista: "tarjetas" };

export default function Catalogo() {
  const { ciclo } = useSistema();
  const f = useFiltros(DEFECTO);
  const qUrl = f.valor("q");
  const [texto, setTexto] = useState(qUrl);
  const q = useDebounce(texto, 300);
  const { cambiar } = f;
  useEffect(() => { if (q !== qUrl) cambiar({ q }); }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const vista = f.valor("vista") as "tarjetas" | "tabla";
  const tam = 24;
  const params = { q: qUrl, categoria: f.valor("categoria"), proveedor: f.valor("proveedor"), orden: f.valor("orden"), direccion: f.valor("direccion"), pagina: f.pagina, tam };
  const cat = useApi((s) => api.catalogo(params, s), [JSON.stringify(params), ciclo]);
  const facetas = useApi((s) => api.facetas(s), [ciclo]);
  const ordenar = (c: string) => f.cambiar(f.valor("orden") === c ? { direccion: f.valor("direccion") === "asc" ? "desc" : "asc" } : { orden: c, direccion: ["nombre", "id", "categoria"].includes(c) ? "asc" : "desc" });

  return (
    <div className="space-y-6">
      <section className="panel entra relative isolate overflow-hidden px-6 py-8 sm:px-10">
        <FondoCatalogo className="-z-10" />
        <Encabezado etiqueta="Datos · catálogo maestro" titulo="Catálogo de productos">
          Los 50 productos oficiales son la «verdad» contra la que se valida cada venta. Las ilustraciones son representaciones por categoría; el dataset no incluye fotografías de producto.
        </Encabezado>
        {cat.datos && (
          <ul className="mt-6 flex flex-wrap gap-3" aria-label="Productos por categoría">
            {cat.datos.por_categoria.map((c) => (
              <li key={c.categoria}>
                <button type="button" aria-pressed={f.valor("categoria") === c.categoria} onClick={() => f.cambiar({ categoria: f.valor("categoria") === c.categoria ? "" : c.categoria })}
                  className={`flex min-h-14 items-center gap-3 rounded-2xl border py-2 pl-2 pr-4 text-left transition ${f.valor("categoria") === c.categoria ? "border-bosque bg-bosque text-blanco" : "border-borde bg-blanco hover:border-borde-fuerte"}`}>
                  <IconoCategoria categoria={c.categoria} tam={40} />
                  <span><span className="block font-bold leading-tight">{c.categoria}</span>
                    <span className={`num text-xs ${f.valor("categoria") === c.categoria ? "text-menta/80" : "text-suave"}`}>{c.productos} productos · medio {fMXNCorto(c.precio_medio)}</span></span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel entra p-4 sm:p-5" aria-label="Filtros del catálogo">
        <div className="flex flex-wrap items-end gap-3">
          <Buscador valor={texto} alCambiar={setTexto} etiqueta="Buscar producto por ID o nombre" placeholder="Buscar producto: PROD-025, Hogar Ref…" />
          <Seleccion etiqueta="Categoría" valor={f.valor("categoria")} alCambiar={(v) => f.cambiar({ categoria: v })} opciones={facetas.datos?.categorias_catalogo ?? []} />
          <Seleccion etiqueta="Proveedor" valor={f.valor("proveedor")} alCambiar={(v) => f.cambiar({ proveedor: v })} opciones={facetas.datos?.proveedores ?? []} />
          <Seleccion etiqueta="Ordenar por" valor={f.valor("orden")} alCambiar={(v) => f.cambiar({ orden: v })} todas="ID"
            opciones={[{ valor: "nombre", texto: "Nombre" }, { valor: "precio", texto: "Precio base" }, { valor: "stock", texto: "Stock mínimo" }, { valor: "ventas", texto: "Ventas registradas" }, { valor: "importe", texto: "Importe" }]} />
          <Segmentado etiqueta="Vista" valor={vista} alCambiar={(v) => f.cambiar({ vista: v })} opciones={[{ valor: "tarjetas", texto: <span className="inline-flex items-center gap-1.5"><LayoutGrid size={15} aria-hidden="true" />Tarjetas</span> }, { valor: "tabla", texto: <span className="inline-flex items-center gap-1.5"><Rows3 size={15} aria-hidden="true" />Tabla</span> }]} />
          {f.hayFiltros && <button type="button" onClick={() => { f.limpiar(); setTexto(""); }} className="inline-flex min-h-11 items-center gap-1.5 rounded-full px-4 text-sm font-bold text-petroleo hover:bg-superficie-2"><FilterX size={16} aria-hidden="true" />Limpiar</button>}
        </div>
      </section>

      {cat.error && !cat.datos ? <EstadoError error={cat.error} alReintentar={cat.recargar} /> : !cat.datos ? <FilasEsqueleto filas={8} /> : cat.datos.items.length === 0 ? (
        <EstadoVacio titulo="Ningún producto coincide" accion={<button type="button" className="min-h-11 rounded-full bg-bosque px-5 text-sm font-bold text-blanco" onClick={() => { f.limpiar(); setTexto(""); }}>Quitar filtros</button>}>
          Revisa la búsqueda o elige otra categoría.</EstadoVacio>
      ) : (
        <section aria-busy={cat.cargando} className={`transition-opacity ${cat.cargando ? "opacity-60" : ""}`}>
          {vista === "tarjetas" ? (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {cat.datos.items.map((p, i) => (
                <li key={p.id_producto} className="panel entra flex flex-col gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-elevada" style={{ ["--i" as string]: Math.min(i, 10) } as React.CSSProperties}>
                  <div className="flex items-start gap-3">
                    <IconoCategoria categoria={p.categoria} />
                    <div className="min-w-0"><p className="num text-xs font-bold text-suave">{p.id_producto}</p>
                      <h2 className="font-display text-lg font-bold leading-snug text-bosque">{p.nombre_producto}</h2>
                      <Insignia tono="neutro" className="mt-1">{p.categoria}</Insignia></div>
                  </div>
                  <p className="num font-display text-3xl font-bold text-bosque">{fMXN(p.precio_base_mxn)}<span className="ml-1 text-xs font-bold text-suave">precio base</span></p>
                  <dl className="grid grid-cols-2 gap-3 border-t border-borde pt-3 text-sm">
                    <div><dt className="etiqueta">Stock mínimo</dt><dd className="num font-bold">{fEntero(p.stock_minimo)}</dd></div>
                    <div><dt className="etiqueta">Proveedor</dt><dd className="font-bold">{p.proveedor ?? "—"}</dd></div>
                    <div><dt className="etiqueta">Ventas válidas</dt><dd className="num font-bold">{fEntero(p.ventas)}</dd></div>
                    <div><dt className="etiqueta">Importe</dt><dd className="num font-bold">{fMXNCorto(p.importe)}</dd></div>
                  </dl>
                </li>
              ))}
            </ul>
          ) : (
            <div className="panel scroll-fino overflow-auto">
              <table className="tabla min-w-[860px]">
                <caption className="sr-only">Catálogo oficial de productos</caption>
                <thead><tr>
                  <ThOrden clave="id" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>ID</ThOrden>
                  <ThOrden clave="nombre" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>Producto</ThOrden>
                  <ThOrden clave="categoria" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar}>Categoría</ThOrden>
                  <ThOrden clave="precio" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>Precio base</ThOrden>
                  <ThOrden clave="stock" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>Stock mín.</ThOrden>
                  <th scope="col">Proveedor</th>
                  <ThOrden clave="ventas" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>Ventas</ThOrden>
                  <ThOrden clave="importe" orden={f.valor("orden")} direccion={f.valor("direccion") as "asc" | "desc"} alOrdenar={ordenar} der>Importe</ThOrden>
                </tr></thead>
                <tbody>
                  {cat.datos.items.map((p) => (
                    <tr key={p.id_producto}>
                      <td className="num font-bold">{p.id_producto}</td><td className="font-medium">{p.nombre_producto}</td>
                      <td><span className="inline-flex items-center gap-2"><IconoCategoria categoria={p.categoria} tam={24} />{p.categoria}</span></td>
                      <td className="num der">{fMXN(p.precio_base_mxn)}</td><td className="num der">{fEntero(p.stock_minimo)}</td>
                      <td>{p.proveedor ?? "—"}</td><td className="num der">{fEntero(p.ventas)}</td><td className="num der">{fMXNCorto(p.importe)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="panel mt-4 overflow-hidden"><Paginacion pagina={cat.datos.pagina} paginas={cat.datos.paginas} total={cat.datos.total} tam={tam} alCambiar={(p) => f.cambiar({ pagina: String(p) }, true)} /></div>
          {cat.datos.huerfanos > 0 && (
            <p className="panel-aviso mt-4 flex flex-wrap items-center gap-3 p-4 text-sm">
              <TriangleAlert size={18} className="text-ambar-texto" aria-hidden="true" />
              <span><b>{fEntero(cat.datos.huerfanos)}</b> ventas hacían referencia a productos que <b>no existen</b> en este catálogo y se apartaron como PRODUCTO_HUERFANO.</span>
              <Link to="/cuarentena?codigo=PRODUCTO_HUERFANO" className="font-bold text-petroleo underline">Ver esos registros</Link>
            </p>
          )}
        </section>
      )}
    </div>
  );
}
