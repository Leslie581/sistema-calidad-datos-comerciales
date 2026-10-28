"""El frontend se prueba con respuestas reales de la API guardadas como fixtures: si la API cambia de forma, esto falla."""
from __future__ import annotations

import json

import pytest

from scripts.generar_fixtures_frontend import DESTINO, respuestas_reales

LIBRES = {"glosario", "conteo_correcciones", "entorno", "huellas_entrada", "duracion_etapas_s", "distincion", "metricas", "faltantes",
          "perfil_antes", "limpieza", "iqr", "transformacion", "antes_despues", "registro_original", "transaccion", "ultimo_resultado",
          "filas_fuentes", "indicadores", "integridad_originales", "filtros", "criterios", "evidencia",
          "sin_atipicas"}


def forma(x, nivel=0):
    if isinstance(x, dict):
        return {k: ("<libre>" if k in LIBRES or nivel >= 4 else forma(v, nivel + 1)) for k, v in sorted(x.items())}
    if isinstance(x, list):
        return [forma(x[0], nivel + 1)] if x else []
    return type(x).__name__ if x is not None else "None"


@pytest.fixture(scope="module")
def reales(tmp_path_factory):
    return respuestas_reales(tmp_path_factory.mktemp("fixtures"))


def test_hay_un_fixture_por_respuesta_y_con_la_misma_forma_que_la_api(reales):
    archivos = {p.stem for p in DESTINO.glob("*.json")}
    assert archivos == set(reales), "ejecuta python scripts/generar_fixtures_frontend.py"
    for nombre, cuerpo in reales.items():
        guardado = json.loads((DESTINO / f"{nombre}.json").read_text(encoding="utf-8"))
        assert forma(guardado) == forma(cuerpo), f"el fixture {nombre}.json está desactualizado: regenéralo"
