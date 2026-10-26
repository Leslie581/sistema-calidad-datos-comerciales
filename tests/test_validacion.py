"""Pruebas del modelo Pydantic y de la segregación a cuarentena (etapa de Nono): un caso por validador."""
from __future__ import annotations

import json
import logging
from unittest import mock

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from src.validacion import cuarentena as cua
from src.validacion.cuarentena import (ErrorConservacion, a_nativo, clasificar_registro, errores_fases_previas,
                                       formatear_errores, validar_lote)
from src.validacion.esquemas import TransaccionLimpia
from tests.ayudas_nono import HOY, fila_valida

AHORA = "2026-10-25T12:00:00"


def codigos(fila: dict) -> set[str]:
    try:
        TransaccionLimpia.model_validate(fila, context={"hoy": HOY})
    except ValidationError as e:
        return {d["codigo"] for d in formatear_errores(e)}
    return set()


def clasificar(fila):
    return clasificar_registro(fila, "L-test", AHORA, HOY)


# ----------------------------------------------------------------------------- registros conformes
@pytest.mark.parametrize("origen", ["FISICA", "ONLINE"])
def test_registro_valido_en_ambos_canales(origen):
    estado, reg = clasificar(fila_valida(origen))
    assert estado == "VALIDO" and reg["moneda"] == "MXN"
    assert isinstance(reg["cantidad"], int) and reg["alertas"] == "[]"


def test_valores_originales_y_tratados_conviven():
    """El capping no borra la evidencia: cantidad_origen y monto_total_origen siguen en la fila persistible."""
    f = fila_valida(cantidad_origen=500.0, cantidad=500.0, cantidad_cap=8.0, monto_total_origen=51299.0,
                    monto_total_mxn=51299.0, precio_unitario_mxn=102.598, monto_total_mxn_cap=820.78)
    f["precio_unitario_mxn"] = 102.598
    f["monto_total_mxn"] = round(500 * 102.598, 2)
    estado, reg = clasificar(f)
    assert estado == "VALIDO"
    assert (reg["cantidad_origen"], reg["cantidad"], reg["cantidad_cap"]) == (500.0, 500, 8)
    assert reg["monto_total_origen"] == 51299.0 and reg["monto_total_mxn_cap"] == 820.78


def test_etiquetas_controladas_se_aceptan():
    assert codigos(fila_valida("ONLINE", email_cliente="SIN_CORREO", direccion_envio="SIN_DIRECCION")) == set()
    assert codigos(fila_valida("FISICA", id_cliente="ANONIMO")) == set()


@pytest.mark.parametrize("estado", ["COMPLETADO", "PAGADO", "PENDIENTE", "CANCELADO", "DEVUELTO"])
def test_cancelados_y_devueltos_no_son_errores_R11(estado):
    assert codigos(fila_valida("ONLINE", estado_pedido=estado)) == set()


