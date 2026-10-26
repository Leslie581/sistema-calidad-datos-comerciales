# Resumen técnico · Etapa 3: Ingeniero 3 (Nono) · Validación, Resiliencia y Persistencia

**Rama:** `feat/nono-validacion` (sin commits todavía) · **Ejecución verificada:** 2026-10-25
**Entorno del proyecto (`.venv`):** Python 3.13.15 · pandas 3.1.0 · numpy 2.5.4 · Pydantic 2.14.1 · SQLite 3.50.4 (la batería también pasa con pandas 2.3.3 y Pydantic 2.13.5)
**Fuentes:** `docs/GUIA_LINEAMIENTOS_PROYECTO_ALUMNOS.pdf` (leído; fases 6 y 7, criterios 4–6 de la rúbrica) · `REGLAS_DE_NEGOCIO.md` (R1, R2, R8–R13) · `GUIA_INGENIERO_3_NONO.md`

---

## 1. Qué se desarrolló

| Entregable | Estado | Cómo se comprobó |
|---|---|---|
| Modelo Pydantic 2 `TransaccionLimpia` con 20 `@field_validator` | ✅ | 96 pruebas unitarias (`tests/test_validacion.py`) |
| Segregación registro por registro: conformes vs. cuarentena, con todos los motivos | ✅ | cuarentena de 116 registros; 15 con más de un motivo, contados una vez |
| Manejo explícito de defectos de fases previas (duplicado, conflicto de ID, huérfano, alertas) | ✅ | `etapa_deteccion` = `FASE_PREVIA` / `PYDANTIC` / `ERROR_INESPERADO` |
| SQLite: `transacciones_limpias`, `cuarentena_errores` (+ `catalogo_productos`, `ejecuciones`) | ✅ | 1,104 + 116 filas reales; `integrity_check = ok`, `foreign_key_check = []` |
| Carga transaccional con `BEGIN`/`commit()`/`rollback()` e idempotencia por snapshot | ✅ | 35 pruebas de persistencia, incluidos rollback y recarga repetida |
| Orquestador `python -m src.pipeline` (las 7 fases oficiales) | ✅ | ejecutado sobre los 3 datasets oficiales (0.25 s) |
| Pruebas de resiliencia y estrés | ✅ | 48 escenarios (38 por registro + 10 globales), 54 pruebas |
| Evidencias, logs y gráficos | ✅ archivos · ⏳ capturas | `salidas/etapa_nono/` · `evidencias/GUIA_CAPTURAS_NONO.md` |
| Frontend | ⛔ fuera de alcance | no se tocó |

## 2. Archivos

**Creados:**
- `src/validacion/esquemas.py` (modelo) · `src/validacion/cuarentena.py` (segregación)
- `src/persistencia/esquema.sql` (DDL) · `src/persistencia/carga.py` (carga transaccional)
- `src/pipeline.py` (orquestador y CLI) · `src/reporte_final.py` (evidencias)
- `datos/estres/generar_estres.py` (escenarios de estrés; copia registros reales, no toca los originales)
- `tests/test_validacion.py`, `tests/test_persistencia.py`, `tests/test_estres.py`, `tests/test_pipeline.py`, `tests/ayudas_nono.py`
- `docs/RESUMEN_AVANCE_NONO.md`, `evidencias/GUIA_CAPTURAS_NONO.md`, `salidas/etapa_nono/`

**Modificados (compartidos, solo adiciones):**
- `src/config.py`: `RUTA_SALIDAS_NONO`, `RUTA_BD`, `ESTADOS_PEDIDO_VALIDOS` (R11).
- `src/contratos.py`: códigos de rechazo `RECH_*` y `CODIGOS_RECHAZO_PROPUESTOS`.
- `requirements.txt`: `pydantic>=2.5`. · `README.md`: instrucciones para Windows PowerShell.

**Módulos de Leslie y Yerik: no se modificaron** (`src/calidad/`, `src/integracion/`, `src/extraccion.py`). No hizo falta: sus salidas son compatibles. Sus 152 pruebas pasan sin cambios.

## 3. Arquitectura

```
extraer → perfilar → homologar → limpiar → integrar → IQR/capping → Min-Max y terciles → VALIDAR → CARGAR → reporte
 Yerik     Leslie     Yerik       Leslie     Yerik       Leslie           Yerik              Nono     Nono     Nono
```

