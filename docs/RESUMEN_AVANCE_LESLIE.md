# Resumen técnico · Etapa 1: Ingeniera 1 (Leslie) · Calidad, Nulos y Outliers

**Proyecto:** Sistema de Integración y Calidad de Datos Comerciales *(nombre provisional)*
**Fecha de ejecución verificada:** 2026-10-25 · Python 3.13.16 · pandas 3.0.5 (compatibilidad también comprobada con pandas 2.2.3)
**Fuente principal:** `docs/GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf` · reglas en `docs/avance01/REGLAS_DE_NEGOCIO.md`

---

## 1. Qué se hizo y en qué estado está

| Actividad | Estado | Cómo se comprobó |
|---|---|---|
| Proyecto Python nuevo; ZIP del Avance 01 y originales intactos | ✅ | SHA-256 del ZIP idéntico antes y después; los 3 originales coinciden con las huellas del diagnóstico y se verifican en cada ejecución |
| `src/contratos.py` y `src/config.py` | ✅ | Cada etapa valida su entrada con `verificar_columnas()` (probado) |
| Extracción y homologación mínimas (Yerik) | ✅ mínima | 1,220 filas (620 + 600); 18 columnas del contrato; 13 pruebas |
| `perfilado.py` (F1) | ✅ | Reproduce completitud, nulos, duplicados y los 8 p-valores χ² del diagnóstico |
| `limpieza.py` (F2) | ✅ | 20 duplicados, 32 + 12 montos, 127/20/77 etiquetas, medianas por canal |
| `outliers.py` (F3) | ✅ | LS cantidad 8.5 → tope 8 (13); LS monto 12,032.68 (80 en la base) |
| USD→MXN y catálogo, solo lo necesario para el IQR en MXN (Yerik) | ✅ mínima | 193 conversiones; 29 + 33 huérfanos; USD vs catálogo ≤ 0.10 |
| `reporte.py` (antes/después + comparación con la referencia) | ✅ | 39/41 coincidencias exactas; 2 diferencias explicadas y probadas |
| Pruebas unitarias | ✅ **78/78** | `salidas/etapa_leslie/pytest_pandas3.txt` y `pytest_pandas2.txt` |
| Evidencias | ✅ archivos · ⏳ capturas | Las capturas las toma el equipo (`evidencias/GUIA_CAPTURAS_LESLIE.md`) |
| Comparación "después" sobre la tabla final de SQLite | ⏳ **pendiente** | Requiere los módulos de Nono |

---

## 2. Archivos creados

| Archivo | Responsable | Contenido |
|---|---|---|
| `src/config.py` | compartido | Paridad `Decimal("19.50")`, factor 1.5, tolerancia 0.01, etiquetas, huellas SHA-256, `redondear()` HALF_UP |
| `src/contratos.py` | compartido | Columnas de origen, mapeo al esquema unificado, columnas por etapa, códigos de corrección/alerta, `verificar_columnas()` |
| `src/extraccion.py` | Yerik (mín.) | Lectura sin conversiones; `id_fila_origen`, `registro_original`; `ErrorExtraccion`; `verificar_integridad()` |
| `src/integracion/homologacion.py` | Yerik (mín.) | Esquema unificado, `a_numero()` con alertas, mayúsculas, `""` → `None` |
| `src/integracion/moneda.py` | Yerik (mín.) | `convertir_a_mxn()` con Decimal HALF_UP |
| `src/integracion/catalogo.py` | Yerik (mín.) | `cruzar_catalogo()` LEFT JOIN, `validate="many_to_one"`, `en_catalogo` |
| `src/calidad/perfilado.py` | Leslie | `es_vacio`, `inferir_tipo`, `perfilar_dataframe/fuentes`, `perfil_a_tabla`, `clasificar_faltantes(_por_canal)`, `metricas_calidad` |
| `src/calidad/limpieza.py` | Leslie | `marcar_duplicados`, `imputar_mediana`, `mediana_entera`, `recalcular_montos`, `imputar_categoricas`, `limpiar_registros` |
| `src/calidad/outliers.py` | Leslie | `calcular_limites_iqr`, `mascara_base_estadistica`, `aplicar_capping_cantidad/monto`, `tratar_outliers` |
| `src/calidad/reporte.py` | Leslie | `tabla_antes_despues`, `comparar_con_referencia`, `graficar_boxplots` |
| `scripts/ejecutar_etapa_leslie.py` | Leslie | Ejecuta la etapa y escribe `salidas/etapa_leslie/` |
| `tests/*.py` (6 archivos) | Leslie / Yerik | 78 pruebas |

---

## 3. Métricas obtenidas (ejecución real)

### 3.1 Perfil inicial (F1)

