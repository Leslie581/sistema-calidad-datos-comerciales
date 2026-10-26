import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { ErrorApi } from "../services/api";

interface Estado<T> {
  clave: string;
  datos?: T;
  error?: ErrorApi;
}

/**
 * Carga de datos con AbortController. Mientras llega una nueva respuesta conserva la anterior (`datos`) y marca
 * `cargando`, para que tablas y filtros no «parpadeen». `recargar()` repite la consulta.
 */
export function useApi<T>(llamar: (senal: AbortSignal) => Promise<T>, deps: readonly unknown[] = []) {
  const [version, setVersion] = useState(0);
  const [estado, setEstado] = useState<Estado<T>>({ clave: "" });
  const clave = `${version}|${JSON.stringify(deps)}`;
  const ejecutar = useEffectEvent(llamar);

  useEffect(() => {
    const control = new AbortController();
    ejecutar(control.signal)
      .then((datos) => setEstado({ clave, datos }))
      .catch((e: unknown) => {
        if ((e as Error).name === "AbortError") return;
        setEstado((prev) => ({ clave, datos: prev.datos, error: e instanceof ErrorApi ? e : new ErrorApi("ERROR_DESCONOCIDO", String(e)) }));
      });
    return () => control.abort();
  }, [clave]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  const cargando = estado.clave !== clave;
  return { datos: estado.error && estado.clave === clave ? undefined : estado.datos, error: estado.clave === clave ? estado.error : undefined, cargando, recargar };
}
