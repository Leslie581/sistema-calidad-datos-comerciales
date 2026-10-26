# GUÍA GENERAL DEL EQUIPO

**Proyecto:** Sistema de Integración y Calidad de Datos Comerciales *(nombre provisional; el nombre definitivo está pendiente)*
**Materia:** Ingeniería de Datos (ATD-2602) · Unidad 2: Limpieza y Preprocesamiento de Datos
**Docente:** Prof. Armando Román Gallardo Heredia · TecNM Campus Colima · Ago-Dic 2026
**Equipo:** Leslie (Ingeniera 1) · Yerik (Ingeniero 2) · Nono (Ingeniero 3)
**Ponderación:** 60 % del Portafolio Digital de la Unidad 2 · Duración: 1 semana (5 días de laboratorio)

> **Documentos relacionados:** `REGLAS_DE_NEGOCIO.md` (qué se acepta, corrige o rechaza), `DIAGRAMA_PIPELINE.md` (flujo), `AVANCE_01_PROFESOR.md` (primera entrega) y una guía por integrante.
> **Convención:** 🟥 = obligatorio por el profesor · 🟦 = propuesta del equipo · ⬜ = mejora opcional (no se evalúa).

---

## 1. ¿De qué trata el proyecto? (explicación sencilla)

Una cadena comercial de Colima vende de dos formas: en **4 tiendas físicas** (Colima Centro, Villa de Álvarez, Tecomán y Manzanillo Puerto) y por una **tienda en línea**. Cada canal guarda sus ventas a su manera:

- la caja registradora (POS) exporta un **CSV** con fechas escritas de tres maneras, filas repetidas, totales vacíos y algunos "bots" que compran 500 piezas;
- la tienda web exporta un **JSON** con nombres de columnas en inglés, precios en dólares y en pesos mezclados, fechas como número (epoch), correos mal escritos y totales inflados 80 veces.

Ambos archivos hacen referencia a un **catálogo maestro** de 50 productos, pero hay ventas de productos que no existen en él.

**Nuestro trabajo:** construir en Python un **pipeline ETL** que:
1. lea los tres archivos sin modificarlos,
2. mida qué tan "sucios" están,
3. los limpie con criterios estadísticos justificados,
4. los integre en una sola tabla con fechas ISO y pesos mexicanos,
5. valide cada registro con **Pydantic**,
6. guarde los buenos en `transacciones_limpias` y desvíe los malos a `cuarentena_errores` **con el motivo**, sin que el programa se caiga,
7. demuestre con números cómo mejoró la calidad.

**La frase que lo resume (de la guía del profesor):** *"Un pipeline no se evalúa porque funcione en el caso ideal, sino por su capacidad de procesar registros corruptos sin colapsar, desviando la anomalía con trazabilidad auditable."*

---

## 2. Requisitos obligatorios del profesor 🟥

Fuente: `GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf`. Es la lista literal de lo que se evalúa.

| # | Requisito | Responsable |
|---|---|---|
| F1 | Perfilado cuantitativo **antes** de transformar: % de nulos por columna, duplicados exactos y dtypes. | Leslie |
| F2 | Clasificar faltantes (MCAR/MAR). Imputar numéricas sesgadas con la **mediana** (justificar por qué no la media). Imputar categóricas con etiquetas controladas (`'ANONIMO'`). Recalcular `monto_total = cantidad × precio_unitario`. | Leslie |
| F3 | IQR = Q3 − Q1 con factor **1.5**. Capping o Winsorizing en lugar de eliminar filas. Eliminar **solo** los valores imposibles (cantidad ≤ 0). | Leslie |
| F4 | Fechas a **YYYY-MM-DD**. USD → MXN a **$19.50**. Merge con el catálogo y marcar las llaves huérfanas para cuarentena. | Yerik |
| F5 | Min-Max a **[0, 1]**. Discretizar el importe en **Bajo, Medio y Alto** (cuantiles o reglas justificadas). | Yerik |
| F6 | Esquemas Pydantic estrictos con validadores personalizados (`BaseModel`, `@field_validator`). `try … except ValidationError` → cuarentena con `motivo_rechazo_cuarentena`. | Nono |
| F7 | SQLite o PostgreSQL con `conn.commit()` y `conn.rollback()`. Tablas obligatorias: `transacciones_limpias` y `cuarentena_errores`. | Nono |
| — | Batería de **pruebas de estrés** con datos corruptos; el pipeline no debe lanzar excepciones no controladas. | Nono |
| — | Roles asignados **explícitamente en el repositorio Git**. | Equipo |
| Día 1 | `REGLAS_DE_NEGOCIO.md` con justificación técnica **firmada** + diagrama de flujo (mockup). | Equipo |
| Día 5 | Entrega final: **repositorio Git + base SQLite + reporte PDF**. Defensa oral de 5 a 7 minutos con **preguntas individuales**. | Equipo |

