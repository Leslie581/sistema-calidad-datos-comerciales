"""Pruebas de los componentes mínimos de Yerik que alimentan a Leslie."""
import json

import pytest

from src.contratos import COLUMNAS_HOMOLOGADAS
from src.extraccion import ErrorExtraccion, leer_json_ventas, verificar_integridad
from src.integracion.homologacion import a_numero, homologar_columnas
from tests.conftest import fila


def test_originales_sin_modificar():
    assert all(verificar_integridad().values())


def test_dimensiones_extraccion(fuentes):
    assert fuentes["catalogo"].shape == (50, 6)
    assert fuentes["fisica"].shape == (620, 9 + 2)      # + id_fila_origen, registro_original
    assert fuentes["online"].shape == (600, 11 + 2)


def test_extraccion_csv_como_texto(fuentes):
    assert fuentes["fisica"]["cantidad"].map(type).eq(str).all()


def test_json_conserva_tipos_originales(fuentes):
    tipos = fuentes["online"]["order_timestamp"].map(lambda v: type(v).__name__).value_counts().to_dict()
    assert tipos == {"str": 392, "int": 208}


def test_homologacion_filas_y_contrato(df_homologado):
    assert len(df_homologado) == 1220
    assert df_homologado.groupby("origen").size().to_dict() == {"FISICA": 620, "ONLINE": 600}
    assert list(df_homologado.columns) == COLUMNAS_HOMOLOGADAS


def test_no_aplica_queda_none(df_homologado):
    online = df_homologado[df_homologado["origen"] == "ONLINE"]
    fisica = df_homologado[df_homologado["origen"] == "FISICA"]
    assert online["id_cliente"].isna().all()
    assert fisica["email_cliente"].isna().all() and fisica["estado_pedido"].isna().all()


def test_faltantes_reales_por_canal(df_homologado):
    fis = df_homologado[df_homologado["origen"] == "FISICA"]
    onl = df_homologado[df_homologado["origen"] == "ONLINE"]
    assert fis["id_cliente"].isna().sum() == 127
    assert fis["monto_total"].isna().sum() == 32
    assert onl["email_cliente"].isna().sum() == 20          # 15 null + 5 "" (R3.8)
    assert onl["direccion_envio"].isna().sum() == 77


def test_homologacion_categoricas(df_homologado):
    assert df_homologado["metodo_pago"].value_counts()["EFECTIVO"] == 193
    assert df_homologado["estado_pedido"].value_counts()["COMPLETADO"] == 192


def test_epoch_se_guarda_como_texto(df_homologado):
    assert fila(df_homologado, "WEB-00005")["fecha_cruda"] == "1789105020"


@pytest.mark.parametrize("entrada, esperado", [("3", 3.0), (2, 2.0), (" 4.5 ", 4.5), ("", None), (None, None),
                                               (float("nan"), None)])
def test_a_numero_validos(entrada, esperado):
    assert a_numero(entrada) == esperado


@pytest.mark.parametrize("entrada", ["dos", True, float("inf"), "1e999"])
def test_a_numero_invalidos(entrada):
    with pytest.raises(ValueError):
        a_numero(entrada)


def test_cantidad_no_numerica_genera_alerta(fuentes):
    corrupto = {k: v.copy() for k, v in fuentes.items()}
    corrupto["fisica"].loc[0, "cantidad"] = "dos"
    df = homologar_columnas(corrupto)
    assert df.loc[0, "alertas"] == ["CANTIDAD_NO_NUMERICA"]
    assert df["cantidad"].isna().sum() == 1


def test_json_invalido_es_error_controlado(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text('[{"order_id": "WEB-', encoding="utf-8")
    with pytest.raises(ErrorExtraccion, match="no es un JSON válido"):
        leer_json_ventas(ruta, ["order_id"])


def test_json_campo_ausente_queda_none(tmp_path):
    ruta = tmp_path / "parcial.json"
    ruta.write_text(json.dumps([{"order_id": "WEB-00001"}]), encoding="utf-8")
    df = leer_json_ventas(ruta, ["order_id", "units"])
    assert df.loc[0, "units"] is None
