# REGLAS DE NEGOCIO Y JUSTIFICACIÓN TÉCNICA

**Proyecto:** Sistema de Integración y Calidad de Datos Comerciales *(nombre provisional)*
**Materia:** Ingeniería de Datos (ATD-2602) · Unidad 2: Limpieza y Preprocesamiento de Datos
**Institución:** TecNM · Instituto Tecnológico de Colima · Semestre Ago-Dic 2026
**Docente:** Prof. Armando Román Gallardo Heredia
**Sector asignado:** Grupo 1 (LCS2) · Retail & E-commerce Omnicanal
**Versión:** 1.0 (propuesta para el Día 1, pendiente de firma)

---

## 0. Cómo leer este documento

Cada regla tiene un identificador y una **etiqueta de origen**:

| Etiqueta | Significado |
|---|---|
| 🟥 **[PROF]** | Regla exigida explícitamente en `GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf`. No es negociable. |
| 🟦 **[EQUIPO]** | Decisión técnica propuesta por el equipo para cumplir una regla [PROF] o resolver una ambigüedad. Se justifica con datos. |

Y una **acción** sobre el registro:

| Acción | Qué significa | ¿Llega a `transacciones_limpias`? |
|---|---|---|
| **CONSERVAR** | El valor es correcto; solo se homologa el formato (mayúsculas, fecha ISO, etc.). | Sí |
| **CORREGIR** | El valor se repara de forma determinista o estadística y **se guarda el valor original** y una bandera de corrección. | Sí |
| **CUARENTENA** | El registro no puede repararse sin inventar datos. Se desvía a `cuarentena_errores` con `motivo_rechazo_cuarentena`. | No |

> **Principio rector [PROF]:** el pipeline no se detiene ante registros corruptos (*no crash*). Toda anomalía se desvía con trazabilidad auditable.
> **Principio de trazabilidad [EQUIPO]:** ningún valor financiero se sobrescribe sin conservar su versión original en otra columna.

Todas las cifras de este documento salen de `diagnostico/diagnostico_inicial.py` ejecutado sobre los archivos originales (ver `diagnostico/resultados_diagnostico.json`).

---

## 1. Datos válidos e inválidos

| ID | Origen | Regla |
|---|---|---|
| R1.1 | 🟥 PROF | Un registro válido es el que cumple el esquema Pydantic definido para `transacciones_limpias`. El que lo viola se captura con `try … except ValidationError` y va a cuarentena. |
| R1.2 | 🟦 EQUIPO | Se distinguen tres tipos de defecto: **(a) de formato** (fechas mixtas, mayúsculas, moneda) → CONSERVAR homologando; **(b) reparable** (monto nulo con cantidad y precio presentes, total inconsistente, categórica faltante, outlier) → CORREGIR con bandera; **(c) estructural** (duplicado, cantidad ≤ 0, producto huérfano, correo malformado, fecha imposible) → CUARENTENA. |
| R1.3 | 🟦 EQUIPO | La decisión final de rechazo la toma **solamente** la capa de validación (Ingeniero 3). Las capas de limpieza e integración **marcan** con banderas, no eliminan filas. Así existe un único punto de salida a cuarentena y ningún registro se pierde sin explicación. |
| R1.4 | 🟦 EQUIPO | Regla de conservación de conteo: `filas_entrada = filas_transacciones_limpias + filas_cuarentena_errores`. Si no cuadra, la ejecución se considera fallida. |

## 2. Identificadores y duplicados