**Lo que NO pide el profesor** (y por eso no debe consumir tiempo antes del Día 4): la interfaz web, PostgreSQL (SQLite basta) y el proyecto de escritorio AutoMarket. La interfaz web es una mejora del equipo (⬜, sección 8.3).

---

## 3. Análisis inicial de los tres datasets

Cifras obtenidas al ejecutar `python diagnostico/diagnostico_inicial.py` sobre los archivos originales. Huellas SHA-256 en `diagnostico/resultados_diagnostico.json`.

### 3.1 `catalogo_productos.csv`: catálogo maestro

| Propiedad | Valor |
|---|---|
| Dimensiones | 50 filas × 6 columnas (`id_producto, nombre_producto, categoria, precio_base_mxn, stock_minimo, proveedor`) |
| Calidad | 0 nulos · 0 duplicados · IDs `PROD-001` a `PROD-050` |
| Categorías | Hogar 14 · Alimentos 12 · Juguetería 10 · Electrónica 7 · Ropa 5 · Deportes 2 |
| Proveedores | Norte 16 · Centro 13 · Pacífico 12 · Bajío 9 |
| `precio_base_mxn` | mín 332.70 · mediana 1,685.82 · media 2,030.60 · máx 4,218.11 · sin outliers |

**Conclusión:** es la fuente de verdad. No necesita limpieza.

### 3.2 `ventas_tienda_fisica.csv`: POS (620 filas × 9 columnas)

| Columna | dtype inferido | Nulos | Observación |
|---|---|---|---|
| `id_ticket` | str | 0 | `POS-2026-NNNN`; 20 tickets repetidos (duplicados exactos) |
| `fecha_venta` | str | 0 | 3 formatos: DD/MM/YYYY 208 · ISO 207 · DD-MM-YYYY 205 |
| `sucursal` | str | 0 | Manzanillo 166 · Tecomán 160 · Colima Centro 147 · Villa de Álvarez 147 |
| `id_producto` | str | 0 | 29 huérfanos (`PROD-9xx`, todos con precio 500.00) |
| `cantidad` | int64 | 0 | −1 ×6 · 0 ×5 · 1–5 normal · **99 ×7 · 500 ×6** |
| `precio_unitario` | float64 | 0 | coincide 100 % con el catálogo |
| `monto_total_mxn` | float64 | **32 (5.16 %)** | todos recalculables; máximo 2,109,055.00 |
| `id_cliente` | str | **127 (20.48 %)** | `CTE-NNN`; 183 clientes distintos |
| `metodo_pago` | str | 0 | `Efectivo` y `efectivo` sin homologar |

### 3.3 `ventas_online.json`: tienda web (600 registros × 11 campos)

| Campo | Tipo en JSON | Nulos | Observación |
|---|---|---|---|
| `order_id` | str | 0 | `WEB-NNNNN`, sin repetidos |
| `order_timestamp` | **str (392) / int (208)** | 0 | ISO con hora o Unix epoch |
| `product_id` | str | 0 | 33 huérfanos (`PROD-8xx`) |
| `units` | int | 0 | 1 ×362 · 2 ×127 · 3 ×111 |
| `currency` | str | 0 | MXN 407 · **USD 193** |
| `unit_price` | float | 0 | USD × 19.50 = catálogo (diferencia máxima de $0.095) |
| `total_amount` | float | 0 | **12 registros = 80 × units × unit_price** |
| `customer_email` | str/null | **20 (3.33 %)** | 15 `null` + 5 `""`; **28 malformados** |
| `shipping_address` | str/null | **77 (12.83 %)** | — |
| `order_status` | str | 0 | `completado` y `COMPLETADO` sin homologar |
| `payment_gateway` | str | 0 | OXXO Pay 167 · PayPal 149 · Stripe 147 · MercadoPago 137 |

