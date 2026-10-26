import type { ReactNode } from "react";
import { AlertTriangle, DatabaseZap, PlugZap, RotateCw, SearchX } from "lucide-react";
import { ErrorApi } from "../../services/api";
import { Isotipo, MarcaDeAgua } from "../brand/Marca";
import { Boton, Esqueleto } from "./Basicos";

/** Estado vacío con identidad: marca de agua + composición de módulos. Nunca un simple «sin datos». */
export function EstadoVacio({ titulo, children, accion, icono }: { titulo: string; children?: ReactNode; accion?: ReactNode; icono?: ReactNode }) {
  return (
    <div role="status" className="panel relative overflow-hidden px-6 py-14 text-center">
      <MarcaDeAgua className="-right-16 -top-10 scale-75" opacidad={0.05} />
      <div className="relative mx-auto flex max-w-md flex-col items-center gap-3">
        <span className="grid size-14 place-items-center rounded-2xl bg-superficie-2 text-petroleo">{icono ?? <SearchX aria-hidden="true" />}</span>
        <h2 className="titular text-2xl text-bosque">{titulo}</h2>
        {children && <p className="text-suave">{children}</p>}
        {accion}
      </div>
    </div>
  );
}

/** Errores de la API o de conexión, con mensaje comprensible y acción para reintentar. */
export function EstadoError({ error, alReintentar }: { error: ErrorApi | Error; alReintentar?: () => void }) {
  const e = error instanceof ErrorApi ? error : null;
  const sinConexion = e?.sinConexion;
  const sinBase = e?.sinBase;
  const Icono = sinConexion ? PlugZap : sinBase ? DatabaseZap : AlertTriangle;
  const titulo = sinConexion ? "KOVA no puede comunicarse con el servidor" : sinBase ? "Todavía no hay datos procesados" : "No se pudo completar la consulta";
  return (
    <div role="alert" className="panel-aviso relative overflow-hidden px-6 py-10">
      <div className="relative mx-auto flex max-w-xl flex-col items-center gap-3 text-center">
        <span className="grid size-14 place-items-center rounded-2xl bg-[#fbf0dc] text-ambar-texto"><Icono aria-hidden="true" /></span>
        <h2 className="titular text-2xl text-bosque">{titulo}</h2>
        <p className="text-suave">{error.message}</p>
        {sinConexion && (
          <p className="rounded-xl bg-blanco px-4 py-2 text-left font-mono text-xs text-grafito">
            python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
          </p>
        )}
        <div className="mt-1 flex flex-wrap justify-center gap-2">
          {sinBase && <a className="inline-flex min-h-11 items-center rounded-full bg-bosque px-5 text-sm font-bold text-blanco" href="/etl">Ir al Centro ETL</a>}
          {alReintentar && <Boton variante="secundario" onClick={alReintentar}><RotateCw size={16} aria-hidden="true" />Reintentar</Boton>}
        </div>
      </div>
    </div>
  );
}

export function PantallaCarga({ etiqueta = "Cargando datos de KOVA" }: { etiqueta?: string }) {
  return (
    <div role="status" aria-live="polite" aria-label={etiqueta} className="space-y-4">
      <span className="sr-only">{etiqueta}…</span>
      <Esqueleto className="h-44" />
      <div className="grid gap-4 md:grid-cols-3">
        <Esqueleto className="h-32" /><Esqueleto className="h-32" /><Esqueleto className="h-32" />
      </div>
      <Esqueleto className="h-72" />
    </div>
  );
}

export function FilasEsqueleto({ filas = 8 }: { filas?: number }) {
  return (
    <div role="status" aria-label="Cargando filas" className="space-y-2 p-4">
      {Array.from({ length: filas }, (_, i) => <Esqueleto key={i} className="h-9" style={{ opacity: 1 - i * 0.08 }} />)}
    </div>
  );
}

export function Cargador({ tam = 20 }: { tam?: number }) {
  return <span className="pulso inline-block" aria-hidden="true"><Isotipo tam={tam} /></span>;
}