**Evidencia:** la tienda física tiene **20 duplicados exactos** (filas 601–620 del CSV repiten tickets anteriores, por ejemplo `POS-2026-0001`). Ningún `id_ticket` se repite con contenido distinto. La tienda online tiene **0 duplicados** y **0 `order_id` repetidos**.

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R2.1 | 🟥 PROF | Medir la unicidad (conteo de duplicados exactos) en el diagnóstico inicial. | — |
| R2.2 | 🟦 EQUIPO | Los formatos válidos de identificador son `POS-AAAA-NNNN` para la tienda física y `WEB-NNNNN` para la online. Los 620 y 600 identificadores actuales cumplen. | Fuera de formato → CUARENTENA |
| R2.3 | 🟦 EQUIPO | Duplicado exacto (todas las columnas iguales): se conserva la **primera aparición** y las siguientes van a CUARENTENA con el motivo `DUPLICADO_EXACTO`. No se borran en silencio, para que el conteo cuadre (R1.4). | CUARENTENA (20 registros) |
| R2.4 | 🟦 EQUIPO | Si el mismo identificador aparece con contenido distinto (hoy 0 casos), **ambos** registros van a CUARENTENA con `ID_REPETIDO_CONFLICTO`, porque no hay criterio objetivo para elegir uno. | CUARENTENA |
| R2.5 | 🟦 EQUIPO | `id_transaccion` es la llave primaria de `transacciones_limpias`. Los dos prefijos (`POS-` y `WEB-`) no colisionan entre sí. | — |

## 3. Valores faltantes

**Evidencia (completitud):** tienda física 97.15 %, tienda online 98.53 %, catálogo 100 %.

| Columna | Faltantes | % | Prueba χ² de independencia (p-valor) | Clasificación |
|---|---|---|---|---|
| `ventas_tienda_fisica.id_cliente` | 127 | 20.48 % | vs sucursal p = 0.714 · vs método de pago p = 0.571 | MCAR |
| `ventas_tienda_fisica.monto_total_mxn` | 32 | 5.16 % | vs sucursal p = 0.479 · vs método de pago p = 0.569 | MCAR (y recuperable) |
| `ventas_online.customer_email` | 20 (15 `null` + 5 `""`) | 3.33 % | vs pasarela p = 0.779 · vs moneda p = 0.314 | MCAR |
| `ventas_online.shipping_address` | 77 | 12.83 % | vs estado p = 0.280 · vs pasarela p = 0.532 | MCAR |

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R3.1 | 🟥 PROF | Clasificar cada ausencia como MCAR o MAR. | — |
| R3.2 | 🟦 EQUIPO | **Criterio de clasificación:** prueba χ² entre el indicador "falta / no falta" y cada variable categórica observada. Con p ≥ 0.05 en todas, no hay evidencia de que la ausencia dependa de otra variable, por lo que se clasifica como **MCAR**. Con p < 0.05 en alguna, se clasificaría como **MAR** respecto a esa variable. *Limitación:* MNAR no puede probarse con los datos observados; se declara como supuesto. | — |
| R3.3 | 🟥 PROF | Las variables numéricas sesgadas se imputan con la **mediana**, no con la media. | CORREGIR |
| R3.4 | 🟦 EQUIPO | **Justificación de la mediana con datos reales:** en la tienda física, `monto_total_mxn` tiene media de **$16,586.74** contra mediana de **$3,506.37** (asimetría 14.08), y `cantidad` tiene media de 8.58 contra mediana de 2 (asimetría 9.38). Los valores de 99 y 500 unidades arrastran la media. La mediana es robusta a esos extremos. | — |
| R3.5 | 🟦 EQUIPO | **Dónde se aplica la mediana:** a `cantidad` cuando falte, calculada **por canal** (física y online) con los registros no duplicados y con cantidad > 0 (en la Fase 2 aún no existe el cruce con el catálogo). En los datos oficiales hay **0 casos**; la función se implementa y se comprueba con las pruebas de estrés. **No se usa la mediana para el monto**, porque el monto se puede reconstruir con exactitud (R6). | CORREGIR |
| R3.6 | 🟦 EQUIPO | Si falta `precio_unitario`, **no** se imputa con la mediana global, porque cada producto tiene su propio precio y una mediana inventaría un valor financiero. El registro va a CUARENTENA con `PRECIO_FALTANTE` (hoy 0 casos). | CUARENTENA |
| R3.7 | 🟥 PROF | Las categóricas se imputan con etiquetas controladas (la guía da como ejemplo `'ANONIMO'`). | CORREGIR |
| R3.8 | 🟦 EQUIPO | Etiquetas controladas: `id_cliente` → `ANONIMO` (127); `email_cliente` nulo o vacío → `SIN_CORREO` (20); `direccion_envio` → `SIN_DIRECCION` (77). La cadena vacía `""` se trata como nulo. | CORREGIR |
| R3.9 | 🟦 EQUIPO | Un campo que **no existe** en un canal (por ejemplo `direccion_envio` en la tienda física o `id_cliente` en la online) se guarda como `NULL` y no se imputa, porque no es un faltante sino un "no aplica". | — |

