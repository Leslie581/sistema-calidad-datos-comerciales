"""Configuración de la API local de KOVA. Solo rutas decididas por el servidor: el cliente nunca aporta rutas."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..config import RAIZ, RUTA_BD, RUTA_SALIDAS, RUTA_SALIDAS_NONO
from .comercial import Criterios

# Orígenes del servidor de desarrollo de Vite (CORS restringido al entorno local, nunca "*").
ORIGENES_LOCALES = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173",
                    "http://localhost:8000", "http://127.0.0.1:8000")
CARPETAS_REPORTES = ("etapa_leslie", "etapa_yerik", "etapa_nono")        # únicas carpetas consultables
EXTENSIONES_REPORTE = {".csv": "text/csv", ".json": "application/json", ".txt": "text/plain", ".png": "image/png",
                       ".md": "text/markdown"}


@dataclass
class Ajustes:
    ruta_bd: Path = RUTA_BD
    dir_salida: Path = RUTA_SALIDAS_NONO          # evidencias y bitácoras del pipeline
    raiz_salidas: Path = RUTA_SALIDAS             # contiene etapa_leslie / etapa_yerik / etapa_nono
    rutas_fuentes: dict | None = None             # None = datasets oficiales (con verificación SHA-256)
    dist_frontend: Path = RAIZ / "frontend" / "dist"
    origenes: tuple[str, ...] = field(default_factory=lambda: ORIGENES_LOCALES)
    criterios_comerciales: Criterios = field(default_factory=Criterios.desde_entorno)   # umbrales propios de KOVA (configurables)

    @classmethod
    def desde_entorno(cls) -> "Ajustes":
        """KOVA_BD y KOVA_SALIDA permiten apuntar a otra copia (por ejemplo, para pruebas); por omisión, las del proyecto."""
        aj = cls()
        if os.environ.get("KOVA_BD"):
            aj.ruta_bd = Path(os.environ["KOVA_BD"])
        if os.environ.get("KOVA_SALIDA"):
            aj.dir_salida = Path(os.environ["KOVA_SALIDA"])
        return aj
