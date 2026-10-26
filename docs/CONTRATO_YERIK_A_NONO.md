# Contrato de entrega · Yerik → Nono (`df_transformado`)

**Producido por:** `src/integracion/transformacion.transformar(df_outliers)` (F5), encadenado como
`extraer → homologar → limpiar_registros → integrar → tratar_outliers → transformar`
(`scripts/ejecutar_etapa_yerik.py` ejecuta toda la cadena).
**Archivo de muestra real:** `salidas/etapa_yerik/10_salida_etapa_yerik.csv` (1,220 filas × 41 columnas; `alertas` y `correcciones` serializadas como JSON).
**Lista de columnas:** `salidas/etapa_yerik/10_columnas_entrega.json`.

## 1. Garantías

| Garantía | Verificada por |
|---|---|
| 1,220 filas (620 FISICA + 600 ONLINE); **ninguna se elimina** | `test_integrar_conserva_1220_filas_y_contrato`, `test_transformar_conserva_filas_y_columnas_de_leslie` |
| Los valores originales no se modifican (`registro_original`, `fecha_cruda`, `precio_unitario`, `monto_total`, `moneda`, `cantidad_origen`, `monto_total_origen`) | `test_integrar_no_altera_valores_originales`, `test_transformar_conserva_filas_y_columnas_de_leslie` |
| `fecha_venta` es `YYYY-MM-DD` o `None` (hoy 0 `None`) | `test_todas_las_fechas_reales_se_interpretan` |
| `monto_minmax` ∈ [0, 1] en **todas** las filas con importe; `segmento_importe` ∈ {Bajo, Medio, Alto} en todas las filas con importe | `test_minmax_rango_y_extremos_de_la_base`, `test_segmentos_reales` |
| Los registros que irán a cuarentena siguen presentes y marcados (20 duplicados, 11 con cantidad ≤ 0, 62 huérfanos) | `test_cuarentena_no_pierde_registros` |
| `NaN` solo en columnas numéricas (float64); texto ausente = `None` | revisar `a_texto_json`/`astype(object)` antes de Pydantic (ver §4) |

## 2. Columnas que Nono usa para decidir

| Columna | Tipo | Valores / significado | Código de rechazo propuesto |
|---|---|---|---|
| `id_transaccion` | str | `POS-AAAA-NNNN` / `WEB-NNNNN` | `ID_FORMATO_INVALIDO` |
| `origen` | str | `FISICA` / `ONLINE` | — |
| `fecha_venta` | str \| None | ISO `YYYY-MM-DD`; `None` si no se pudo interpretar (alerta `FECHA_NO_INTERPRETABLE`) | `FECHA_INVALIDA` |
| `en_catalogo` | bool | `False` = producto huérfano (22 + 30 IDs, 29 + 33 registros) | `PRODUCTO_HUERFANO` |
| `moneda_original` | str | `MXN`, `USD` (otra → alerta `MONEDA_NO_SOPORTADA` y columnas MXN en NaN) | `MONEDA_NO_SOPORTADA` |
| `precio_unitario_mxn`, `tipo_cambio_aplicado` | float | USD × 19.50, Decimal HALF_UP a centavos | `PRECIO_*` |
| `monto_total_mxn` | float | `redondear(cantidad × precio_unitario_mxn)` | `MONTO_*` |
| `cantidad`, `cantidad_cap` | float | Nono las convierte a `int`; 11 filas con `cantidad` ≤ 0 | `CANTIDAD_INVALIDA` |
| `monto_total_mxn_cap` | float | importe con capping IQR (Leslie) | — |
| `monto_minmax` | float \| None | (x − 332.67) / (12 032.68 − 332.67), acotado a [0, 1]; 6 decimales | `ESCALA_FUERA_DE_RANGO` (hoy 0 casos) |
| `segmento_importe` | str \| None | Bajo ≤ 2,069.07 < Medio ≤ 4,183.67 < Alto | `TIPO_INVALIDO` |
| `es_duplicado`, `es_id_conflicto` | bool | de Leslie | `DUPLICADO_EXACTO`, `ID_REPETIDO_CONFLICTO` |

## 3. Columnas nuevas o con significado a tener en cuenta

| Columna | De | Uso |
|---|---|---|
| `minmax_recortado` (bool) | Yerik, **nueva** | `True` en 11 filas (las de `cantidad` ≤ 0): su importe quedó fuera del rango [min, max] de la base y se acotó a [0, 1]. Informativa; Nono puede ignorarla (`extra="ignore"`) o guardarla en la cuarentena. |
| `cantidad_origen`, `monto_cantidad_cap_mxn` | Leslie | Se conservan intactas; `monto_cantidad_cap_mxn` es el importe con la cantidad ya topada, antes del tope de monto. |
| `es_base_estadistica` | Leslie | Población usada para min/max y terciles (1,129 filas). Informativa. |
| `fecha_cruda` | Yerik | Texto original de la fecha (epoch como texto). |
| `alertas` (lista) | todos | Nuevos códigos de Yerik: `FECHA_NO_INTERPRETABLE`, `PRECIO_DIFIERE_CATALOGO` (informativa, no rechaza). Con los datos oficiales la lista está vacía en las 1,220 filas. |
| `correcciones` (lista) | todos | Nuevos códigos de Yerik: `FECHA_DESDE_{DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, ISO_DATETIME, EPOCH}`. |

## 4. Qué debe hacer Nono antes de validar

1. Convertir `NaN` a `None` y tipos numpy a tipos Python (`df.astype(object).where(df.notna(), None)`).
2. `cantidad` y `cantidad_cap` llegan como `float` (p. ej. `2.0`): validar que sean enteros > 0 y convertir.
3. Una fila con `cantidad` ≤ 0 llega **con** `monto_minmax` y `segmento_importe` válidos a propósito: así solo se rechaza por `CANTIDAD_INVALIDA` y no por un segundo motivo artificial. Si el equipo prefiere `None` en esos casos, es un cambio de una línea en `escalar_min_max` (decisión pendiente D-Y1).
4. Regla R8.5 (fecha posterior a la fecha de ejecución → `FECHA_INVALIDA`): **no está implementada en la etapa de Yerik**; corresponde al validador. Con los datos oficiales la fecha máxima es 2026-10-16.
5. Zona horaria del epoch: America/Mexico_City (UTC−6). Pendiente de confirmar con el docente (A8); no afecta el contrato, solo 49 valores de `fecha_venta`.

## 5. Códigos añadidos a `src/contratos.py` (cambio compartido, solo adiciones)

`ALERTA_FECHA_NO_INTERPRETABLE`, `ALERTA_PRECIO_DIFIERE_CATALOGO`, `corr_fecha()`, `COLUMNAS_AGREGA_FECHAS`, `COLUMNAS_AGREGA_TRANSFORMACION`, `REQUERIDAS_INTEGRACION`, `REQUERIDAS_TRANSFORMACION`. No se renombró ni se eliminó nada: los 78 tests de Leslie pasan sin cambios.