# ----------------------------------------------------------------------------- un caso por validador
@pytest.mark.parametrize("cambios, esperado", [
    ({"es_duplicado": True}, "DUPLICADO_EXACTO"),
    ({"es_id_conflicto": True}, "ID_REPETIDO_CONFLICTO"),
    ({"id_transaccion": "POS-1"}, "ID_FORMATO_INVALIDO"),
    ({"id_transaccion": "WEB-00001"}, "ID_ORIGEN_INCONSISTENTE"),                 # [PROPUESTA] canal FISICA con prefijo WEB-
    ({"id_transaccion": "'; DROP TABLE transacciones_limpias;--"}, "ID_FORMATO_INVALIDO"),
    ({"id_transaccion": None}, "TIPO_INVALIDO"),
    ({"id_transaccion": 12345}, "TIPO_INVALIDO"),                                  # estricto: un entero no es un ID de texto
    ({"fecha_venta": None}, "FECHA_INVALIDA"),
    ({"fecha_venta": "13-09-2026"}, "FECHA_INVALIDA"),
    ({"fecha_venta": "2026-02-31"}, "FECHA_INVALIDA"),
    ({"fecha_venta": "2026-10-26"}, "FECHA_INVALIDA"),                             # posterior a la fecha de ejecución (HOY)
    ({"en_catalogo": False}, "PRODUCTO_HUERFANO"),
    ({"nombre_producto": None}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"cantidad": 0.0}, "CANTIDAD_INVALIDA"),
    ({"cantidad": -1.0}, "CANTIDAD_INVALIDA"),
    ({"cantidad": 2.5}, "CANTIDAD_INVALIDA"),
    ({"cantidad": None}, "CANTIDAD_INVALIDA"),
    ({"cantidad": "2"}, "CANTIDAD_INVALIDA"),                                      # un texto no se convierte en silencio
    ({"cantidad": True}, "CANTIDAD_INVALIDA"),
    ({"cantidad": float("inf")}, "CANTIDAD_INVALIDA"),
    ({"cantidad_cap": 0.0}, "CANTIDAD_INVALIDA"),
    ({"moneda_original": "EUR"}, "MONEDA_NO_SOPORTADA"),
    ({"moneda_original": None}, "MONEDA_NO_SOPORTADA"),
    ({"tipo_cambio_aplicado": 19.5}, "TIPO_CAMBIO_INCONSISTENTE"),                 # [PROPUESTA] MXN con tipo de cambio 19.5
    ({"precio_unitario_mxn": None}, "PRECIO_FALTANTE"),
    ({"precio_unitario_mxn": 0.0}, "PRECIO_INVALIDO"),
    ({"precio_unitario_mxn": -5.0}, "PRECIO_INVALIDO"),
    ({"monto_total_mxn": None}, "MONTO_INVALIDO"),
    ({"monto_total_mxn": 0.0}, "MONTO_INVALIDO"),
    ({"monto_total_mxn": -200.0}, "MONTO_INVALIDO"),
    ({"monto_total_mxn": 250.0}, "MONTO_INCONSISTENTE"),
    ({"monto_total_mxn_cap": -1.0}, "MONTO_INVALIDO"),
    ({"monto_minmax": 1.5}, "ESCALA_FUERA_DE_RANGO"),
    ({"monto_minmax": -0.1}, "ESCALA_FUERA_DE_RANGO"),
    ({"monto_minmax": None}, "TIPO_INVALIDO"),
    ({"monto_minmax": float("nan")}, "TIPO_INVALIDO"),
    ({"segmento_importe": "Premium"}, "TIPO_INVALIDO"),
    ({"segmento_importe": None}, "TIPO_INVALIDO"),
    ({"origen": "TIENDA"}, "TIPO_INVALIDO"),
    ({"es_outlier_monto": "no"}, "TIPO_INVALIDO"),
    ({"id_cliente": None}, "CAMPO_OBLIGATORIO_FALTANTE"),                          # FISICA exige id_cliente (ANONIMO si faltaba)
    ({"id_cliente": "  "}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"estado_pedido": "COMPLETADO"}, "ESTADO_INVALIDO"),                          # [PROPUESTA] el canal FISICA no tiene estado
    ({"metodo_pago": ""}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"punto_venta": None}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"id_fila_origen": 0}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"registro_original": ""}, "CAMPO_OBLIGATORIO_FALTANTE"),
])
def test_validadores_fisica(cambios, esperado):
    assert esperado in codigos(fila_valida("FISICA", **cambios))