---

## 4. Problemas de calidad encontrados (y quién los resuelve)

| # | Problema real | Evidencia | Regla | Responsable |
|---|---|---|---|---|
| 1 | Duplicados de POS | 20 filas idénticas (filas 601–620 del CSV) | R2.3 | Leslie marca, Nono rechaza |
| 2 | Fechas mixtas | 3 formatos en POS; ISO + epoch en web | R8 | Yerik |
| 3 | Trampa de parseo | `format="mixed", dayfirst=True` interpreta mal 104 fechas | R8.2 | Yerik |
| 4 | Nulos en totales | 32 `monto_total_mxn` vacíos, todos recalculables | R6.2 | Leslie |
| 5 | Totales inflados ("bots" web) | 12 pedidos con total = 80× (ej. `WEB-00508`: 826,360.80 en lugar de 10,329.51) | R6.3 | Leslie |
| 6 | Compras gigantes ("bots" POS) | 13 tickets con 99 o 500 unidades (hasta $2.1 M) | R5.3 | Leslie |
| 7 | Cantidades imposibles | 11 tickets con −1 o 0 | R4 | Nono rechaza |
| 8 | USD vs MXN | 193 pedidos en USD | R7 | Yerik |
| 9 | Productos huérfanos | 29 POS + 33 web | R9 | Yerik marca, Nono rechaza |
| 10 | Correos malformados | 28 (`usuario@@gmail..com`, `sin_arroba_dominio.org`, `correo_invalido.com`) | R10 | Nono |
| 11 | Faltantes categóricos | `id_cliente` 127 · correo 20 · dirección 77 | R3.8 | Leslie |
| 12 | Categóricas sin homologar | `efectivo` 89 / `completado` 98 | R11 | Yerik |
| 13 | Esquemas distintos | nombres en español vs inglés; 9 vs 11 columnas | §6 | Yerik |

Los seis retos que la guía señala para el Grupo 1 (duplicados POS, fechas mixtas, nulos en totales, USD/MXN, correos malformados y bots) **sí aparecen en los datos**.

---

## 5. Arquitectura propuesta 🟦

**Estilo:** pipeline por capas con **funciones puras**: cada función recibe un `DataFrame` y devuelve uno nuevo sin modificar la entrada. Un orquestador (`pipeline.py`) llama a las funciones en orden. Así cada integrante programa y prueba sus funciones **sin tocar los archivos de los demás**.

```
           ┌──────────────── pipeline.py (orquestador · Nono) ───────────────┐
datos/     │                                                                   │   salidas/
crudos/ ──►│ extraccion → calidad.perfilado → integracion.homologacion        │──► comercial.db
(solo      │ → calidad.limpieza → integracion.integrar → calidad.outliers      │    ├ transacciones_limpias
lectura)   │ → integracion.transformacion → validacion → persistencia          │    └ cuarentena_errores
           │ → calidad.reporte (antes vs después)                              │──► reporte_calidad.md + gráficas
           └───────────────────────────────────────────────────────────────────┘
```

**Decisiones de arquitectura (con justificación):**

| Decisión | Por qué |
|---|---|
| Las capas previas a la validación **marcan** y no eliminan | Garantiza `entrada = limpias + cuarentena` (R1.4) y un único punto de rechazo |
| Contratos de columnas en un archivo compartido (`src/contratos.py`) | Evita que un cambio de nombre rompa el módulo de otro integrante |
| Constantes del profesor en `src/config.py` (19.50, 1.5, rutas) | Una sola fuente; se cita en la defensa |
| SQLite (`sqlite3`, biblioteca estándar) | El profesor lo acepta, no requiere servidor y el archivo `.db` se entrega tal cual |
| Valores originales en columnas `*_origen` / `*_original` | Trazabilidad financiera (R5.5, R6.3) |

---

## 6. Diagrama de flujo ETL

El diagrama completo está en **`DIAGRAMA_PIPELINE.md`** (Mermaid) y en imagen en `diagramas/01_flujo_pipeline.png`. Resumen del orden de ejecución:

```
E (Yerik) → F1 (Leslie) → Homologación (Yerik) → F2 (Leslie) → F4 (Yerik) → F3 (Leslie)
          → F5 (Yerik) → F6 (Nono) → F7 (Nono) → F1 bis "después" (Leslie)
```

> **Por qué la F3 va después de la F4:** el IQR del importe debe calcularse en una sola moneda. Si se hace antes de convertir los USD, el límite superior del canal web sale en 7,659.30 en lugar de 8,100.74, porque mezcla dólares con pesos. Ver la ambigüedad A2 en `REGLAS_DE_NEGOCIO.md`.

---

## 7. Estructura inicial de carpetas y archivos

```
sistema-calidad-datos-comerciales/        ← repositorio Git NUEVO (independiente de CRM-Web)
├── README.md                              equipo · roles · cómo ejecutar           (Equipo)
├── REGLAS_DE_NEGOCIO.md                   firmado                                  (Equipo)
├── requirements.txt                                                                (Nono)
├── .gitignore                             __pycache__/, salidas/*.db, .venv/, .env
├── datos/
│   ├── crudos/                            los 3 archivos oficiales · SOLO LECTURA
│   └── estres/                            archivos corruptos para pruebas          (Nono)
├── diagnostico/
│   ├── diagnostico_inicial.py             ✅ ya existe (primer avance)
│   └── resultados_diagnostico.json        ✅ generado
├── diagramas/                             PNG del flujo para el reporte PDF        ✅
├── docs/                                  guías del equipo, diagrama, avance
├── src/
│   ├── __init__.py
│   ├── config.py                          constantes y rutas                       (Equipo, Día 1)
│   ├── contratos.py                       nombres de columnas por etapa            (Equipo, Día 1)
│   ├── extraccion.py                      extraer_fuentes()                        (Yerik)
│   ├── calidad/                                                                    (Leslie)
│   │   ├── __init__.py
│   │   ├── perfilado.py                   perfilar_fuentes(), clasificar_faltantes()
│   │   ├── limpieza.py                    marcar_duplicados(), recalcular_montos(), imputar_*()
│   │   ├── outliers.py                    calcular_limites_iqr(), aplicar_capping()
│   │   └── reporte.py                     comparar_calidad(), graficas antes/después
│   ├── integracion/                                                                (Yerik)
│   │   ├── __init__.py
│   │   ├── homologacion.py                homologar_columnas(), homologar_categoricas()
│   │   ├── fechas.py                      normalizar_fecha(), normalizar_fechas()
│   │   ├── moneda.py                      convertir_a_mxn()
│   │   ├── catalogo.py                    cruzar_catalogo()
│   │   └── transformacion.py              escalar_min_max(), discretizar_importe()
│   ├── validacion/                                                                 (Nono)
│   │   ├── __init__.py
│   │   ├── esquemas.py                    class TransaccionLimpia(BaseModel)
│   │   └── cuarentena.py                  validar_lote(), formatear_motivos()
│   ├── persistencia/                                                               (Nono)
│   │   ├── __init__.py
│   │   ├── esquema.sql                    CREATE TABLE …
│   │   └── carga.py                       crear_tablas(), cargar_lote()
│   └── pipeline.py                        ejecutar_pipeline()                      (Nono)
├── tests/
│   ├── test_calidad.py                                                             (Leslie)
│   ├── test_integracion.py                                                         (Yerik)
│   ├── test_validacion.py                                                          (Nono)
│   ├── test_persistencia.py                                                        (Nono)
│   └── test_estres.py                                                              (Nono)
└── salidas/                               se genera al ejecutar (no se versiona el .db intermedio)
    ├── comercial.db
    ├── reporte_calidad.md
    └── graficas/
```

**Reglas de colaboración en Git:**
1. Cada integrante trabaja en su rama: `calidad-leslie`, `integracion-yerik`, `validacion-nono`.
2. **Solo se editan los archivos propios.** `config.py` y `contratos.py` se cambian únicamente por acuerdo de los tres, con un commit `contrato: …`.
3. Merge a `main` al final de cada día, después de que `pytest` pase.
4. `datos/crudos/` nunca se modifica. Se puede comprobar con las huellas SHA-256 del diagnóstico.
5. **No se copia nada de CRM-Web.zip al repositorio nuevo** (en particular, su `backend/.env`).