## 4. Cantidades negativas o cero

**Evidencia:** 11 registros de la tienda física con `cantidad ≤ 0` (seis con −1 y cinco con 0), por ejemplo `POS-2026-0216` (−1, monto −934.83) y `POS-2026-0035` (0, monto 0.00). En la online hay 0 casos (`units` ∈ {1, 2, 3}).

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R4.1 | 🟥 PROF | Eliminar únicamente los registros con valores imposibles (cantidades ≤ 0). | — |
| R4.2 | 🟦 EQUIPO | "Eliminar" se interpreta como **sacar de la tabla limpia y desviar a CUARENTENA** con `CANTIDAD_INVALIDA`, no como borrar sin rastro. Así se cumplen R4.1 y el principio de trazabilidad. | CUARENTENA (11) |
| R4.3 | 🟦 EQUIPO | Estos registros **no** participan en el cálculo de cuartiles, mediana, Min-Max ni cuantiles (base estadística, R5.6). | — |
| R4.4 | 🟦 EQUIPO | Una cantidad no entera o no numérica (por ejemplo `"dos"` o `2.5`) también va a CUARENTENA (`CANTIDAD_INVALIDA`), porque las ventas son por unidad. | CUARENTENA |

## 5. Tratamiento estadístico de outliers

| ID | Origen | Regla |
|---|---|---|
| R5.1 | 🟥 PROF | Calcular IQR = Q3 − Q1 con factor **1.5**. Límites: `LI = Q1 − 1.5·IQR` y `LS = Q3 + 1.5·IQR`. |
| R5.2 | 🟥 PROF | Aplicar Capping / Winsorizing: recortar a los límites **en lugar de eliminar filas**. |
| R5.3 | 🟦 EQUIPO | **Cantidad (por canal).** Tienda física: Q1 = 1, Q3 = 4, IQR = 3, LS = 8.5, con **13 outliers** (siete de 99 unidades y seis de 500, los "bots"). Como la cantidad es entera, el tope es `floor(8.5) = 8`. Tienda online: Q1 = 1, Q3 = 2, LS = 3.5, con **0 outliers**. |
| R5.4 | 🟦 EQUIPO | **Importe (unificado, ya en MXN).** El IQR del monto se calcula **después** de convertir USD a MXN, sobre `cantidad_cap × precio_unitario_mxn`. Valores de referencia: Q1 = 1,563.78, Q3 = 5,751.34, IQR = 4,187.56, **LS = 12,032.68**, con 80 registros por encima. LI es negativo (−4,717.56), así que no hay recorte inferior. *Sensibilidad:* el LS depende del redondeo de los precios convertidos: con `ROUND_HALF_UP` (R6.4) da 12,032.68, y con el `round()` de numpy, 12,032.63. Se acepta una diferencia de ±0.10 al comparar con el pipeline real. |
| R5.5 | 🟦 EQUIPO | **No destrucción:** el capping se guarda en **columnas analíticas nuevas** (`cantidad_cap`, `monto_total_mxn_cap`) con las banderas `es_outlier_cantidad` y `es_outlier_monto`. Las columnas `cantidad` y `monto_total_mxn` conservan el valor real reconstruido, y `monto_total_origen` conserva el dato crudo. Los KPI, Min-Max y la discretización usan las columnas `_cap`. |
| R5.6 | 🟦 EQUIPO | **Base estadística:** los cuartiles, la mediana, Min-Max y los cuantiles se calculan solo con registros **sin defecto estructural ya detectado** (no duplicados, cantidad > 0, producto en catálogo). Son 1,129 registros de referencia: 562 de la tienda física y 567 de la online. |
| R5.7 | 🟦 EQUIPO | No se usa Z-score (la guía lo permite como alternativa), porque supone una distribución aproximadamente normal y los datos tienen asimetría de 9 a 14. |

