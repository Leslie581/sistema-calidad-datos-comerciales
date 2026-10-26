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
