"""Investigación de la advertencia numérica conocida (RuntimeWarning: overflow en la prueba de estrés E30).

Causa: en `recalcular_montos` (Leslie) el factor de inconsistencia se resume con `(monto / calculado).round(4)`.
Con un total de 1e308 el cociente es ~1e306 y `round(4)` lo multiplica por 10^4 → desborda float64 a `inf`.
Efecto: SOLO el diagnóstico `factores_inconsistencia` registra la clave 'inf'. El importe corregido, la bandera y el
resto del pipeline no cambian. Estas pruebas fijan ese comportamiento; no se modificó el módulo estadístico.
"""
import warnings

import pytest

from src.calidad.limpieza import recalcular_montos
from tests.conftest import df_minimo


def test_total_gigante_desborda_solo_el_diagnostico_del_factor():
    df = df_minimo([{"cantidad": 1.0, "precio_unitario": 100.0, "monto_total": 1e308}])
    with pytest.warns(RuntimeWarning, match="overflow"):
        out, bitacora = recalcular_montos(df)
    assert out.loc[0, "monto_total"] == 100.0                       # el importe SÍ se corrige
    assert out.loc[0, "monto_total_origen"] == 1e308                # y el original se conserva
    assert out.loc[0, "correcciones"] == ["MONTO_RECALCULADO_INCONSISTENTE"]
    assert bitacora["recalculados_inconsistente"] == 1
    assert bitacora["factores_inconsistencia"] == {"inf": 1}        # lo único afectado


def test_con_los_datos_oficiales_no_hay_desbordes(etapa_limpieza):
    _, bitacora = etapa_limpieza
    assert bitacora["reconstruccion_montos"]["factores_inconsistencia"] == {"80.0": 12}


def test_un_factor_normal_no_emite_advertencias():
    df = df_minimo([{"cantidad": 1.0, "precio_unitario": 100.0, "monto_total": 8000.0}])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _, bitacora = recalcular_montos(df)
    assert bitacora["factores_inconsistencia"] == {"80.0": 1}