> Los valores de R5.3 y R5.4 son **de referencia**, calculados por el diagnóstico con estas mismas reglas. El pipeline real debe reproducirlos; si no coinciden, hay un error en alguna fase.

## 6. Reconstrucción de importes

**Evidencia:**
- Tienda física: 32 montos nulos, y **los 32** tienen cantidad y precio. Ningún monto presente es inconsistente con `cantidad × precio`. El precio coincide con el catálogo en el 100 % de los productos existentes.
- Tienda online: **12 registros** con `total_amount` exactamente **80 veces** `units × unit_price`. Por ejemplo, `WEB-00508`: 3 × 3,443.17 = 10,329.51, pero el archivo dice **826,360.80**. En esos 12 casos el precio unitario coincide con el catálogo y las unidades son normales (1 a 3). Son los "bots con compras gigantes" que menciona la guía.

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R6.1 | 🟥 PROF | Recalcular campos cuando la información exista en otras columnas: `monto_total = cantidad × precio_unitario`. | CORREGIR |
| R6.2 | 🟦 EQUIPO | Si el monto es nulo y existen cantidad y precio, se recalcula y se marca con `MONTO_RECALCULADO_NULO` (32 casos). | CORREGIR |
| R6.3 | 🟦 EQUIPO | Si `|monto − cantidad × precio| > 0.01`, el monto derivado se considera corrupto y se recalcula con `MONTO_RECALCULADO_INCONSISTENTE` (12 casos). El valor original queda en `monto_total_origen`. *Justificación:* las dos variables primarias (precio, verificado contra catálogo, y unidades) son coherentes, y solo la derivada está alterada por un factor constante. | CORREGIR |
| R6.4 | 🟦 EQUIPO | El redondeo financiero es a 2 decimales con `ROUND_HALF_UP` (módulo `decimal`), para evitar errores de punto flotante. | — |

## 7. Conversión de monedas

| ID | Origen | Regla |
|---|---|---|
| R7.1 | 🟥 PROF | Convertir importes en USD a MXN con la paridad oficial **$19.50**. |
| R7.2 | 🟦 EQUIPO | Se convierten **precio y monto** (`precio_unitario_mxn = precio × 19.50`, `monto_total_mxn = cantidad × precio_unitario_mxn`). Se guardan `moneda_original` y `tipo_cambio_aplicado` (19.50 o 1.00). |
| R7.3 | 🟦 EQUIPO | **Verificación:** los 180 registros USD con producto en catálogo, multiplicados por 19.50, coinciden con `precio_base_mxn` con una diferencia máxima de **$0.095**, que se explica por el redondeo del precio en USD. Ejemplo: `WEB-00002`, 169.59 USD × 19.50 = 3,307.01 contra 3,306.99 del catálogo. Se acepta una tolerancia de ±0.50 MXN. |
| R7.4 | 🟦 EQUIPO | Se conserva el precio convertido (no se sustituye por el del catálogo) para no alterar el dato de origen. |
| R7.5 | 🟦 EQUIPO | Una moneda distinta de `MXN` o `USD` va a CUARENTENA con `MONEDA_NO_SOPORTADA` (hoy 0 casos: 407 MXN y 193 USD). |

## 8. Fechas

**Evidencia:**
- Tienda física: tres formatos casi en partes iguales: `DD/MM/YYYY` (208), ISO `YYYY-MM-DD` (207) y `DD-MM-YYYY` (205). En 105 y 92 registros el primer campo es mayor que 12, lo que confirma que el **día va primero**. Rango real: 2026-09-01 a 2026-10-15.
- Tienda online: 392 ISO con hora (`2026-10-02T15:27:00`) y **208 Unix epoch** en segundos, guardados como entero en el JSON.