@pytest.mark.parametrize("cambios, esperado", [
    ({"email_cliente": "sin_arroba_dominio.org"}, "EMAIL_MALFORMADO"),
    ({"email_cliente": "usuario@@gmail..com"}, "EMAIL_MALFORMADO"),
    ({"email_cliente": "correo_invalido.com"}, "EMAIL_MALFORMADO"),
    ({"email_cliente": "a@b"}, "EMAIL_MALFORMADO"),
    ({"email_cliente": "con espacio@correo.com"}, "EMAIL_MALFORMADO"),
    ({"email_cliente": None}, "CAMPO_OBLIGATORIO_FALTANTE"),                       # faltante ≠ malformado (R10.3)
    ({"direccion_envio": None}, "CAMPO_OBLIGATORIO_FALTANTE"),
    ({"estado_pedido": "ENVIADO"}, "ESTADO_INVALIDO"),
    ({"estado_pedido": None}, "ESTADO_INVALIDO"),
    ({"moneda_original": "USD", "tipo_cambio_aplicado": 1.0}, "TIPO_CAMBIO_INCONSISTENTE"),
    ({"id_transaccion": "POS-2026-0001"}, "ID_ORIGEN_INCONSISTENTE"),
    ({"id_transaccion": "WEB-1"}, "ID_FORMATO_INVALIDO"),
])
def test_validadores_online(cambios, esperado):
    assert esperado in codigos(fila_valida("ONLINE", **cambios))


def test_usd_con_paridad_oficial_es_valido():
    f = fila_valida("ONLINE", moneda_original="USD", tipo_cambio_aplicado=19.5, precio_unitario_original=10.0,
                    precio_unitario_mxn=195.0, monto_total_mxn=390.0, monto_total_mxn_cap=390.0)
    assert codigos(f) == set()


def test_monto_con_diferencia_dentro_de_la_tolerancia():
    assert codigos(fila_valida(monto_total_mxn=200.01)) == set()
    assert "MONTO_INCONSISTENTE" in codigos(fila_valida(monto_total_mxn=200.02))


def test_la_fecha_limite_es_la_del_contexto_no_la_del_reloj():
    f = fila_valida(fecha_venta="2026-10-25")
    assert TransaccionLimpia.model_validate(f, context={"hoy": HOY})
    with pytest.raises(ValidationError):
        TransaccionLimpia.model_validate(f, context={"hoy": pd.Timestamp("2026-10-24").date()})


def test_mensajes_empiezan_con_codigo_y_los_nativos_son_tipo_invalido():
    estado, reg = clasificar(fila_valida(segmento_importe="Premium", en_catalogo=False))
    assert estado == "RECHAZADO"
    partes = reg["motivo_rechazo_cuarentena"].split(" | ")
    assert all(p.split(":")[0].isupper() for p in partes)
    assert any(p.startswith("TIPO_INVALIDO: segmento_importe") for p in partes)


def test_campo_requerido_ausente_es_tipo_invalido():
    f = fila_valida()
    del f["monto_minmax"]
    estado, reg = clasificar(f)
    assert estado == "RECHAZADO" and "TIPO_INVALIDO" in reg["codigos_error"]


# ----------------------------------------------------------------------------- cuarentena
def test_varias_causas_se_conservan_todas_y_el_registro_cuenta_una_vez():
    f = fila_valida(cantidad=-1.0, cantidad_cap=-1.0, monto_total_mxn=-100.0, en_catalogo=False, es_duplicado=True,
                    fecha_venta=None)
    estado, reg = clasificar(f)
    assert estado == "RECHAZADO"
    assert set(reg["codigos_error"].split(";")) >= {"CANTIDAD_INVALIDA", "MONTO_INVALIDO", "PRODUCTO_HUERFANO",
                                                      "DUPLICADO_EXACTO", "FECHA_INVALIDA"}
    assert reg["num_motivos"] == len(reg["codigos_error"].split(";"))
    assert reg["motivo_rechazo_cuarentena"].count(" | ") + 1 == reg["num_motivos"]      # un código = un motivo (sin repetir)
    df = pd.DataFrame([{**f, "id_fila_origen": 1}])
    assert len(validar_lote(df, "L", HOY, AHORA).cuarentena) == 1