- **Orden y decisión técnica:** la normalización de fechas (7.º paso pedido) se ejecuta dentro de la integración (paso 5), antes del IQR. No lo afecta (Guía de Yerik §4) y el IQR sí necesita el importe en MXN y el cruce con el catálogo (ambigüedad A2). Las siete fases oficiales se cumplen todas.
- **Errores por registro (recuperables):** van a cuarentena y el lote continúa. **Errores globales:** archivo ilegible o faltante (`ErrorExtraccion`), contrato roto (`ErrorContrato`), huella SHA-256 distinta (`ErrorIntegridad`), conservación violada (`ErrorConservacion`), fallo de BD (`ErrorCarga`) → estado `FALLIDO` con etapa, tipo y mensaje, registrado en log, bitácora y tabla `ejecuciones`; la BD conserva la última carga válida. Cualquier otra excepción se clasifica como **imprevista**: se guarda el traceback en el log y la bitácora, sin imprimirlo en consola.
- **Etapas informativas:** el perfilado y el MCAR/MAR no detienen el ETL si fallan, pero el fallo queda en `advertencias` (visible, no oculto). Con los datos oficiales: 0 advertencias.
- **Contrato roto:** si al modelo le falta una columna, `validar_lote` lanza `ErrorContrato` en lugar de guardar `NULL` en silencio (se encontró un caso real durante el desarrollo, ver §10).

## 4. Reglas Pydantic

`strict=True` (un texto no se convierte en número), `extra="ignore"`, errores acumulados por registro. Cada mensaje empieza con su código. **[EQUIPO]** = documentado en `REGLAS_DE_NEGOCIO.md`; **[PROPUESTA]** = añadida en esta etapa, **pendiente de aprobación**.

| Campo(s) | Código | Regla | Origen |
|---|---|---|---|
| `es_duplicado` | `DUPLICADO_EXACTO` | repite una fila anterior del mismo canal | [EQUIPO] R2.3 |
| `es_id_conflicto` | `ID_REPETIDO_CONFLICTO` | mismo ID con contenido distinto | [EQUIPO] R2.4 |
| `id_transaccion` | `ID_FORMATO_INVALIDO` | `POS-AAAA-NNNN` o `WEB-NNNNN` | [EQUIPO] R2.2 |
| `id_transaccion` | `ID_ORIGEN_INCONSISTENTE` | el prefijo debe corresponder al canal | [PROPUESTA] |
| `fecha_venta` | `FECHA_INVALIDA` | ISO `YYYY-MM-DD`, existe en el calendario, no posterior a la ejecución | [EQUIPO] R8.1, R8.5 |
| `en_catalogo`, `nombre_producto`, `categoria` | `PRODUCTO_HUERFANO` | el producto existe en el catálogo | [EQUIPO] R9 |
| `cantidad`, `cantidad_cap` | `CANTIDAD_INVALIDA` | número entero > 0 | [EQUIPO] R4 |
| `moneda_original` | `MONEDA_NO_SOPORTADA` | MXN o USD | [EQUIPO] R7.5 |
| `tipo_cambio_aplicado` | `TIPO_CAMBIO_INCONSISTENTE` | 1.0 para MXN, 19.5 para USD | [PROPUESTA] |
| `precio_unitario_mxn` | `PRECIO_FALTANTE` / `PRECIO_INVALIDO` | presente y > 0 (distingue la alerta de homologación) | [EQUIPO] R3.6 |
| `monto_total_mxn` | `MONTO_INVALIDO` / `MONTO_INCONSISTENTE` | > 0 y = cantidad × precio (±0.01) | [EQUIPO] R6.3 |
| `monto_total_mxn_cap` | `MONTO_INVALIDO` | > 0 | [EQUIPO] R6 |
| `monto_minmax` | `ESCALA_FUERA_DE_RANGO` | ∈ [0, 1] | [EQUIPO] R12.1 |
| `segmento_importe` y tipos | `TIPO_INVALIDO` | Bajo/Medio/Alto; cualquier tipo nativo incorrecto o campo requerido ausente | guía de Nono |
| `email_cliente` (ONLINE) | `EMAIL_MALFORMADO` / `CAMPO_OBLIGATORIO_FALTANTE` | regex R10.2; `SIN_CORREO` es válido | [EQUIPO] R10 / [PROPUESTA] la ausencia |
| `id_cliente` (FISICA), `direccion_envio` (ONLINE), `metodo_pago`, `punto_venta`, `registro_original`, `id_fila_origen` | `CAMPO_OBLIGATORIO_FALTANTE` | obligatorio según el canal (R3.9) | [PROPUESTA] como rechazo |
| `estado_pedido` | `ESTADO_INVALIDO` | ONLINE ∈ {COMPLETADO, PAGADO, PENDIENTE, CANCELADO, DEVUELTO}; FISICA sin estado | [EQUIPO] R11 / [PROPUESTA] el rechazo |
| cualquier excepción distinta | `ERROR_INESPERADO` | se aísla por registro | [EQUIPO] R13.4 |