| ID | Origen | Regla |
|---|---|---|
| R8.1 | 🟥 PROF | Homologar todas las fechas a ISO `YYYY-MM-DD`. |
| R8.2 | 🟦 EQUIPO | Parseo **explícito por patrón** (regex + `strptime`). Está prohibido `pd.to_datetime(format="mixed", dayfirst=True)`: el diagnóstico demostró que interpreta mal **104 fechas** (por ejemplo, `2026-09-01` se convierte en el 9 de enero) y produce un rango falso de 2026-01-09 a 2026-12-10. |
| R8.3 | 🟦 EQUIPO | Epoch: se interpreta como UTC (estándar Unix) y se convierte a `America/Mexico_City` (hora del negocio en Colima, UTC−6) antes de tomar la fecha. Afecta a **49 registros**, cuya fecha cambia al día anterior. Por ejemplo, `WEB-00005` es 1789105020, que corresponde a 2026-09-11 05:37 UTC y a **2026-09-10** 23:37 en México. *Pendiente de confirmar con el docente (ver §13).* |
| R8.4 | 🟦 EQUIPO | Las fechas ISO con hora se consideran ya en hora local y se trunca la hora. |
| R8.5 | 🟦 EQUIPO | Una fecha que no se puede parsear, una fecha imposible (`31/02/2026`) o una fecha posterior a la fecha de ejecución va a CUARENTENA con `FECHA_INVALIDA`. Hoy 0 casos. |

## 9. Integridad referencial

**Evidencia:** el catálogo tiene 50 productos (`PROD-001` a `PROD-050`) sin duplicados. Hay **29** registros físicos (uno de ellos es además un duplicado exacto) con productos `PROD-9xx` inexistentes, **todos con precio 500.00**, y **33** registros online con `PROD-8xx`, con precios de 600.00 MXN o 30.77 USD. Los precios fijos refuerzan que son registros artificiales y no productos reales.

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R9.1 | 🟥 PROF | Cruzar (merge) contra el catálogo maestro y marcar las llaves huérfanas para desviarlas a cuarentena. | CUARENTENA |
| R9.2 | 🟦 EQUIPO | El cruce es un `LEFT JOIN` por `id_producto`, con la bandera `en_catalogo` (verdadero o falso). Si es falso, el motivo es `PRODUCTO_HUERFANO`. | CUARENTENA (29 + 33 = 62 apariciones del motivo) |
| R9.3 | 🟦 EQUIPO | El catálogo se toma como verdad. De él se agregan `nombre_producto` y `categoria` a la tabla limpia. | — |

## 10. Correos electrónicos

**Evidencia:** 552 correos con el patrón `usuario_N@gmail.com`; **28 malformados** (`usuario@@gmail..com` 11, `sin_arroba_dominio.org` 9, `correo_invalido.com` 8); 20 faltantes (15 `null` y 5 `""`).

| ID | Origen | Regla | Acción |
|---|---|---|---|
| R10.1 | 🟥 PROF (reto del dataset) | La guía señala los "correos malformados" como reto del Grupo 1. | — |
| R10.2 | 🟦 EQUIPO | Validación con `@field_validator` y la regex `^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$`. Si no cumple, el motivo es `EMAIL_MALFORMADO`. | CUARENTENA (28) |
| R10.3 | 🟦 EQUIPO | Un correo faltante **no** es malformado: se imputa `SIN_CORREO` (R3.8), que el validador acepta. *Justificación:* la ausencia es MCAR y la venta puede ser legítima; un correo con texto inválido, en cambio, es un dato corrupto. | CORREGIR (20) |
| R10.4 | 🟦 EQUIPO | Antes de validar, el correo se normaliza con `strip()` y minúsculas. | CONSERVAR |

## 11. Homologación de categóricas

