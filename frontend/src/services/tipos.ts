// Tipos de las respuestas de la API (espejo de src/api/esquemas.py). No contienen lógica de negocio.
export type Canal = "FISICA" | "ONLINE";
export type Segmento = "Bajo" | "Medio" | "Alto";

export interface Ejecucion {
  lote_id: string;
  estado: "COMPLETADO" | "FALLIDO";
  inicio: string;
  fin: string;
  filas_entrada: number | null;
  filas_limpias: number | null;
  filas_cuarentena: number | null;
  tasa_aceptacion: number | null;
  duracion_s: number | null;
  etapa_fallida: string | null;
  error: string | null;
  tiene_bitacora: boolean;
  tiene_log?: boolean;
  advertencias: string[];
}

export interface Salud {
  api: "ok";
  base_datos: "disponible" | "no_encontrada" | "sin_esquema" | "no_disponible";
  ruta_bd_relativa: string;
  version: string;
}

export interface SaludOrigen {
  nombre: string;
  es_indicador_compuesto: boolean;
  valor: number | null;
  formula: string;
  detalle: string;
  conformes: number;
  reparados: number;
  rechazados: number;
  entrada: number;
}

export interface CanalResumen {
  origen: Canal;
  entrada: number;
  limpias: number;
  cuarentena: number;
  importe_mxn: number;
  tasa_aceptacion: number | null;
}

export interface MotivosRechazo {
  por_codigo: { codigo: string; registros: number; descripcion: string | null }[];
  combinaciones: { codigos: string[]; registros: number }[];
  por_etapa: { etapa: string; registros: number }[];
  por_canal: { origen: Canal; registros: number }[];
  total_registros: number;
  con_varios_motivos: number;
}

export interface Dashboard {
  hay_datos: boolean;
  ultima_ejecucion: Ejecucion | null;
  totales: { entrada: number; limpias: number; cuarentena: number; tasa_aceptacion: number | null; cuadra: boolean };
  salud: SaludOrigen | null;
  canales: CanalResumen[];
  segmentos: { origen: Canal; segmento: Segmento; n: number; importe_mxn: number }[];
  motivos: MotivosRechazo;
  por_dia: { fecha: string; origen: Canal; n: number; importe_mxn: number }[];
  categorias: { categoria: string; n: number; importe_mxn: number }[];
  indicadores: Record<string, number | string | null>;
  anomalias: { id_error: number; id_registro: string | null; origen: Canal; codigos: string[]; num_motivos: number }[];
  actividad_reciente: Ejecucion[];
  advertencias: string[];
  nota_historial: string;
}

export interface Pagina<T> {
  items: T[];
  total: number;
  pagina: number;
  tam: number;
  paginas: number;
}

export interface TransaccionResumen {
  id_transaccion: string;
  origen: Canal;
  id_fila_origen: number;
  fecha_venta: string;
  id_producto: string;
  nombre_producto: string;
  categoria: string;
  cantidad: number;
  precio_unitario_mxn: number;
  monto_total_mxn: number;
  monto_total_mxn_cap: number;
  segmento_importe: Segmento;
  estado_pedido: string | null;
  moneda_original: "MXN" | "USD";
  precio_unitario_original: number | null;
  tipo_cambio_aplicado: number | null;
}

export type PaginaTransacciones = Pagina<TransaccionResumen> & { resumen_filtro: { n: number; importe_mxn: number | null } };

export interface CampoTraza {
  campo: string;
  antes: unknown;
  despues: unknown;
  cambio: boolean;
  nota: string | null;
}
export interface EtapaTraza {
  clave: string;
  titulo: string;
  estado: "ok" | "sin_cambios" | "corregido" | "tratado" | "aceptado" | "rechazado";
  descripcion: string;
  campos: CampoTraza[];
  codigos: string[];
}

export interface CuarentenaResumen {
  id_error: number;
  id_registro: string | null;
  origen: Canal | null;
  id_fila_origen: number | null;
  etapas: string[];
  codigos: string[];
  num_motivos: number;
  motivo: string;
  fecha_cuarentena: string;
  lote_id: string;
}

