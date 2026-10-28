import { Suspense, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  ChevronRight, History, LayoutDashboard, Menu, Package, ReceiptText, ScanSearch, Search, ShieldAlert, Sprout, TrendingUp, Workflow, X,
} from "lucide-react";
import { Isotipo, Logotipo } from "../components/brand/Marca";
import { Insignia } from "../components/ui/Basicos";
import { PantallaCarga } from "../components/ui/Estados";
import { useSistema } from "../hooks/sistema";
import { fFechaHora } from "../lib/format";

const GRUPOS = [
  { titulo: "Resumen", items: [
    { a: "/", texto: "Inicio", icono: Sprout, fin: true },
    { a: "/panel", texto: "Panel ejecutivo", icono: LayoutDashboard },
    { a: "/pulso-comercial", texto: "Pulso comercial", icono: TrendingUp },
  ] },
  { titulo: "Proceso", items: [
    { a: "/etl", texto: "Centro ETL", icono: Workflow },
    { a: "/calidad", texto: "Calidad de datos", icono: ScanSearch },
    { a: "/historial", texto: "Historial y reportes", icono: History },
  ] },
  { titulo: "Datos", items: [
    { a: "/transacciones", texto: "Transacciones", icono: ReceiptText },
    { a: "/cuarentena", texto: "Cuarentena", icono: ShieldAlert },
    { a: "/catalogo", texto: "Catálogo", icono: Package },
  ] },
];
const TITULOS: Record<string, string> = Object.fromEntries(GRUPOS.flatMap((g) => g.items.map((i) => [i.a, i.texto])));