| Columna | Valores crudos | Regla [EQUIPO] |
|---|---|---|
| `metodo_pago` (física) | `Efectivo` 104, `efectivo` 89, `TRANSFERENCIA` 124, `Vales` 113, `Tarjeta Crédito` 107, `Tarjeta Débito` 83 | `strip().upper()` → 5 categorías (`EFECTIVO` 193) |
| `order_status` (online) | `completado` 98, `COMPLETADO` 94, `CANCELADO` 119, `DEVUELTO` 111, `PAGADO` 93, `PENDIENTE` 85 | `strip().upper()` → 5 categorías (`COMPLETADO` 192) |
| `payment_gateway` (online) | `OXXO Pay`, `PayPal`, `Stripe`, `MercadoPago` | Se mapea a `metodo_pago` en mayúsculas |
| `sucursal` (física) | 4 sucursales | Se mapea a `punto_venta`; la online usa `TIENDA_ONLINE` |

R11.1 🟦 EQUIPO: los pedidos `CANCELADO` (119) y `DEVUELTO` (111) **no son errores de datos**. Se conservan en la tabla limpia con su `estado_pedido`, y la capa de reportes decide si los cuenta como venta.

## 12. Escalamiento y discretización

| ID | Origen | Regla |
|---|---|---|
| R12.1 | 🟥 PROF | Normalizar la variable numérica con Min-Max a [0, 1]: `x' = (x − min) / (max − min)`. |
| R12.2 | 🟦 EQUIPO | La variable escalada es `monto_total_mxn_cap`. Se usa la versión con capping para que un bot no comprima a todos los demás cerca de 0. Valores de referencia: min = 332.67, max = 12,032.68. |
| R12.3 | 🟥 PROF | Discretizar el importe en 3 segmentos (Bajo, Medio, Alto), por cuantiles o por reglas justificadas. |
| R12.4 | 🟦 EQUIPO | Se usan **terciles** (`pd.qcut(q=3)`) sobre la base estadística. Referencia: Bajo ≤ $2,069.07 < Medio ≤ $4,183.67 < Alto. *Justificación:* el negocio no definió umbrales de importe, y los terciles producen grupos de tamaño comparable, lo que evita un segmento vacío. |

## 13. Zona de cuarentena

| ID | Origen | Regla |
|---|---|---|
| R13.1 | 🟥 PROF | Los registros que violan el esquema van a la lista de cuarentena con la columna `motivo_rechazo_cuarentena`, y se persisten en la tabla `cuarentena_errores`. |
| R13.2 | 🟦 EQUIPO | Se registran **todos** los motivos de un registro, no solo el primero, porque Pydantic acumula los errores. Formato: `CODIGO: mensaje legible`, separados por ` \| `. |
| R13.3 | 🟦 EQUIPO | Se guarda el registro **crudo completo** en JSON (`registro_original`), junto con `origen`, `id_registro`, `etapa_deteccion`, `lote_id` y `fecha_cuarentena`, para poder auditarlo y reprocesarlo. |
| R13.4 | 🟦 EQUIPO | Una excepción inesperada en un registro (no `ValidationError`) también se captura **por registro** y va a cuarentena con `ERROR_INESPERADO`; el lote continúa. |

**Catálogo de códigos de rechazo [EQUIPO]:**

| Código | Origen de la regla | Casos esperados (datos oficiales) |
|---|---|---|
| `DUPLICADO_EXACTO` | R2.3 | 20 |
| `ID_REPETIDO_CONFLICTO` | R2.4 | 0 |
| `ID_FORMATO_INVALIDO` | R2.2 | 0 |
| `CANTIDAD_INVALIDA` | R4 | 11 |
| `PRECIO_FALTANTE` / `PRECIO_INVALIDO` | R3.6 | 0 |
| `PRODUCTO_HUERFANO` | R9 | 62 (29 físicos, uno de ellos también duplicado, + 33 online) |
| `EMAIL_MALFORMADO` | R10 | 28 |
| `FECHA_INVALIDA` | R8.5 | 0 |
| `MONEDA_NO_SOPORTADA` | R7.5 | 0 |
| `ERROR_INESPERADO` | R13.4 | 0 |