---

## 8. Tecnologías

### 8.1 Obligatorias / núcleo

| Tecnología | Versión sugerida | Uso |
|---|---|---|
| Python | 3.11 o superior | lenguaje del pipeline |
| pandas | 2.x | lectura, limpieza y cruce |
| numpy | 1.26+ / 2.x | cálculos numéricos |
| **pydantic** | **2.x** | `BaseModel` y `@field_validator` (Fase 6) |
| sqlite3 | biblioteca estándar | Fase 7 |
| scipy | 1.11+ | prueba χ² para MCAR/MAR (opcional pero recomendada) |
| pytest | 8.x | pruebas unitarias y de estrés |
| matplotlib | 3.8+ | gráficas antes/después para el reporte |
| Git + GitHub | — | repositorio entregable y roles |
| DB Browser for SQLite | — | capturas de las tablas |

`requirements.txt` sugerido:
```
pandas>=2.0
numpy>=1.26
pydantic>=2.5
scipy>=1.11
matplotlib>=3.8
pytest>=8.0
```

> **Nota para Windows:** si Application Control bloquea NumPy o pandas en VS Code, todo el pipeline puede ejecutarse en **Google Colab** (sube la carpeta del proyecto o clona el repositorio). `sqlite3` funciona igual y el archivo `comercial.db` se descarga al terminar.

### 8.2 Lo que se puede reutilizar de CRM-Web (solo como referencia)

CRM-Web usa Node, Express, TypeScript y **Zod**, mientras que la guía exige **Python + Pydantic**, así que **su backend no se reutiliza**. Sí sirven como inspiración:
- la idea de **procedencia por campo** y la "cola de revisión" (equivalente a nuestra cuarentena);
- la presentación **antes/después** del laboratorio de reducción (`frontend/src/pages/Reduccion.tsx`);
- los componentes visuales (`Layout`, `Card`, `Table`, `Badge`) y las gráficas con Recharts, si se hace la interfaz web.

### 8.3 Interfaz web comercial ⬜ (mejora del equipo, no obligatoria)

- **Cuándo:** solo después de que el pipeline corra de inicio a fin (Día 4).
- **Qué mostraría:** KPI de ventas por canal y segmento; calidad antes/después; tabla `transacciones_limpias` con filtros; tabla `cuarentena_errores` con motivo y registro original.
- **Regla:** solo **lee** `comercial.db` y no limpia datos, porque toda la lógica vive en el pipeline.
- **Decisión pendiente del equipo:** (a) FastAPI + frontend React/Tailwind inspirado en CRM-Web, o (b) Streamlit (más rápido, todo en Python). No se debe empezar sin acordarlo.

---

## 9. Cómo se conectan los módulos (contratos)

### 9.1 Esquema unificado (`src/contratos.py`, se acuerda el Día 1)

**Mapeo de columnas que hace Yerik en la homologación:**

| Columna unificada | Tienda física (CSV) | Tienda online (JSON) | Tipo tras homologar |
|---|---|---|---|
| `id_transaccion` | `id_ticket` | `order_id` | str |
| `origen` | constante `FISICA` | constante `ONLINE` | str |
| `id_fila_origen` | número de fila (1 = primera fila de datos) | índice + 1 | int |
| `fecha_cruda` | `fecha_venta` | `order_timestamp` | str (sin interpretar) |
| `punto_venta` | `sucursal` | constante `TIENDA_ONLINE` | str |
| `id_producto` | `id_producto` | `product_id` | str |
| `cantidad` | `cantidad` | `units` | numérico o `None` (+ alerta si no es numérico) |
| `precio_unitario` | `precio_unitario` | `unit_price` | float (en la moneda original) |
| `monto_total` | `monto_total_mxn` | `total_amount` | float o `None` (en la moneda original) |
| `moneda` | constante `MXN` | `currency` (mayúsculas) | str |
| `id_cliente` | `id_cliente` | `None` (no aplica) | str o `None` |
| `email_cliente` | `None` (no aplica) | `customer_email` | str o `None` |
| `direccion_envio` | `None` (no aplica) | `shipping_address` | str o `None` |
| `metodo_pago` | `metodo_pago` (MAYÚSCULAS) | `payment_gateway` (MAYÚSCULAS) | str |
| `estado_pedido` | `None` (no aplica) | `order_status` (MAYÚSCULAS) | str o `None` |
| `registro_original` | fila cruda en JSON | objeto crudo en JSON | str |
| `alertas` | `[]` | `[]` | list[str]: errores de tipo detectados antes de validar |
| `correcciones` | `[]` | `[]` | list[str]: bitácora de cambios aplicados |