**Original vs. tratado:** el modelo valida el valor tratado y **conserva** el original en la fila: `cantidad_origen → cantidad → cantidad_cap`; `precio_unitario_original → precio_unitario_mxn`; `monto_total_origen → monto_total_mxn → monto_cantidad_cap_mxn → monto_total_mxn_cap`; `fecha_cruda → fecha_venta`; `registro_original`. El capping nunca borra evidencia (ej. `POS-2026-0031`: 500 → 500 → 8).

## 5. Funcionamiento de la cuarentena

1. `validar_lote` recorre cada fila con `try … except ValidationError` **dentro del ciclo**.
2. Reúne los motivos de las fases previas (`errores_fases_previas`) y los de Pydantic. Si ambos detectan el mismo código se cuenta una vez.
3. Sin motivos → fila para `transacciones_limpias`. Con motivos → un solo registro de cuarentena con: `id_registro`, `origen`, `id_fila_origen`, `etapa_deteccion`, `codigos_error`, `num_motivos`, **`motivo_rechazo_cuarentena`** (`CODIGO: mensaje | …`), `detalle_error` (JSON por motivo: campo, código, mensaje, etapa, valor), `registro_original`, `fecha_cuarentena`, `lote_id` (identifica la ejecución).
4. Comprobación de conservación: cada `(origen, id_fila_origen)` de entrada aparece exactamente una vez entre válidos y cuarentena; si no, `ErrorConservacion` detiene la ejecución (R1.4).

## 6. Estructura de SQLite

Archivo: **`salidas/etapa_nono/calidad_comercial.db`** (abrir con DB Browser for SQLite). DDL completo: `src/persistencia/esquema.sql`.

| Tabla | Filas | Clave y restricciones principales |
|---|---|---|
| `ejecuciones` | 1 | PK `lote_id`; estado `COMPLETADO`/`FALLIDO`; `CHECK entrada = limpias + cuarentena` (R1.4); huellas SHA-256 y entorno en JSON |
| `catalogo_productos` | 50 | PK `id_producto` |
| `transacciones_limpias` | 1,104 | PK `id_transaccion` (GLOB de formato) · `UNIQUE(origen, id_fila_origen)` · FK `id_producto → catalogo_productos` y `lote_id → ejecuciones` · `CHECK` de cantidad > 0, moneda `MXN`, fecha ISO real (`date(x) = x`), `monto_minmax ∈ [0,1]`, segmento, estado por canal |
| `cuarentena_errores` | 116 | PK `id_error` · `UNIQUE(lote_id, origen, id_fila_origen)` · `CHECK` de motivo no vacío · FK `lote_id → ejecuciones` |

Idempotencia (documentada en `carga.py`): **snapshot por ejecución**. Dentro de una sola transacción se borra y se reinserta; correr el pipeline N veces deja las mismas filas y suma una fila al historial `ejecuciones`. `--no-reemplazar` agrega el lote, y una transacción ya existente provoca rollback. Todas las inserciones son parametrizadas (`?`), y la conexión activa `PRAGMA foreign_keys`.

## 7. Resultados reales del pipeline (datasets oficiales)

| | Física | Online | Total |
|---|---|---|---|
| Entrada | 620 | 600 | **1,220** |
| `transacciones_limpias` | 562 | 542 | **1,104** |
| `cuarentena_errores` | 58 | 58 | **116** |

