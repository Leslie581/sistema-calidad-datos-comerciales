"""
Constantes y rutas compartidas por todo el pipeline.

Archivo COMPARTIDO: solo se modifica por acuerdo de los tres integrantes
(commit con prefijo "contrato:"). Las constantes marcadas [PROF] vienen de
GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf; las [EQUIPO], de REGLAS_DE_NEGOCIO.md.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# ----------------------------------------------------------------------------- rutas
RAIZ = Path(__file__).resolve().parent.parent
RUTA_CRUDOS = RAIZ / "datos" / "crudos"
RUTA_SALIDAS = RAIZ / "salidas"
RUTA_DIAGNOSTICO = RAIZ / "diagnostico" / "resultados_diagnostico.json"
RUTA_SALIDAS_NONO = RUTA_SALIDAS / "etapa_nono"
RUTA_BD = RUTA_SALIDAS_NONO / "calidad_comercial.db"   # SQLite entregable (ignorada por Git: se regenera con el pipeline)

RUTAS_FUENTES = {
    "catalogo": RUTA_CRUDOS / "catalogo_productos.csv",
    "fisica": RUTA_CRUDOS / "ventas_tienda_fisica.csv",
    "online": RUTA_CRUDOS / "ventas_online.json",
}

# Huellas SHA-256 registradas por el diagnóstico inicial (Avance 01).
# Si un archivo original cambia, el pipeline lo detecta.
HUELLAS_SHA256 = {
    "catalogo_productos.csv": "677fa7071d7cbe0ae3862c753a068ba9b80fe399b38fc7e23a45dd2e256868d1",
    "ventas_tienda_fisica.csv": "2e41ead654b4d044cca664842bca1ae85df2c1a84f5c0aad8b55706bbebf4df4",
    "ventas_online.json": "a2f150d331aba7bee98df30df501be1966d831488942b5f2c5eb1134c5dbdd7b",
}

# ----------------------------------------------------------------------------- reglas
PARIDAD_USD_MXN = Decimal("19.50")   # [PROF] Fase 4
FACTOR_IQR = 1.5                     # [PROF] Fase 3
TOLERANCIA_MONTO = 0.01              # [EQUIPO] R6.3: diferencia máxima aceptada (MXN o USD)
MONEDAS_SOPORTADAS = ("MXN", "USD")  # [EQUIPO] R7.5
ORIGEN_FISICA = "FISICA"
ORIGEN_ONLINE = "ONLINE"
PUNTO_VENTA_ONLINE = "TIENDA_ONLINE"

# [PROF] etiqueta 'ANONIMO' · [EQUIPO] R3.8 las demás. Solo se imputan en el canal donde la columna existe (R3.9).
ETIQUETAS_CONTROLADAS = {
    (ORIGEN_FISICA, "id_cliente"): "ANONIMO",
    (ORIGEN_ONLINE, "email_cliente"): "SIN_CORREO",
    (ORIGEN_ONLINE, "direccion_envio"): "SIN_DIRECCION",
}

# [EQUIPO] R11: estados comerciales válidos del canal online tras strip().upper(). CANCELADO y DEVUELTO NO son errores.
ESTADOS_PEDIDO_VALIDOS = ("COMPLETADO", "PAGADO", "PENDIENTE", "CANCELADO", "DEVUELTO")

SEMILLA = 2026  # para cualquier muestreo reproducible (no se usa en la etapa de Leslie)


def redondear(valor: float) -> float:
    """[EQUIPO] R6.4: redondeo financiero a 2 decimales con ROUND_HALF_UP (evita errores de float)."""
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
