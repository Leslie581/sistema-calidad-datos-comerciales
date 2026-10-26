-- Esquema SQLite del pipeline (responsable: Nono). Consultable con DB Browser for SQLite.
-- Defensa en profundidad: aunque Pydantic ya validó, la base se protege sola con PK, FK y CHECK.
-- Idempotencia: ver src/persistencia/carga.py (snapshot por ejecución dentro de UNA transacción).

-- Historial de ejecuciones: una fila por intento (COMPLETADO o FALLIDO). Sobrevive a las recargas.
CREATE TABLE IF NOT EXISTS ejecuciones (
    lote_id             TEXT PRIMARY KEY,
    inicio              TEXT NOT NULL,
    fin                 TEXT NOT NULL,
    estado              TEXT NOT NULL CHECK (estado IN ('COMPLETADO', 'FALLIDO')),
    filas_entrada       INTEGER,
    filas_limpias       INTEGER,
    filas_cuarentena    INTEGER,
    huellas_entrada     TEXT,          -- JSON {archivo: sha256}
    entorno             TEXT,          -- JSON {python, pandas, pydantic, sqlite}
    etapa_fallida       TEXT,
    error               TEXT,
    CHECK (estado = 'FALLIDO' OR filas_entrada = filas_limpias + filas_cuarentena)   -- R1.4
);

-- Catálogo maestro: referencia de integridad para transacciones_limpias.id_producto (R9.3).
CREATE TABLE IF NOT EXISTS catalogo_productos (
    id_producto      TEXT PRIMARY KEY,
    nombre_producto  TEXT NOT NULL,
    categoria        TEXT NOT NULL,
    precio_base_mxn  REAL NOT NULL CHECK (precio_base_mxn > 0),
    stock_minimo     INTEGER,
    proveedor        TEXT
);

CREATE TABLE IF NOT EXISTS transacciones_limpias (
    id_transaccion          TEXT PRIMARY KEY
        CHECK (id_transaccion GLOB 'POS-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]'
            OR id_transaccion GLOB 'WEB-[0-9][0-9][0-9][0-9][0-9]'),
    origen                  TEXT NOT NULL CHECK (origen IN ('FISICA', 'ONLINE')),
    id_fila_origen          INTEGER NOT NULL CHECK (id_fila_origen >= 1),
    -- fecha: original y normalizada
    fecha_cruda             TEXT,
    fecha_venta             TEXT NOT NULL
        CHECK (fecha_venta GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date(fecha_venta) = fecha_venta),
    punto_venta             TEXT NOT NULL,
    -- producto (referencia al catálogo)
    id_producto             TEXT NOT NULL REFERENCES catalogo_productos (id_producto),
    nombre_producto         TEXT NOT NULL,
    categoria               TEXT NOT NULL,
    -- cantidad: original → tratada → con capping
    cantidad_origen         REAL,
    cantidad                INTEGER NOT NULL CHECK (cantidad > 0),
    cantidad_cap            INTEGER NOT NULL CHECK (cantidad_cap > 0),
    -- importes: original → convertido a MXN → con capping
    moneda_original         TEXT NOT NULL CHECK (moneda_original IN ('MXN', 'USD')),
    moneda                  TEXT NOT NULL CHECK (moneda = 'MXN'),
    tipo_cambio_aplicado    REAL NOT NULL CHECK (tipo_cambio_aplicado > 0),
    precio_unitario_original REAL,
    precio_unitario_mxn     REAL NOT NULL CHECK (precio_unitario_mxn > 0),
    monto_total_origen      REAL,
    monto_total_mxn         REAL NOT NULL CHECK (monto_total_mxn > 0),
    monto_cantidad_cap_mxn  REAL,
    monto_total_mxn_cap     REAL NOT NULL CHECK (monto_total_mxn_cap > 0),
    monto_minmax            REAL NOT NULL CHECK (monto_minmax BETWEEN 0 AND 1),
    segmento_importe        TEXT NOT NULL CHECK (segmento_importe IN ('Bajo', 'Medio', 'Alto')),
    -- cliente y venta (opcionales según el canal, R3.9)
    id_cliente              TEXT,
    email_cliente           TEXT,
    direccion_envio         TEXT,
    metodo_pago             TEXT NOT NULL,
    estado_pedido           TEXT CHECK (estado_pedido IS NULL
                                        OR estado_pedido IN ('COMPLETADO', 'PAGADO', 'PENDIENTE', 'CANCELADO', 'DEVUELTO')),
    es_outlier_cantidad     INTEGER NOT NULL CHECK (es_outlier_cantidad IN (0, 1)),
    es_outlier_monto        INTEGER NOT NULL CHECK (es_outlier_monto IN (0, 1)),
    -- auditoría y trazabilidad
    alertas                 TEXT NOT NULL DEFAULT '[]',
    correcciones            TEXT NOT NULL DEFAULT '[]',
    registro_original       TEXT NOT NULL,
    lote_id                 TEXT NOT NULL REFERENCES ejecuciones (lote_id),
    fecha_carga             TEXT NOT NULL,
    UNIQUE (origen, id_fila_origen),
    CHECK ((origen = 'ONLINE' AND estado_pedido IS NOT NULL) OR (origen = 'FISICA' AND estado_pedido IS NULL))
);

CREATE TABLE IF NOT EXISTS cuarentena_errores (
    id_error                   INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id                    TEXT NOT NULL REFERENCES ejecuciones (lote_id),
    id_registro                TEXT,                 -- puede ser NULL si el ID mismo faltaba
    origen                     TEXT,
    id_fila_origen             INTEGER,
    etapa_deteccion            TEXT NOT NULL,        -- FASE_PREVIA | PYDANTIC | ERROR_INESPERADO (combinables con ';')
    codigos_error              TEXT NOT NULL CHECK (length(trim(codigos_error)) > 0),
    num_motivos                INTEGER NOT NULL CHECK (num_motivos >= 1),
    motivo_rechazo_cuarentena  TEXT NOT NULL CHECK (length(trim(motivo_rechazo_cuarentena)) > 0),
    detalle_error              TEXT NOT NULL,        -- JSON [{campo, codigo, mensaje, etapa, entrada}]
    registro_original          TEXT NOT NULL,
    fecha_cuarentena           TEXT NOT NULL,
    UNIQUE (lote_id, origen, id_fila_origen)         -- una transacción se cuenta una sola vez por ejecución
);

CREATE INDEX IF NOT EXISTS ix_limpias_fecha ON transacciones_limpias (fecha_venta);
CREATE INDEX IF NOT EXISTS ix_limpias_producto ON transacciones_limpias (id_producto);
CREATE INDEX IF NOT EXISTS ix_limpias_origen_segmento ON transacciones_limpias (origen, segmento_importe);
CREATE INDEX IF NOT EXISTS ix_cuarentena_lote ON cuarentena_errores (lote_id);
CREATE INDEX IF NOT EXISTS ix_cuarentena_codigos ON cuarentena_errores (codigos_error);