| Archivo | Filas × col. | Completitud | Duplicados | Columnas con faltantes |
|---|---|---|---|---|
| Catálogo | 50 × 6 | 100 % | 0 | — |
| Tienda física | 620 × 9 | 97.15 % | 20 | `monto_total_mxn` 32 (5.16 %) · `id_cliente` 127 (20.48 %) |
| Tienda online | 600 × 11 | 98.53 % | 0 | `customer_email` 20 (3.33 %) · `shipping_address` 77 (12.83 %) |

Tipo detectado que merece atención: `order_timestamp` es **mixto (int, str)**: 208 epoch y 392 texto en el mismo campo.

### 3.2 Faltantes (χ², α = 0.05): todos MCAR

| Canal | Columna | vs | χ² | gl | p |
|---|---|---|---|---|---|
| Física | id_cliente | sucursal / método de pago | 1.36 / 2.92 | 3 / 4 | 0.714 / 0.571 |
| Física | monto_total | sucursal / método de pago | 2.48 / 2.94 | 3 / 4 | 0.479 / 0.569 |
| Online | correo | pasarela / moneda | 1.09 / 1.01 | 3 / 1 | 0.779 / 0.314 |
| Online | dirección | estado / pasarela | 5.07 / 2.20 | 4 / 3 | 0.280 / 0.532 |

### 3.3 Limpieza (F2)

| Acción | Registros |
|---|---|
| Duplicados exactos marcados (`es_duplicado`) | 20 (filas 601–620 del CSV) |
| IDs con contenido en conflicto | 0 |
| Montos nulos recalculados | 32 |
| Totales inconsistentes recalculados (factor exacto ×80) | 12 |
| `ANONIMO` / `SIN_CORREO` / `SIN_DIRECCION` | 127 / 20 / 77 |
| Imputación por mediana de la cantidad | 0 (medianas por canal: física 2, online 1; función probada con datos sintéticos) |

### 3.4 Outliers (F3) · base estadística 1,129 (562 física + 567 online)

| Variable | Q1 | Q3 | IQR | LI | LS | Fuera de límite | Recortados |
|---|---|---|---|---|---|---|---|
| Cantidad física | 1 | 4 | 3 | −3.5 | 8.5 → tope 8 | 13 | 13 |
| Cantidad online | 1 | 2 | 1 | −0.5 | 3.5 | 0 | 0 |
| Importe MXN unificado | 1,563.78 | 5,751.34 | 4,187.56 | −4,717.56 | **12,032.68** | 80 (base) | 82 (ver §5) |

### 3.5 Antes / después (etapa de Leslie, sin la cuarentena todavía)

| Métrica | Antes | Después |
|---|---|---|
| Filas | 1,220 | 1,220 (no se elimina ninguna) |
| Montos nulos | 32 | 0 |
| Montos ≠ cantidad × precio | 12 | 0 |
| Faltantes categóricos (id_cliente / correo / dirección) | 127 / 20 / 77 | 0 / 0 / 0 |
| Cantidad máxima física | 500 | 8 (`cantidad_cap`) |
| Importe MXN en la base: media | 12,470.24 | 4,122.11 |
| Importe MXN en la base: mediana | 3,149.64 | 3,127.42 |
| Importe MXN en la base: máximo | 2,109,055.00 | 12,032.68 |
| Importe MXN en la base: asimetría | 17.04 | 1.16 |
| Cantidades ≤ 0 | 11 | 11 (se conservan marcadas para la cuarentena) |

La mediana casi no cambia (−0.7 %), mientras la media baja 67 % y la asimetría pasa de 17.0 a 1.2. Ese es el efecto esperado del capping: corrige los extremos sin alterar el centro de la distribución.

---

## 4. Trazabilidad: columnas originales junto a las tratadas

| Original (nunca se modifica) | Tratada | Ejemplo real |
|---|---|---|
| `cantidad_origen` | `cantidad` (imputada si faltaba) → `cantidad_cap` | `POS-2026-0031`: 500 → 500 → 8 |
| `monto_total_origen` | `monto_total` (recalculado) → `monto_total_mxn` → `monto_cantidad_cap_mxn` → `monto_total_mxn_cap` | `POS-2026-0021`: 208,598.94 → … → 16,856.48 → 12,032.68 |
| `monto_total_origen` | `monto_total` | `WEB-00508`: 826,360.80 → 10,329.51 |
| `precio_unitario` (USD) | `precio_unitario_mxn` | `WEB-00002`: 169.59 → 3,307.01 |
| `registro_original` (JSON crudo) | — | todas las filas |
| `correcciones` (lista de códigos) | — | `["CAPPING_IQR_CANTIDAD", "CAPPING_IQR_MONTO"]` |

---

## 5. Comparación con la referencia del diagnóstico: 39 de 41 coinciden