**Resultado esperado:** 116 registros en cuarentena (58 de la tienda física y 58 de la online; 5 de ellos tienen más de un motivo) y **1,104** en `transacciones_limpias` (562 de la física y 542 de la online). En total, 620 + 600 = 1,220 = 1,104 + 116.

## 14. Resumen: conservar, corregir o rechazar

| Situación | Acción | Casos |
|---|---|---|
| Fecha en formato distinto de ISO | CONSERVAR (homologar) | 413 físicas + 600 online |
| Categórica con mayúsculas distintas | CONSERVAR (homologar) | 89 `efectivo`, 98 `completado` |
| Precio y monto en USD | CORREGIR (convertir, guardar original) | 193 |
| `id_cliente` faltante | CORREGIR (`ANONIMO`) | 127 |
| Correo faltante | CORREGIR (`SIN_CORREO`) | 20 |
| Dirección faltante | CORREGIR (`SIN_DIRECCION`) | 77 |
| Monto nulo recalculable | CORREGIR (recalcular) | 32 |
| Total inflado ×80 | CORREGIR (recalcular, guardar original) | 12 |
| Cantidad atípica (99 y 500) | CORREGIR (capping a 8 en `cantidad_cap`) | 13 |
| Monto atípico (> LS) | CORREGIR (capping en `monto_total_mxn_cap`) | 80 (referencia) |
| Duplicado exacto | CUARENTENA | 20 |
| Cantidad ≤ 0 | CUARENTENA | 11 |
| Producto huérfano | CUARENTENA | 62 (29 + 33) |
| Correo malformado | CUARENTENA | 28 |

## 15. Ambigüedades de los lineamientos y decisión propuesta

| # | Ambigüedad | Decisión del equipo | ¿Consultar al docente? |
|---|---|---|---|
| A1 | La sección 4 dice "Las 6 Fases" pero enumera 7. | Se trabaja con las 7 fases listadas. | No |
| A2 | La Fase 3 (outliers) va antes que la Fase 4 (conversión de moneda). Aplicar IQR a montos con USD y MXN mezclados da un límite incorrecto: 7,659.30 sin convertir contra 8,100.74 convertido. | Se ejecuta F1 → F2 → F4 → F3 → F5 → F6 → F7. El IQR de cantidad no depende de la moneda; el del monto se calcula en MXN. | Sí, informar |
| A3 | "Eliminar registros imposibles" frente a "cuarentena con trazabilidad". | Se desvían a cuarentena (R4.2). | No |
| A4 | El límite IQR de la cantidad (8.5) no es entero. | Tope = `floor(LS)` = 8. | No |
| A5 | El capping altera valores financieros. | Columnas `_cap` separadas (R5.5). | No |
| A6 | La guía no dice qué variable va a Min-Max. | `monto_total_mxn_cap` (R12.2). | No |
| A7 | No hay umbrales de negocio para Bajo, Medio y Alto. | Terciles (R12.4). | No |
| A8 | No se indica la zona horaria del epoch. | UTC → America/Mexico_City (49 fechas cambian). | **Sí** |
| A9 | Los totales inflados ×80 pueden recalcularse o rechazarse. | Recalcular con bandera (R6.3). Alternativa: cuarentena con `MONTO_INCONSISTENTE`. | **Sí** |
| A10 | No se dice si los pedidos cancelados o devueltos son ventas válidas. | Se conservan con su estado (R11.1). | Opcional |

---

## 16. Firmas de conformidad

Los integrantes declaramos que revisamos estas reglas, que las cifras provienen de la ejecución real de `diagnostico/diagnostico_inicial.py` sobre los archivos oficiales sin modificar, y que cada regla [EQUIPO] tiene su justificación técnica.

| Rol | Integrante | Firma | Fecha |
|---|---|---|---|
| Ingeniero/a 1 · Calidad, Nulos y Outliers | Leslie ______________________ | ____________ | ____/____/2026 |
| Ingeniero/a 2 · Transformación e Integración | Yerik ______________________ | ____________ | ____/____/2026 |
| Ingeniero/a 3 · Validación, Resiliencia y BD | Nono ______________________ | ____________ | ____/____/2026 |