def test_registro_de_cuarentena_conserva_lo_minimo_exigido():
    estado, reg = clasificar(fila_valida(en_catalogo=False, registro_original='{"id_ticket": "POS-2026-0001"}'))
    for campo in ("id_registro", "origen", "id_fila_origen", "registro_original", "motivo_rechazo_cuarentena",
                  "codigos_error", "detalle_error", "fecha_cuarentena", "lote_id", "etapa_deteccion"):
        assert reg[campo] not in (None, ""), campo
    detalle = json.loads(reg["detalle_error"])
    assert detalle and {"campo", "codigo", "mensaje", "etapa"} <= set(detalle[0])
    assert reg["registro_original"] == '{"id_ticket": "POS-2026-0001"}'


def test_etapa_de_deteccion_distingue_fase_previa_y_pydantic():
    _, solo_previa = clasificar(fila_valida(es_duplicado=False, alertas=["MONEDA_NO_SOPORTADA"], moneda_original="MXN"))
    assert "FASE_PREVIA" in solo_previa["etapa_deteccion"]
    _, solo_pydantic = clasificar(fila_valida(monto_total_mxn=250.0))
    assert solo_pydantic["etapa_deteccion"] == "PYDANTIC"
    _, ambas = clasificar(fila_valida(es_duplicado=True, monto_total_mxn=250.0))
    assert ambas["etapa_deteccion"] == "FASE_PREVIA;PYDANTIC"


def test_bandera_previa_rechaza_aunque_pydantic_no_lance_nada():
    """Una fase previa que marca (alerta de fecha) pero cuyo valor final pasaría el modelo igual va a cuarentena (R1.3)."""
    estado, reg = clasificar(fila_valida(alertas=["FECHA_NO_INTERPRETABLE"]))
    assert estado == "RECHAZADO" and reg["codigos_error"] == "FECHA_INVALIDA" and reg["etapa_deteccion"] == "FASE_PREVIA"


def test_el_mismo_codigo_de_fase_previa_y_pydantic_se_cuenta_una_vez():
    _, reg = clasificar(fila_valida(en_catalogo=False))
    assert reg["codigos_error"] == "PRODUCTO_HUERFANO" and reg["num_motivos"] == 1


def test_errores_fases_previas_directo():
    previos = errores_fases_previas({"es_duplicado": True, "es_id_conflicto": True, "en_catalogo": False,
                                     "id_producto": "PROD-999", "alertas": ["CANTIDAD_NO_NUMERICA", "PRECIO_INVALIDO"]})
    assert {p["codigo"] for p in previos} == {"DUPLICADO_EXACTO", "ID_REPETIDO_CONFLICTO", "PRODUCTO_HUERFANO",
                                              "CANTIDAD_INVALIDA", "PRECIO_INVALIDO"}
    assert errores_fases_previas(fila_valida()) == []


def test_validar_lote_separa_y_conserva():
    filas = [fila_valida("FISICA", id_fila_origen=1), fila_valida("FISICA", id_fila_origen=2, id_transaccion="POS-2026-0002",
                                                                  en_catalogo=False),
             fila_valida("ONLINE", id_fila_origen=1), fila_valida("ONLINE", id_fila_origen=2, id_transaccion="WEB-00002",
                                                                  email_cliente="mal")]
    r = validar_lote(pd.DataFrame(filas), "L1", HOY, AHORA)
    assert (len(r.validos), len(r.cuarentena), r.total) == (2, 2, 4)
    assert r.conteo_por_codigo == {"EMAIL_MALFORMADO": 1, "PRODUCTO_HUERFANO": 1}


def test_un_registro_malo_no_detiene_al_resto():
    filas = [fila_valida(id_fila_origen=i + 1, id_transaccion=f"POS-2026-{i + 1:04d}",
                         **({"cantidad": "dos"} if i == 3 else {})) for i in range(10)]
    r = validar_lote(pd.DataFrame(filas), "L", HOY, AHORA)
    assert len(r.validos) == 9 and len(r.cuarentena) == 1 and r.cuarentena[0]["id_registro"] == "POS-2026-0004"