| Código | Registros que lo contienen | Combinaciones (registros únicos) |
|---|---|---|
| `PRODUCTO_HUERFANO` | 62 (29 física + 33 online) | solo: 57 · con correo: 3 · con duplicado: 1 · con cantidad/monto: 1 |
| `EMAIL_MALFORMADO` | 28 | solo: 25 · con huérfano: 3 |
| `DUPLICADO_EXACTO` | 20 | solo: 19 · con huérfano: 1 |
| `CANTIDAD_INVALIDA` | 11 | siempre con `MONTO_INVALIDO` (10 solos + 1 con huérfano) |
| `MONTO_INVALIDO` | 11 | ídem |

Registros con más de un motivo: 15. Por etapa de detección: `FASE_PREVIA` 77 · `PYDANTIC` 35 · ambas 4. Errores inesperados: 0. Advertencias: 0.

Verificación sobre las 1,104 válidas (desde la BD): fechas ISO reales 1,104; rango 2026-09-01 → 2026-10-16; `moneda = 'MXN'` 1,104 (930 originales MXN + 174 USD); importes incoherentes con cantidad × precio: 0; `monto_minmax` ∈ [0.0, 1.0] y recalculado coincide (0 diferencias); segmentos recalculados coinciden (0 diferencias); Alto 372 · Bajo 370 · Medio 362; cantidad con capping distinta de la original: 13; importe con capping distinto del convertido: 86. **Los originales siguen intactos** (SHA-256 verificado en la ejecución y en una prueba).

## 8. Pruebas realizadas

`python -m pytest`: **357 pasadas** (`.venv`, pandas 3.1.0) y 357 con pandas 2.3.3. Desglose: Leslie 78 · Yerik 74 · **Nono 205**.

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `test_validacion.py` | 96 | un caso por validador y por canal, tipos estrictos, varias causas contadas una vez, error inesperado aislado y registrado, conservación violada, columnas faltantes |
| `test_persistencia.py` | 35 | commit, rollback (falla a mitad, PK repetida, error no SQLite), conexión usable tras rollback, recarga idempotente, modo agregar, 18 `CHECK`/FK rechazados directamente en SQL (con prueba de control), cuarentena sin motivo, inyección SQL |
| `test_estres.py` | 54 | los 48 escenarios de `datos/estres/generar_estres.py` + invariantes (conteo, motivo no vacío, fechas ISO, la tabla sobrevive a la inyección SQL) |
| `test_pipeline.py` | 20 | conteos oficiales, conservación por fila, motivos, ejemplos de la guía, calidad de las válidas, SHA-256, idempotencia, evidencias, `python -m src.pipeline` por subproceso, fallos globales sin traceback |

Escenarios de estrés (`salidas/etapa_nono/estres/resultados_estres.csv`, **48/48 ok**): cantidad texto/decimal/0/negativa, precio negativo/texto/nulo, fechas imposible/futura/'ayer'/epoch en ms, moneda EUR, producto nulo/inexistente, correos malformados, IDs inválidos e inyección SQL, ID en conflicto, duplicado, campo ausente/extra, tipos incorrectos (lista, objeto), 1e308, emoji, estado fuera de catálogo; globales: JSON vacío, JSON truncado, archivo inexistente, columnas faltantes, JSON no-lista, falla de persistencia con rollback, volumen 12,200 registros (reales ×10, barajados: 1.4 s, 1,104 limpias + 11,096 cuarentena, conteo conservado), huella SHA-256 alterada, ejecución repetida, excepción imprevista en una etapa.

## 9. Diferencias con los resultados esperados

Los conteos **no se forzaron**; resultaron de aplicar las reglas y coinciden con la referencia (1,104 / 116; 562 / 542; 58 / 58; 20 / 11 / 62 / 28). Una sola diferencia, explicada:

| Métrica | Referencia | Obtenido | Explicación |
|---|---|---|---|
| Registros con más de un motivo | 16 (= 5 «por regla» + 11 «cantidad + monto») | **15** | `POS-2026-0493` está en ambos grupos (huérfano y cantidad −1): una transacción se cuenta una vez → 5 + 11 − 1 = 15. Detalle en `09_comparacion_estimaciones.csv`. |