### 9.2 Columnas que agrega cada etapa

| Etapa | Función principal | Agrega |
|---|---|---|
| F2 · Leslie | `limpiar_registros(df)` | `es_duplicado`, `es_id_conflicto`, `monto_total_origen`; corrige `monto_total`, `cantidad`, `id_cliente`, `email_cliente`, `direccion_envio` |
| F4 · Yerik | `integrar(df, catalogo)` | `fecha_venta` (ISO o `None`), `precio_unitario_mxn`, `monto_total_mxn`, `moneda_original`, `tipo_cambio_aplicado`, `nombre_producto`, `categoria`, `precio_catalogo_mxn`, `en_catalogo` |
| F3 · Leslie | `tratar_outliers(df)` | `cantidad_cap`, `monto_total_mxn_cap`, `es_outlier_cantidad`, `es_outlier_monto` (+ devuelve los límites IQR) |
| F5 · Yerik | `transformar(df)` | `monto_minmax`, `segmento_importe` (+ devuelve min, max y cortes) |
| F6 · Nono | `validar_lote(df)` | separa en `validos` y `cuarentena` |
| F7 · Nono | `cargar_lote(...)` | escribe ambas tablas en una transacción |

### 9.3 Tablas finales (resumen; el detalle está en la guía de Nono)

- **`transacciones_limpias`** (PK `id_transaccion`): `origen, fecha_venta, punto_venta, id_producto, nombre_producto, categoria, cantidad, cantidad_cap, precio_unitario_mxn, moneda_original, tipo_cambio_aplicado, monto_total_origen, monto_total_mxn, monto_total_mxn_cap, monto_minmax, segmento_importe, id_cliente, email_cliente, direccion_envio, metodo_pago, estado_pedido, es_outlier_cantidad, es_outlier_monto, correcciones, lote_id, fecha_carga`.
- **`cuarentena_errores`** (PK `id_error` autoincremental): `lote_id, id_registro, origen, id_fila_origen, etapa_deteccion, codigos_error, motivo_rechazo_cuarentena, registro_original, fecha_cuarentena`.

### 9.4 Cómo trabajar en paralelo sin esperar al otro

Cada integrante crea en sus pruebas un **DataFrame pequeño de ejemplo** con las columnas del contrato de la etapa anterior y programa contra él. Por ejemplo, Nono puede probar `validar_lote()` desde el Día 1 con 5 registros escritos a mano, sin esperar a Yerik. Al integrar, solo se cambia la entrada de prueba por la salida real.

---

## 10. Cronograma de trabajo con entregables

Basado en el cronograma oficial (sección 5 de la guía). Los días son relativos al inicio del proyecto.

| Día | Oficial 🟥 | Leslie | Yerik | Nono | Entregable |
|---|---|---|---|---|---|
| **1** | Encuadre, lectura de datos, diagrama | Revisar y entender el diagnóstico; definir los criterios MCAR/MAR | Revisar el mapeo de columnas; `extraccion.py` | Crear el repositorio, `config.py`, `contratos.py`, README con roles | 🟥 `REGLAS_DE_NEGOCIO.md` firmado + diagrama · ✅ **primer avance** |
| **2** | Imputación, IQR, integración | `perfilado.py`, `limpieza.py` + pruebas | `homologacion.py`, `fechas.py`, `moneda.py`, `catalogo.py` + pruebas | `esquemas.py` (modelo + validadores) con datos de ejemplo | 🟥 Código de limpieza y cruce en Git |
| **3** | Escalamiento, Pydantic | `outliers.py`; integrar con la salida de Yerik | `transformacion.py`; integrar con la salida de Leslie | `cuarentena.py` (`validar_lote`), `esquema.sql` | 🟥 Módulo Pydantic + cuarentena operativa |
| **4** | BD, transacciones, estrés | `reporte.py` (antes/después + gráficas) | Pruebas de integración end-to-end | `carga.py`, `pipeline.py`, `test_estres.py` | 🟥 Pipeline end-to-end funcionando |
| **5** | Defensa oral | Ensayar la defensa | Ensayar la defensa | Ensayar la defensa | 🟥 Repositorio + `comercial.db` + reporte PDF |