def test_lote_vacio_no_falla():
    r = validar_lote(pd.DataFrame(columns=list(fila_valida())), "L", HOY, AHORA)
    assert r.total == 0


def test_error_inesperado_por_registro_se_aisla_y_queda_registrado(caplog):
    filas = [fila_valida(id_fila_origen=i + 1, id_transaccion=f"POS-2026-{i + 1:04d}") for i in range(3)]
    original = TransaccionLimpia.model_validate.__func__

    def falla_en_el_2(cls, obj, *a, **kw):
        if obj.get("id_transaccion") == "POS-2026-0002":
            raise RuntimeError("bug simulado")
        return original(cls, obj, *a, **kw)

    with caplog.at_level(logging.ERROR, logger="src.validacion.cuarentena"):
        with mock.patch.object(TransaccionLimpia, "model_validate", classmethod(falla_en_el_2)):
            r = validar_lote(pd.DataFrame(filas), "L", HOY, AHORA)
    assert (len(r.validos), len(r.cuarentena), r.errores_inesperados) == (2, 1, 1)
    q = r.cuarentena[0]
    assert q["codigos_error"] == "ERROR_INESPERADO" and "RuntimeError: bug simulado" in q["motivo_rechazo_cuarentena"]
    assert q["etapa_deteccion"] == "ERROR_INESPERADO"
    assert any("bug simulado" in m and "POS-2026-0002" in m for m in caplog.messages)       # trazabilidad: no se oculta


def test_conservacion_violada_interrumpe(monkeypatch):
    filas = pd.DataFrame([fila_valida(id_fila_origen=i + 1, id_transaccion=f"POS-2026-{i + 1:04d}") for i in range(3)])
    real = cua.clasificar_registro
    llamadas = {"n": 0}

    def pierde_un_registro(*a, **kw):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            return "VALIDO", {"origen": "FISICA", "id_fila_origen": 1}        # duplica la fila 1 en vez de la 2
        return real(*a, **kw)

    monkeypatch.setattr(cua, "clasificar_registro", pierde_un_registro)
    with pytest.raises(ErrorConservacion, match="Conservación violada"):
        validar_lote(filas, "L", HOY, AHORA)


# ----------------------------------------------------------------------------- a_nativo
@pytest.mark.parametrize("entrada, esperado", [(np.nan, None), (None, None), (pd.NA, None), (np.float64(2.5), 2.5),
                                               (np.int64(3), 3), (np.bool_(True), True), ("x", "x"), ("", ""),
                                               (["a", np.nan], ["a", None])])
def test_a_nativo(entrada, esperado):
    r = a_nativo(entrada)
    assert r == esperado and type(r) is type(esperado)


def test_a_nativo_convierte_numpy_para_pydantic_estricto():
    f = {k: (np.float64(v) if isinstance(v, float) else v) for k, v in fila_valida().items()}
    f["id_fila_origen"] = np.int64(5)
    f["es_duplicado"] = np.bool_(False)
    assert clasificar(f)[0] == "VALIDO"


# ----------------------------------------------------------------------------- contrato con las etapas anteriores
def test_columnas_faltantes_para_el_modelo_son_falla_global_no_nulos_silenciosos():
    from src.contratos import ErrorContrato
    df = pd.DataFrame([fila_valida()]).drop(columns=["monto_cantidad_cap_mxn"])
    with pytest.raises(ErrorContrato, match="monto_cantidad_cap_mxn"):
        validar_lote(df, "L", HOY, AHORA)


def test_precio_original_se_toma_de_precio_unitario_del_pipeline():
    f = fila_valida()
    f["precio_unitario"] = f.pop("precio_unitario_original")
    estado, reg = clasificar(f)
    assert estado == "VALIDO" and reg["precio_unitario_original"] == 100.0
    r = validar_lote(pd.DataFrame([f]), "L", HOY, AHORA)
    assert len(r.validos) == 1 and r.validos[0]["precio_unitario_original"] == 100.0