export interface DetalleTransaccion {
  moneda: MonedaTransaccion;
  transaccion: Record<string, unknown> & TransaccionResumen & { correcciones: string[]; lote_id: string };
  registro_original: Record<string, unknown>;
  trazabilidad: EtapaTraza[];
  glosario: Record<string, string | null>;
  cuarentena_relacionada: CuarentenaResumen[];
}

export interface DetalleCuarentena {
  registro: CuarentenaResumen;
  detalle: { campo: string | null; codigo: string; mensaje: string; etapa: string; entrada: string | null; descripcion: string | null }[];
  registro_original: Record<string, unknown> | string;
  trazabilidad: EtapaTraza[];
  hay_limpia_con_mismo_id: boolean;
  glosario: Record<string, string | null>;
}

export interface Producto {
  id_producto: string;
  nombre_producto: string;
  categoria: string;
  precio_base_mxn: number;
  stock_minimo: number | null;
  proveedor: string | null;
  ventas: number;
  unidades: number;
  importe: number;
}
export type PaginaCatalogo = Pagina<Producto> & {
  por_categoria: { categoria: string; productos: number; precio_medio: number }[];
  huerfanos: number;
};

export interface Facetas {
  canales: Canal[];
  categorias: string[];
  segmentos: Segmento[];
  estados: string[];
  proveedores: string[];
  categorias_catalogo: string[];
  rango_fechas: (string | null)[];
  codigos_rechazo: string[];
}

export type EstadoFase = "COMPLETADA" | "FALLIDA" | "PARCIAL" | "NO_EJECUTADA" | "SIN_DATOS";
export interface Fase {
  numero: number;
  clave: string;
  nombre: string;
  responsable: string;
  nota?: string;
  etapas_internas: string[];
  estado: EstadoFase;
  duracion_s: number | null;
  metricas: Record<string, unknown>;
}

export interface EstadoPipeline {
  ejecutor: {
    estado: "INACTIVO" | "EN_EJECUCION";
    iniciado_en: string | null;
    lote_en_curso: string | null;
    ultimo_resultado: Record<string, unknown> | null;
  };
  ultima: Ejecucion | null;
  fases: Fase[];
  nota_progreso: string;
  ruta_bd_existe: boolean;
  fuentes: { oficiales: boolean; verificacion_sha256: boolean };
}

export interface DetalleEjecucion {
  ejecucion: Ejecucion;
  fases: Fase[];
  entorno: Record<string, string>;
  huellas_entrada: Record<string, string>;
  duracion_etapas_s: Record<string, number>;
  log: string[] | null;
  bitacora_disponible: boolean;
}

