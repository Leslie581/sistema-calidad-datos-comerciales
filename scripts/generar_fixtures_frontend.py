"""
Genera los fixtures de las pruebas del frontend a partir de respuestas REALES de la API (base generada por el pipeline).

    python scripts/generar_fixtures_frontend.py

Escribe frontend/src/test/fixtures/*.json. Así las pruebas de React usan datos con la forma exacta que entrega FastAPI;
`tests/test_contrato_fixtures.py` falla si la API cambia de forma y los fixtures quedan desactualizados.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi.testclient import TestClient  # noqa: E402

from src.api.config import Ajustes  # noqa: E402
from src.api.main import crear_app  # noqa: E402
from src.config import RUTA_SALIDAS  # noqa: E402
from src.pipeline import ejecutar_pipeline  # noqa: E402

DESTINO = RAIZ / "frontend" / "src" / "test" / "fixtures"


def respuestas_reales(carpeta: Path) -> dict:
    """Ejecuta el pipeline oficial en `carpeta` y devuelve {nombre: JSON de la API}."""
    aj = Ajustes(ruta_bd=carpeta / "kova.db", dir_salida=carpeta / "salida", raiz_salidas=RUTA_SALIDAS, dist_frontend=carpeta / "sin_dist")
    r = ejecutar_pipeline(ruta_bd=aj.ruta_bd, dir_salida=aj.dir_salida, generar_reportes=False)
    assert r["estado"] == "COMPLETADO", r.get("error")
    c = TestClient(crear_app(aj))
    cuarentena = c.get("/api/cuarentena", params={"q": "POS-2026-0493"}).json()["items"][0]["id_error"]
    out = {
        "salud": c.get("/api/salud").json(), "dashboard": c.get("/api/dashboard").json(), "facetas": c.get("/api/facetas").json(),
        "transacciones": c.get("/api/transacciones", params={"tam": 20}).json(),
        "transaccion_detalle": c.get("/api/transacciones/WEB-00508").json(),
        "cuarentena": c.get("/api/cuarentena", params={"tam": 20}).json(),
        "cuarentena_detalle": c.get(f"/api/cuarentena/{cuarentena}").json(),
        "catalogo": c.get("/api/catalogo", params={"tam": 24}).json(), "calidad": c.get("/api/calidad").json(),
        "ejecuciones": c.get("/api/ejecuciones").json(), "ejecucion_detalle": c.get(f"/api/ejecuciones/{r['lote_id']}").json(),
        "estado_pipeline": c.get("/api/pipeline/estado").json(), "reportes": c.get("/api/reportes").json(),
    }
    out["ejecucion_detalle"]["log"] = (out["ejecucion_detalle"]["log"] or [])[:6]
    return out


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        datos = respuestas_reales(Path(tmp))
    for nombre, cuerpo in datos.items():
        (DESTINO / f"{nombre}.json").write_text(json.dumps(cuerpo, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(datos)} fixtures escritos en {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