function Navegacion({ alNavegar }: { alNavegar?: () => void }) {
  return (
    <nav aria-label="Principal" className="flex flex-col gap-5">
      {GRUPOS.map((g) => (
        <div key={g.titulo}>
          <p className="mb-1.5 px-3 text-[0.68rem] font-bold uppercase tracking-[0.14em] text-menta/60">{g.titulo}</p>
          <ul className="flex flex-col gap-0.5">
            {g.items.map(({ a, texto, icono: Icono, fin }) => (
              <li key={a}>
                <NavLink to={a} end={fin} onClick={alNavegar}
                  className={({ isActive }) =>
                    `group relative flex min-h-11 items-center gap-3 rounded-2xl px-3 text-[0.95rem] font-medium transition-colors ${
                      isActive ? "bg-menta/14 text-blanco" : "text-menta/80 hover:bg-menta/8 hover:text-blanco"}`}>
                  {({ isActive }) => (
                    <>
                      <span aria-hidden="true" className={`absolute -left-3 h-5 w-1.5 rounded-r-full bg-ambar transition-all ${isActive ? "opacity-100" : "scale-y-0 opacity-0"}`} />
                      <Icono size={19} aria-hidden="true" className={isActive ? "text-ambar" : ""} />
                      <span>{texto}</span>
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function EstadoSistema() {
  const { estado, error } = useSistema();
  const ult = estado?.ultima;
  const ejecutando = estado?.ejecutor.estado === "EN_EJECUCION";
  let tono = "bg-menta", texto = "Cargando estado…";
  if (error?.sinConexion) { tono = "bg-coral"; texto = "Sin conexión con la API"; }
  else if (ejecutando) { tono = "bg-ambar pulso"; texto = "Pipeline en ejecución"; }
  else if (ult) { tono = ult.estado === "COMPLETADO" ? "bg-menta" : "bg-coral"; texto = ult.estado === "COMPLETADO" ? "Última carga completada" : "Última ejecución fallida"; }
  else if (estado && !estado.ruta_bd_existe) { tono = "bg-ambar"; texto = "Sin base de datos"; }
  return (
    <div className="rounded-2xl bg-bosque-2/80 p-3.5 ring-1 ring-menta/15" role="status">
      <p className="flex items-center gap-2 text-sm font-bold text-blanco"><span className={`size-2.5 rounded-full ${tono}`} aria-hidden="true" />{texto}</p>
      {ult && <p className="num mt-1 text-xs text-menta/70">{fFechaHora(ult.fin)}</p>}
    </div>
  );
}

function Migas() {
  const { pathname } = useLocation();
  const base = "/" + (pathname.split("/")[1] ?? "");
  const titulo = TITULOS[pathname] ?? TITULOS[base];
  const detalle = pathname.split("/")[2];
  return (
    <ol className="flex min-w-0 items-center gap-1.5 text-sm text-suave" aria-label="Ruta de navegación">
      <li><Link to="/" className="rounded px-1 font-bold text-bosque hover:underline">KOVA</Link></li>
      {titulo && pathname !== "/" && (
        <>
          <li aria-hidden="true"><ChevronRight size={14} /></li>
          <li className="truncate" aria-current={detalle ? undefined : "page"}>{detalle ? <Link to={base} className="hover:underline">{titulo}</Link> : titulo}</li>
        </>
      )}
      {detalle && (
        <>
          <li aria-hidden="true"><ChevronRight size={14} /></li>
          <li className="truncate font-bold text-bosque" aria-current="page">{decodeURIComponent(detalle)}</li>
        </>
      )}
    </ol>
  );
}

export function AppLayout() {
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const { estado } = useSistema();

  const buscar = (e: FormEvent) => {
    e.preventDefault();
    const q = busqueda.trim();
    if (q) navegar(`/transacciones?q=${encodeURIComponent(q)}`);
  };

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[288px_1fr]">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-full focus:bg-ambar focus:px-4 focus:py-2 focus:font-bold focus:text-bosque">
        Saltar al contenido
      </a>
      {/* Riel lateral (escritorio): flota con margen y esquinas orgánicas */}
      <aside className="hidden p-4 lg:block">
        <div className="panel-bosque sticky top-4 flex h-[calc(100dvh-2rem)] flex-col justify-between overflow-hidden px-5 py-6">
          <div className="pointer-events-none absolute -bottom-24 -right-20 opacity-[0.07]" aria-hidden="true"><Isotipo tam={300} titulo="" /></div>
          <div className="relative space-y-8">
            <Link to="/" aria-label="KOVA, ir al inicio" className="block rounded-xl pl-1"><Logotipo oscuro /></Link>
            <Navegacion />
          </div>
          <div className="relative space-y-3">
            <EstadoSistema />
            <p className="px-1 text-xs leading-snug text-menta/60">Inteligencia comercial, datos confiables.</p>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        {/* Barra superior contextual */}
        <header className="sticky top-0 z-30 border-b border-borde/70 bg-crema/85 px-4 py-3 backdrop-blur-md sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-[1500px] items-center gap-3">
            <button type="button" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú"
              className="grid size-11 shrink-0 place-items-center rounded-full border border-borde-fuerte bg-blanco text-bosque lg:hidden"><Menu size={20} aria-hidden="true" /></button>
            <Link to="/" className="lg:hidden" aria-label="KOVA"><Isotipo tam={34} fondo="bosque" /></Link>
            <div className="hidden min-w-0 flex-1 lg:block"><Migas /></div>
            <form onSubmit={buscar} role="search" className="relative ml-auto w-full max-w-sm lg:ml-0">
              <label htmlFor="busqueda-global" className="sr-only">Buscar una transacción por ID</label>
              <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-suave" />
              <input id="busqueda-global" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar ID, p. ej. WEB-00508"
                className="h-11 w-full rounded-full border border-borde-fuerte bg-blanco pl-10 pr-4 text-sm placeholder:text-suave/80 focus:border-petroleo" />
            </form>
            <div className="hidden xl:block">
              {estado?.ejecutor.estado === "EN_EJECUCION" ? <Insignia tono="aviso"><span className="pulso">●</span> Ejecutando pipeline</Insignia>
                : estado?.ultima ? <Insignia tono={estado.ultima.estado === "COMPLETADO" ? "ok" : "alerta"}>{estado.ultima.estado === "COMPLETADO" ? "Datos al día" : "Última ejecución fallida"}</Insignia> : null}
            </div>
          </div>
        </header>

        <main id="contenido" key={pathname.split("/")[1]} tabIndex={-1} className="entra-suave mx-auto max-w-[1500px] px-4 pb-16 pt-6 outline-none sm:px-6 lg:px-8">
          <Suspense fallback={<PantallaCarga />}><Outlet /></Suspense>
        </main>
      </div>

      {/* Navegación móvil */}
      {menuAbierto && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="entra-suave absolute inset-0 bg-bosque/55" onClick={() => setMenuAbierto(false)} aria-hidden="true" />
          <div role="dialog" aria-modal="true" aria-label="Menú de navegación" className="drawer-entra panel-bosque relative flex h-full w-[min(86vw,320px)] flex-col justify-between rounded-l-none px-5 py-6" style={{ animationName: "none" }}>
            <div className="space-y-7">
              <div className="flex items-center justify-between">
                <Logotipo oscuro />
                <button type="button" onClick={() => setMenuAbierto(false)} aria-label="Cerrar menú" className="grid size-11 place-items-center rounded-full text-blanco ring-1 ring-menta/30"><X size={18} aria-hidden="true" /></button>
              </div>
              <Navegacion alNavegar={() => setMenuAbierto(false)} />
            </div>
            <EstadoSistema />
          </div>
        </div>
      )}
    </div>
  );
}