export interface ArchivoReporte {
  ruta: string;
  nombre: string;
  tipo: string;
  bytes: number;
  modificado: number;
  url: string;
}
export interface ListaReportes {
  grupos: { carpeta: string; archivos: ArchivoReporte[] }[];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;
export interface Calidad {
  lote_id: string | null;
  nota_mcar: string;
  graficas: { id: string; titulo: string; descripcion: string; url: string; fuente: string }[];
  distincion: Record<string, string>;
  fuentes: { bitacora: string | null; reportes_leslie_disponibles: boolean; nota: string };
  limpieza: Json;
  iqr: Json;
  transformacion: Json;
  perfil_antes: Json;
  faltantes: Json;
  antes_despues: Record<string, string>[] | null;
  conteo_correcciones: Record<string, number> | null;
}

// ---------------------------------------------------------------- Pulso comercial
export type EstadoDiagnostico = "crecimiento" | "estable" | "disminucion" | "sin_comparacion" | "no_concluyente" | "sin_datos";
export type ModoComparacion = "equivalente" | "mes_anterior_completo" | "ninguna";
export type EstadosVenta = "todas" | "efectivas";

export interface PeriodoComercial {
  inicio: string;
  fin: string;
  dias: number;
  dias_cubiertos: number;
  cobertura: number;
  parcial: boolean;
  etiqueta: string;
  dias_calendario_mes: number | null;
}
export interface IndicadoresVenta {
  transacciones: number;
  importe: number;
  unidades: number;
  ticket_promedio: number | null;
  promedio_diario: number | null;
  dias_con_ventas: number;
  primera_venta: string | null;
  ultima_venta: string | null;
}
export interface MensajeComercial {
  id: string;
  tipo: "tendencia" | "canal" | "aviso" | "info" | "nota";
  texto: string;
  evidencia: Record<string, unknown>;
}
export interface CanalComercial extends IndicadoresVenta {
  canal: Canal;
  participacion_pct: number | null;
  importe_anterior: number | null;
  transacciones_anterior: number | null;
  variacion_importe_pct: number | null;
}
export interface ResumenComercial {
  filtros: { mes: string | null; desde: string | null; hasta: string | null; canal: Canal | null; comparacion: ModoComparacion; estados: EstadosVenta };
  modo: "mes" | "personalizado";
  periodo: PeriodoComercial;
  anterior: PeriodoComercial | null;
  homogeneo: boolean;
  avisos: string[];
  cobertura_datos: { inicio: string; fin: string };
  actual: IndicadoresVenta;
  anterior_kpis: IndicadoresVenta | null;
  variaciones: { importe_pct: number | null; transacciones_pct: number | null; ticket_promedio_pct: number | null; promedio_diario_pct: number | null };
  canales: CanalComercial[];
  atipicas: { transacciones: number; importe: number; participacion_pct: number | null; sin_atipicas: { actual: number; anterior: number | null; variacion_pct: number | null } | null };
  no_efectivas: { transacciones: number; importe: number };
  diagnostico: { estado: EstadoDiagnostico; titular: string; mensajes: MensajeComercial[] };
  criterios: Record<string, number>;
  definicion_importe: { campo: string; texto: string; no_es: string };
}
export interface DiaTendencia {
  indice: number;
  fecha: string;
  importe: number | null;
  transacciones: number | null;
  ticket_promedio: number | null;
  fisica: number | null;
  online: number | null;
  acumulado: number | null;
  fecha_anterior: string | null;
  importe_anterior: number | null;
  transacciones_anterior: number | null;
  ticket_anterior: number | null;
  acumulado_anterior: number | null;
}
export interface MesComercial {
  mes: string;
  etiqueta: string;
  inicio_datos: string;
  fin_datos: string;
  dias_mes: number;
  dias_cubiertos: number;
  parcial: boolean;
  transacciones: number;
  importe: number;
  promedio_diario: number | null;
}
export interface TendenciaComercial {
  periodo: PeriodoComercial;
  anterior: PeriodoComercial | null;
  homogeneo: boolean;
  dias: DiaTendencia[];
  meses: MesComercial[];
  avisos: string[];
}
export interface ProductoComercial {
  id_producto: string;
  nombre_producto: string;
  categoria: string;
  transacciones: number;
  unidades: number;
  importe: number;
  participacion_pct: number | null;
}
export interface ProductosComerciales {
  periodo: PeriodoComercial;
  orden: string;
  importe_total: number;
  productos_distintos: number;
  productos: ProductoComercial[];
  categorias: { categoria: string; transacciones: number; unidades: number; importe: number; participacion_pct: number | null }[];
  avisos: string[];
  nota: string;
}
export interface OpcionesComerciales {
  hay_datos: boolean;
  cobertura: { inicio: string | null; fin: string | null };
  meses: MesComercial[];
  mes_por_defecto: string | null;
  canales: Canal[];
  comparaciones: ModoComparacion[];
  estados: EstadosVenta[];
}
export interface MonedaTransaccion {
  moneda_original: "MXN" | "USD";
  es_usd: boolean;
  tipo_cambio: number | null;
  precio_original: number | null;
  importe_original: number | null;
  precio_mxn: number;
  importe_mxn: number;
  importe_mxn_capping: number;
  capping_aplicado: boolean;
  importe_original_coherente: number | null;
  importe_original_corregido: boolean;
  formula: string | null;
}
