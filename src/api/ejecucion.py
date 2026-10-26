"""
Ejecución del pipeline desde la API, protegida contra ejecuciones simultáneas.

Un `threading.Lock` no bloqueante garantiza UNA ejecución a la vez dentro del proceso; además, el pipeline abre la
base con `BEGIN IMMEDIATE`, que impide dos escrituras simultáneas de procesos distintos. El pipeline actual NO emite
progreso granular: el estado es solo «EN_EJECUCION» o «INACTIVO» y, al terminar, el resultado real. No hay porcentajes.
Aplicación local y académica: no está pensada para exponerse a internet.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable

from ..pipeline import ejecutar_pipeline
from .config import Ajustes


class EjecutorPipeline:
    def __init__(self, ajustes: Ajustes, ejecutar: Callable[..., dict] = ejecutar_pipeline):
        self.aj, self._ejecutar = ajustes, ejecutar
        self._candado = threading.Lock()
        self._estado = {"estado": "INACTIVO", "iniciado_en": None, "lote_en_curso": None, "ultimo_resultado": None}
        self._hilo: threading.Thread | None = None

    def estado(self) -> dict:
        return dict(self._estado)

    def esperar(self, timeout: float | None = None) -> None:
        """Solo para pruebas: espera a que termine la ejecución en curso."""
        if self._hilo:
            self._hilo.join(timeout)

    def iniciar(self) -> str | None:
        """Arranca la ejecución en segundo plano. Devuelve la hora de inicio, o None si ya hay una en curso."""
        if not self._candado.acquire(blocking=False):
            return None
        inicio = datetime.now().isoformat(timespec="seconds")
        self._estado.update(estado="EN_EJECUCION", iniciado_en=inicio, lote_en_curso=None)
        self._hilo = threading.Thread(target=self._correr, name="kova-pipeline", daemon=True)
        self._hilo.start()
        return inicio

    def _correr(self) -> None:
        try:
            kw = dict(ruta_bd=self.aj.ruta_bd, dir_salida=self.aj.dir_salida)
            if self.aj.rutas_fuentes is not None:
                kw["rutas"] = self.aj.rutas_fuentes
            r = self._ejecutar(**kw)
            resultado = {k: r.get(k) for k in ("lote_id", "estado", "duracion_s", "etapa_fallida", "tipo_error", "error",
                                               "filas_entrada", "advertencias")}
            resultado["validacion"] = {k: (r.get("validacion") or {}).get(k) for k in ("validos", "cuarentena")} \
                if r.get("validacion") else None
        except Exception as e:  # noqa: BLE001 — el pipeline ya clasifica sus fallos; esto cubre un fallo del propio ejecutor
            resultado = {"lote_id": None, "estado": "FALLIDO", "tipo_error": type(e).__name__, "error": str(e),
                         "etapa_fallida": None, "duracion_s": None, "filas_entrada": None, "advertencias": [], "validacion": None}
        resultado["terminado_en"] = datetime.now().isoformat(timespec="seconds")
        self._estado.update(estado="INACTIVO", lote_en_curso=resultado.get("lote_id"), ultimo_resultado=resultado)
        self._candado.release()
