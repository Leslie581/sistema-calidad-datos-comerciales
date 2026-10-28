"""Contratos de respuesta de la API (Pydantic). Los campos clave están tipados; el detalle profundo conserva su forma."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Canal = Literal["FISICA", "ONLINE"]
Segmento = Literal["Bajo", "Medio", "Alto"]


class Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class ErrorRespuesta(BaseModel):
    codigo: str
    mensaje: str


class Salud(Base):
    api: Literal["ok"] = "ok"
    base_datos: Literal["disponible", "no_encontrada", "sin_esquema", "no_disponible"]
    ruta_bd_relativa: str
    version: str


class Pagina(Base):
    total: int
    pagina: int
    tam: int
    paginas: int


class Ejecucion(Base):
    lote_id: str
    estado: Literal["COMPLETADO", "FALLIDO"]
    inicio: str
    fin: str
    filas_entrada: Optional[int] = None
    filas_limpias: Optional[int] = None
    filas_cuarentena: Optional[int] = None
    tasa_aceptacion: Optional[float] = None
    duracion_s: Optional[float] = None
    etapa_fallida: Optional[str] = None
    error: Optional[str] = None
    tiene_bitacora: bool = False
    advertencias: list[str] = Field(default_factory=list)


class Totales(Base):
    entrada: int
    limpias: int
    cuarentena: int
    tasa_aceptacion: Optional[float] = None
    cuadra: bool


class Dashboard(Base):
    hay_datos: bool
    ultima_ejecucion: Optional[Ejecucion] = None
    totales: Totales
    salud: Optional[dict[str, Any]] = None
    canales: list[dict[str, Any]]
    segmentos: list[dict[str, Any]]
    motivos: dict[str, Any]
    por_dia: list[dict[str, Any]]
    categorias: list[dict[str, Any]]
    indicadores: dict[str, Any]
    anomalias: list[dict[str, Any]]
    actividad_reciente: list[Ejecucion]
    advertencias: list[str]
    nota_historial: str


class TransaccionResumen(Base):
    id_transaccion: str
    origen: Canal
    id_fila_origen: int
    fecha_venta: str
    id_producto: str
    nombre_producto: str
    categoria: str
    cantidad: int
    precio_unitario_mxn: float
    monto_total_mxn: float
    monto_total_mxn_cap: float
    segmento_importe: Segmento
    estado_pedido: Optional[str] = None
    moneda_original: Literal["MXN", "USD"]
    precio_unitario_original: Optional[float] = None      # en la moneda original (USD o MXN), tal como se persistió
    tipo_cambio_aplicado: Optional[float] = None          # 19.5 para USD; 1.0 para MXN


class PaginaTransacciones(Pagina):
    items: list[TransaccionResumen]
    resumen_filtro: dict[str, Any]


class EtapaTraza(Base):
    clave: str
    titulo: str
    estado: str
    descripcion: str
    campos: list[dict[str, Any]]
    codigos: list[str]


class DetalleTransaccion(Base):
    moneda: dict[str, Any]
    transaccion: dict[str, Any]
    registro_original: dict[str, Any]
    trazabilidad: list[EtapaTraza]
    glosario: dict[str, Optional[str]]
    cuarentena_relacionada: list[dict[str, Any]]


class CuarentenaResumen(Base):
    id_error: int
    id_registro: Optional[str] = None
    origen: Optional[str] = None
    id_fila_origen: Optional[int] = None
    etapas: list[str]
    codigos: list[str]
    num_motivos: int
    motivo: str
    fecha_cuarentena: str
    lote_id: str


class PaginaCuarentena(Pagina):
    items: list[CuarentenaResumen]


class DetalleCuarentena(Base):
    registro: CuarentenaResumen
    detalle: list[dict[str, Any]]
    registro_original: Any
    trazabilidad: list[EtapaTraza]
    hay_limpia_con_mismo_id: bool
    glosario: dict[str, Optional[str]]


class Producto(Base):
    id_producto: str
    nombre_producto: str
    categoria: str
    precio_base_mxn: float
    stock_minimo: Optional[int] = None
    proveedor: Optional[str] = None
    ventas: int
    unidades: int
    importe: float


class PaginaCatalogo(Pagina):
    items: list[Producto]
    por_categoria: list[dict[str, Any]]
    huerfanos: int


class ListaEjecuciones(Base):
    items: list[Ejecucion]
    total: int
    nota: str


class Fase(Base):
    numero: int
    clave: str
    nombre: str
    responsable: str
    estado: Literal["COMPLETADA", "FALLIDA", "PARCIAL", "NO_EJECUTADA", "SIN_DATOS"]
    duracion_s: Optional[float] = None
    metricas: dict[str, Any]


class DetalleEjecucion(Base):
    ejecucion: Ejecucion
    fases: list[Fase]
    entorno: dict[str, Any]
    huellas_entrada: dict[str, Any]
    duracion_etapas_s: dict[str, float]
    log: Optional[list[str]] = None
    bitacora_disponible: bool


class EstadoEjecucion(Base):
    estado: Literal["INACTIVO", "EN_EJECUCION"]
    iniciado_en: Optional[str] = None
    lote_en_curso: Optional[str] = None
    ultimo_resultado: Optional[dict[str, Any]] = None


class EstadoPipeline(Base):
    ejecutor: EstadoEjecucion
    ultima: Optional[Ejecucion] = None
    fases: list[Fase]
    nota_progreso: str
    ruta_bd_existe: bool
    fuentes: dict[str, Any]


class PeriodoComercial(Base):
    inicio: str
    fin: str
    dias: int
    dias_cubiertos: int
    cobertura: float
    parcial: bool
    etiqueta: str
    dias_calendario_mes: Optional[int] = None


class IndicadoresVenta(Base):
    transacciones: int
    importe: float
    unidades: int
    ticket_promedio: Optional[float] = None
    promedio_diario: Optional[float] = None
    dias_con_ventas: int
    primera_venta: Optional[str] = None
    ultima_venta: Optional[str] = None


class Mensaje(Base):
    id: str
    tipo: Literal["tendencia", "canal", "aviso", "info", "nota"]
    texto: str
    evidencia: dict[str, Any]


class Diagnostico(Base):
    estado: Literal["crecimiento", "estable", "disminucion", "sin_comparacion", "no_concluyente", "sin_datos"]
    titular: str
    mensajes: list[Mensaje]


class ResumenComercial(Base):
    filtros: dict[str, Any]
    modo: Literal["mes", "personalizado"]
    periodo: PeriodoComercial
    anterior: Optional[PeriodoComercial] = None
    homogeneo: bool
    avisos: list[str]
    cobertura_datos: dict[str, str]
    actual: IndicadoresVenta
    anterior_kpis: Optional[IndicadoresVenta] = None
    variaciones: dict[str, Optional[float]]
    canales: list[dict[str, Any]]
    atipicas: dict[str, Any]
    no_efectivas: dict[str, Any]
    diagnostico: Diagnostico
    criterios: dict[str, float]
    definicion_importe: dict[str, str]


class TendenciaComercial(Base):
    periodo: PeriodoComercial
    anterior: Optional[PeriodoComercial] = None
    homogeneo: bool
    dias: list[dict[str, Any]]
    meses: list[dict[str, Any]]
    avisos: list[str]


class CanalesComerciales(Base):
    periodo: PeriodoComercial
    anterior: Optional[PeriodoComercial] = None
    homogeneo: bool
    canales: list[dict[str, Any]]
    avisos: list[str]
    nota: str


class ProductosComerciales(Base):
    periodo: PeriodoComercial
    orden: str
    importe_total: float
    productos_distintos: int
    productos: list[dict[str, Any]]
    categorias: list[dict[str, Any]]
    avisos: list[str]
    nota: str


class OpcionesComerciales(Base):
    hay_datos: bool
    cobertura: dict[str, Optional[str]]
    meses: list[dict[str, Any]]
    mes_por_defecto: Optional[str] = None
    canales: list[str]
    comparaciones: list[str]
    estados: list[str]


class SolicitudEjecucion(BaseModel):
    confirmar: bool = Field(description="Debe ser true: la ejecución reemplaza el contenido de la base (snapshot).")


class RespuestaEjecucion(Base):
    aceptada: Literal[True] = True
    estado: Literal["EN_EJECUCION"] = "EN_EJECUCION"
    iniciado_en: str
    mensaje: str


class ArchivoReporte(Base):
    ruta: str
    nombre: str
    tipo: str
    bytes: int
    modificado: float
    url: str


class ListaReportes(Base):
    grupos: list[dict[str, Any]]


class Facetas(Base):
    canales: list[str]
    categorias: list[str]
    segmentos: list[str]
    estados: list[str]
    proveedores: list[str]
    categorias_catalogo: list[str]
    rango_fechas: list[Optional[str]]
    codigos_rechazo: list[str]


class Calidad(Base):
    lote_id: Optional[str] = None
    nota_mcar: str
    graficas: list[dict[str, Any]]
    distincion: dict[str, str]
    fuentes: dict[str, Any]