| Métrica | Referencia | Obtenido | Explicación (verificada con prueba automática) |
|---|---|---|---|
| Montos recortados | 80 | 82 | La referencia contó solo la base. El pipeline aplica el recorte a toda fila con cantidad > 0, y **2 duplicados exactos** (filas 608 y 609, copias de `POS-2026-0257` y `POS-2026-0457`) superan el LS. Irán a cuarentena por `DUPLICADO_EXACTO`; en la base, los recortes siguen siendo 80. |
| Diferencia máx. USD × 19.50 vs catálogo | 0.095 | 0.10 | El diagnóstico comparó el precio sin redondear (46.45 × 19.5 = 905.775). El pipeline aplica `ROUND_HALF_UP` (R6.4) → 905.78, frente a 905.68 del catálogo. Sigue dentro de la tolerancia de ±0.50. |

Todas las demás métricas coinciden exactamente o dentro de la tolerancia de redondeo: dimensiones, completitud, nulos, 8 p-valores, base estadística, Q1/Q3/IQR/LS de cantidad y monto, mediana y asimetría. Tabla completa en `salidas/etapa_leslie/07_comparacion_referencia.csv`.

---

## 6. Decisiones técnicas que el equipo debe revisar

| # | Decisión | Por qué | Impacto en los datos oficiales | Alternativa |
|---|---|---|---|---|
| D1 | **Mediana entera** (ROUND_HALF_UP) al imputar la cantidad | La cantidad es discreta; una mediana de 1.5 no es una venta posible | 0 casos (medianas 2 y 1) | Mediana sin redondear (rompería el tipo entero) |
| D2 | Se agregó la columna **`cantidad_origen`** al contrato | El punto 5 de la consigna pide conservar la cantidad original; la imputación la modificaría | Columna nueva para Yerik y Nono | — |
| D3 | Se agregó **`monto_cantidad_cap_mxn`** (monto con la cantidad ya topada, antes del tope de monto) | Hace visibles los dos pasos del capping | Columna informativa | Omitirla |
| D4 | Capping aplicado a **toda fila con cantidad > 0**, con límites calculados solo con la base | Ninguna fila queda sin columna tratada | 82 recortes en lugar de 80 (2 duplicados) | Recortar solo la base (80) |
| D5 | Las filas con **cantidad ≤ 0 pasan sin recorte** (`cantidad_cap` −1, `monto_total_mxn_cap` −934.83) | Son imposibles, no atípicas; recortarlas a 1 las haría parecer válidas | 11 filas | — · **Yerik debe recortar Min-Max a [0, 1]** y Nono las rechaza |
| D6 | `monto_total` queda en la **moneda original**; la columna en MXN es `monto_total_mxn` | Así se recalcula sin depender de la conversión | 193 filas USD | — |
| D7 | `monto_total_mxn` = redondear(cantidad × precio en MXN), no total × 19.50 | Coherencia exacta para el validador de Nono | Difiere en centavos en 55 pedidos USD | Convertir el total directo |
| D8 | **Validez del χ²:** en "correo vs pasarela" hay 3 celdas con frecuencia esperada < 5 (y 1 en "monto vs método de pago") | La aproximación χ² pierde precisión con frecuencias esperadas bajas | La conclusión no cambia (p = 0.779 y 0.569, lejos de 0.05) | Mencionarlo en el reporte o complementar con una prueba exacta |
| D9 | **Pendientes con el profesor** (vienen del Avance 01): recalcular o rechazar los 12 totales ×80 (A9) y calcular el IQR después de convertir (A2) | — | 12 y 80 registros | Si el profesor decide distinto, solo cambian `recalcular_montos()` o el orden de llamada |

---

## 7. Qué recibe Yerik

**Archivo:** `salidas/etapa_leslie/09_salida_etapa_leslie.csv` (1,220 filas × 37 columnas). En código, la salida de `tratar_outliers()`.

| Yerik debe… | Detalle |
|---|---|
| Revisar y adueñarse de las 4 versiones mínimas | `extraccion.py`, `homologacion.py`, `moneda.py`, `catalogo.py` (22 casos de prueba en `test_extraccion_homologacion.py` + 4 en `test_outliers.py`) |
| Implementar `fechas.py` | Parseo explícito por patrón; epoch UTC → America/Mexico_City (pendiente A8) |
| Implementar `transformacion.py` | Min-Max y terciles sobre `monto_total_mxn_cap`, usando `mascara_base_estadistica()` y recortando a [0, 1] (D5) |
| Reordenar si hace falta | Fechas pueden ir antes o después de F3: no afectan el IQR |

---

## 8. Cómo reproducir

```bash
pip install -r requirements.txt
python -m pytest                          # 78 passed
python scripts/ejecutar_etapa_leslie.py   # 39/41 coincidencias; ~1 s
```