**Dependencias críticas:**
- `contratos.py` (Día 1) bloquea a todos, así que es lo primero.
- `homologar_columnas` (Yerik) → `limpiar_registros` (Leslie) → `integrar` (Yerik) → `tratar_outliers` (Leslie) → `transformar` (Yerik) → `validar_lote` (Nono).
- Mientras tanto, cada quien avanza con datos de ejemplo (§9.4).

---

## 11. Criterios de "proyecto terminado" (definición de hecho)

El proyecto está terminado **solo si todas** estas condiciones se comprueban ejecutando el código, no "porque parece que funciona":

- [ ] `python -m src.pipeline` corre de inicio a fin sin excepciones no controladas.
- [ ] `datos/crudos/` mantiene las mismas huellas SHA-256 que en el diagnóstico.
- [ ] `SELECT COUNT(*)` de `transacciones_limpias` + `cuarentena_errores` = **1,220**.
- [ ] Los conteos coinciden con la referencia (o la diferencia está explicada): **1,104** limpias y **116** en cuarentena.
- [ ] Ningún registro de cuarentena tiene `motivo_rechazo_cuarentena` vacío.
- [ ] Todas las `fecha_venta` cumplen `^\d{4}-\d{2}-\d{2}$`, y todas las monedas de la tabla limpia están en MXN.
- [ ] No hay `id_producto` de la tabla limpia ausente del catálogo (comprobado con `LEFT JOIN`).
- [ ] `monto_minmax` está entre 0 y 1; `segmento_importe` ∈ {Bajo, Medio, Alto}.
- [ ] Límites IQR: cantidad física LS = 8.5 (tope 8); monto LS ≈ 12,032.68.
- [ ] `pytest` pasa en verde, incluida la batería de estrés.
- [ ] La prueba de rollback demuestra **0 filas parciales** tras un error forzado.
- [ ] El reporte antes/después existe con cifras reales.
- [ ] El README indica los roles y los comandos para ejecutar.
- [ ] Cada integrante puede explicar su módulo **y** el flujo completo.

---

## 12. Relación de requisitos con la rúbrica oficial (100 pts)

| Criterio de la rúbrica | Pts | Qué lo demuestra en nuestro proyecto | Responsable | Archivo / evidencia |
|---|---|---|---|---|
| 1. Mockup y Reglas de Negocio | 10 | Diagrama de flujo completo + reglas con justificación estadística y firmas | Equipo | `REGLAS_DE_NEGOCIO.md`, `DIAGRAMA_PIPELINE.md` |
| 2. Calidad de Datos (Nulos y Outliers) | 20 | χ² para MCAR; mediana justificada (media 16,586 vs mediana 3,506); capping sin borrar filas; columnas `_cap` | Leslie | `src/calidad/*`, `reporte_calidad.md` |
| 3. Integración y Transformación | 20 | 3 formatos de fecha + epoch → ISO; USD → MXN verificado contra el catálogo; huérfanos; Min-Max; terciles | Yerik | `src/integracion/*` |
| 4. Validación Pydantic y Cuarentena | 20 | `BaseModel` + `@field_validator` con códigos de error; todos los motivos por registro | Nono | `src/validacion/*`, tabla `cuarentena_errores` |
| 5. Persistencia y Transacciones | 15 | `commit`/`rollback`; prueba de 0 filas parciales; tablas legibles | Nono | `src/persistencia/*`, `comercial.db` |
| 6. Resiliencia y Defensa Oral | 15 | Batería de estrés; conteo conservado; dominio individual | Equipo | `tests/test_estres.py`, ensayo de la defensa |

**Recomendación para la defensa:** cada integrante debe poder responder también una pregunta básica de los otros dos módulos, porque las preguntas son individuales y pueden tocar cualquier parte. Las preguntas probables están en cada guía individual.