`MONTO_INVALIDO` aparece como código propio (11); la referencia lo cuenta junto con `CANTIDAD_INVALIDA`.

## 10. Limitaciones y decisiones técnicas

| # | Decisión / hallazgo | Detalle |
|---|---|---|
| D-N1 | **Reglas propuestas pendientes de aprobación** | `ID_ORIGEN_INCONSISTENTE`, `CAMPO_OBLIGATORIO_FALTANTE`, `ESTADO_INVALIDO` (como rechazo), `TIPO_CAMBIO_INCONSISTENTE`. Con los datos oficiales no rechazan ningún registro; solo actúan con datos corruptos |
| D-N2 | Registros con cantidad ≤ 0 llegan con `monto_minmax` acotado (decisión D-Y1 de Yerik) | Se rechazan solo por sus motivos reales |
| D-N3 | **Hallazgo corregido durante el desarrollo** | El primer diseño no copiaba `precio_unitario` a `precio_unitario_original`: se habría guardado `NULL` en las 1,104 filas sin ningún error. Lo detectó una prueba de la fila `WEB-00002`; ahora hay un alias, una comprobación de columnas del contrato (`ErrorContrato`) y pruebas de regresión |
| D-N4 | Snapshot en lugar de acumular | La BD refleja la última ejecución completada; el historial queda en `ejecuciones`. Alternativa: acumular lotes (requeriría otra llave) |
| D-N5 | **`*.db` y `*.log` están en `.gitignore`** | La BD y los logs se regeneran con un comando, pero **no viajan en Git**. Si la entrega exige el `.db` en el repositorio, hay que decidirlo (`git add -f` o cambiar el `.gitignore`) |
| D-N6 | Fecha límite = día de ejecución | R8.5; en pruebas se fija con `hoy=` para no depender del reloj |
| D-N7 | Epoch en ms (13 dígitos) | no se acepta (decisión D-Y7) → `FECHA_INVALIDA` |
| D-N8 | Advertencia numérica con `total_amount = 1e308` | `RuntimeWarning: overflow` en `recalcular_montos` de Leslie (el factor ×80 de la bitácora queda en `inf`). No afecta resultados (el monto se recalcula y el registro es válido); no se tocó su módulo |
| D-N9 | Perfilado y MCAR/MAR no detienen el ETL | Su fallo se reporta como advertencia visible |
| D-N10 | SHA-256 solo con las rutas oficiales | Con rutas alternas (`--fisica/--online/--catalogo`, usadas para pruebas con datos corruptos) se omite, salvo `verificar_huellas=True` |
| D-N11 | Una sola ejecución concurrente | `BEGIN IMMEDIATE` protege la escritura, pero no se probó con dos procesos a la vez |

No se verificó: ejecución en PostgreSQL, rendimiento con volúmenes mayores a 12,200 registros, ni las capturas de pantalla (las toma el equipo).

## 11. Cómo ejecutar el sistema (Windows PowerShell)

```powershell
cd "C:\Users\Leslie Valadez\Documents\Proyectos\sistema-calidad-datos-comerciales"
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.pipeline                 # ETL completo → salidas\etapa_nono\calidad_comercial.db
python -m pytest                       # 357 pruebas
python datos\estres\generar_estres.py  # 48 escenarios → salidas\etapa_nono\estres\resultados_estres.csv
```

Opciones: `--bd RUTA` · `--salida CARPETA` · `--no-reemplazar` · `--catalogo/--fisica/--online RUTA` (archivos alternos; la ejecución falla de forma controlada si están corruptos). Código de salida: 0 completado, 1 fallido.

## 12. Qué queda pendiente para cerrar el proyecto

1. Aprobar o descartar las reglas propuestas (D-N1) y decidir si el `.db` va en el repositorio (D-N5).
2. Decisiones heredadas: zona horaria del epoch (A8), recalcular o rechazar los 12 totales ×80 (A9), IQR antes/después de convertir (A2).
3. Tomar las capturas (`evidencias/GUIA_CAPTURAS_NONO.md`) y armar el reporte PDF y la defensa oral.
4. Comparación «después» de Leslie sobre la tabla final de SQLite (pendiente desde su etapa; ahora es posible).
5. Revisar la rama, hacer commit y merge a `main` por acuerdo del equipo. Frontend, si se decide.
