# Resumen técnico · Etapa 2: Ingeniero 2 (Yerik) · Integración y Transformación

**Rama:** `feat/yerik-integracion` (creada desde `main`; sin commits todavía)
**Ejecución verificada:** 2026-10-25 · entorno del proyecto `.venv`: Python 3.13.15 · pandas 3.1.0 · numpy 2.5.4 (las 150 pruebas también pasan con pandas 2.3.3 / Python 3.13)
**Reglas:** `docs/avance01/REGLAS_DE_NEGOCIO.md` (R6, R7, R8, R9, R12) · **Guía:** `docs/avance01/GUIA_INGENIERO_2_YERIK.md`

---

## 1. Estado

| Actividad | Estado | Cómo se comprobó |
|---|---|---|
| Extracción robusta de CSV y JSON | ✅ | BOM UTF-8, archivo vacío/inexistente/ilegible, JSON que no es lista, catálogo con IDs repetidos → `ErrorExtraccion` (5 pruebas nuevas) |
| Homologación de columnas | ✅ (ya existía; sin cambios) | 18 columnas del contrato; 620 + 600 = 1,220 filas; categorías 6 → 5 |
| Fechas a `YYYY-MM-DD` (5 formatos, epoch con zona) | ✅ nuevo `fechas.py` | 0 fechas no interpretables en las 1,220; 8 formatos válidos y 11 inválidos parametrizados |
| USD → MXN a 19.50 | ✅ reforzado | 193 conversiones; 180 vs catálogo con dif. máx. 0.10; aritmética en `Decimal` |
| Unificación física + digital | ✅ | `integrar()` mantiene 1,220 filas |
| Cruce con catálogo y huérfanos | ✅ reforzado | 29 física + 33 online `en_catalogo = False`; `validate="many_to_one"` probado |
| Min-Max en [0, 1] | ✅ nuevo `transformacion.py` | min 332.67, max 12,032.68; extremos de la base = 0.0 y 1.0; 0 valores fuera de [0, 1] |
| Discretización Bajo/Medio/Alto | ✅ | cortes 2,069.07 / 4,183.67; base 380 / 374 / 375 |
| Trazabilidad y registros originales | ✅ | `test_integrar_no_altera_valores_originales`, `cantidad_origen` y `monto_cantidad_cap_mxn` intactos |
| Pruebas | ✅ **150 / 150** (78 de Leslie + 72 nuevas) | `salidas/etapa_yerik/pytest_completo.txt`, `pytest_integracion.txt` |
| Evidencias y gráficos | ✅ archivos · ⏳ capturas | `salidas/etapa_yerik/`; guía en `evidencias/GUIA_CAPTURAS_YERIK.md` |
| Contrato para Nono | ✅ | `docs/CONTRATO_YERIK_A_NONO.md` |
| Etapa 3 de Nono, frontend | ⛔ fuera de alcance | no se tocó |

## 2. Archivos

**Nuevos:** `src/integracion/fechas.py`, `src/integracion/transformacion.py`, `tests/test_integracion.py`, `scripts/ejecutar_etapa_yerik.py`, `docs/CONTRATO_YERIK_A_NONO.md`, `docs/RESUMEN_AVANCE_YERIK.md`, `evidencias/GUIA_CAPTURAS_YERIK.md`, `salidas/etapa_yerik/` (evidencias).

**Modificados (módulos de Yerik):**
- `src/extraccion.py`: `utf-8-sig` (tolera BOM), error controlado para catálogo ilegible/vacío, IDs del catálogo normalizados (strip + mayúsculas) igual que los de ventas.
- `src/integracion/moneda.py`: multiplicaciones en `Decimal` (antes en `float`) y `paridad` parametrizable.
- `src/integracion/catalogo.py`: IDs normalizados, `huerfanos()`, alerta informativa `PRECIO_DIFIERE_CATALOGO` (> 0.50 MXN).
- `src/integracion/__init__.py`: `integrar()` (F4 = fechas → moneda → catálogo).

**Modificado, compartido (solo adiciones):** `src/contratos.py` (códigos y listas de columnas nuevas; detalle en el contrato para Nono).

**Módulos de Leslie:** `src/calidad/*` y `scripts/ejecutar_etapa_leslie.py` **no se modificaron**; tampoco se re-ejecutó su script, para no reescribir sus evidencias (`salidas/etapa_leslie/`). Sus 78 pruebas pasan sin cambios.

## 3. Decisiones técnicas

| # | Decisión | Por qué | Alternativa |
|---|---|---|---|
| D-Y1 | Los registros fuera de la base (11 con cantidad ≤ 0, duplicados, huérfanos) se escalan con min/max de la base y se **acotan a [0, 1]**; `minmax_recortado` marca los 11 casos acotados | Atiende D5 de Leslie. Evita que Nono rechace por un 2.º motivo artificial (`ESCALA_FUERA_DE_RANGO`) además del real | Dejar `None` (rechazaría además por `TIPO_INVALIDO`) |
| D-Y2 | Población de min/max y terciles = `es_base_estadistica` (1,129) | Los duplicados repiten ventas y los registros de cuarentena no son ventas reales | Todas las filas válidas (min/max y cortes cambiarían) |
| D-Y3 | Si max = min (importes iguales o 1 solo registro): `monto_minmax = 0.0` y `constante: True` en el resumen. Base vacía: todo `None` | Evita la división por cero sin inventar una escala | Lanzar error |
| D-Y4 | Terciles asignados con comparaciones (≤ c1 Bajo, ≤ c2 Medio, resto Alto), no con `pd.cut` | `pd.cut` falla si los cortes se repiten | — |
| D-Y5 | Fecha interpretada por patrón estricto + `strptime`; **sin** `pd.to_datetime` (una prueba revisa el AST de `src/`) | R8.2 | — |
| D-Y6 | Epoch: UTC → `America/Mexico_City` antes de tomar la fecha; fecha sin hora y ISO con hora se toman como hora local (R8.3/R8.4). Si falta `tzdata` en Windows, se usa UTC−6 fijo (correcto para estas fechas) | Documentado en `fechas.py`; `zona_epoch=ZONA_UTC` lo cambia | UTC (49 fechas distintas) |
| D-Y7 | Epoch en milisegundos (13 dígitos) **no se acepta** → `None` + `FECHA_NO_INTERPRETABLE` | No hay casos en los datos; adivinar la unidad sería inventar | Aceptar ms |
| D-Y8 | La regla «fecha posterior a la ejecución» (R8.5) queda para el validador de Nono | Es una regla de validación, no de transformación | — |
| D-Y9 | Cambios en `contratos.py` solo de adición | Archivo compartido | — |

## 4. Resultados reales (ejecución de `scripts/ejecutar_etapa_yerik.py`)

| Métrica | Resultado |
|---|---|
| Filas | 1,220 (620 FISICA + 600 ONLINE); 41 columnas en la salida |
| Formatos de fecha (físicas) | `DD-MM-YYYY` 205 · `DD/MM/YYYY` 208 · `YYYY-MM-DD` 207; rango 2026-09-01 → 2026-10-15 |
| Formatos de fecha (online) | ISO con hora 392 · epoch 208; rango 2026-09-01 → 2026-10-16 |
| Epoch cuya fecha cambia (México vs UTC) | 49 · ejemplo `WEB-00005`: 1789105020 → **2026-09-10** (UTC: 2026-09-11) |
| USD | 193 pedidos, 180 con producto en catálogo, dif. máx. vs catálogo **0.10**; `WEB-00002` 169.59 → 3,307.01 |
| Huérfanos | física 29 (22 IDs, todos a 500.00) · online 33 (30 IDs, 600 MXN o 30.77 USD) |
| Min-Max | min 332.67 · max 12,032.68 · base 1,129 · extremos de la base 0.0 / 1.0 |
| Terciles | Bajo ≤ 2,069.07 < Medio ≤ 4,183.67 < Alto · base 380 / 374 / 375 |
| Todas las filas | Bajo 456 · Medio 383 · Alto 381 (76 / 9 / 6 fuera de la base) |
| Filas con `minmax_recortado` | 11 (las de cantidad ≤ 0) |
| Comparación con el diagnóstico | 28 / 28 métricas coinciden (`07_comparacion_referencia.csv`; una con tolerancia, ver §5) |
| Pruebas | 150 passed (72 nuevas) |

## 5. Diferencias con el diagnóstico inicial

| Punto | Diagnóstico | Esta ejecución | Explicación |
|---|---|---|---|
| Fechas mal leídas por `format="mixed"` + `dayfirst=True` | 104; rango 2026-01-09 → 2026-12-10 | **Con pandas 3.1.0 (`.venv`): 104** (se reproduce). Con pandas 2.3.3: 0. `dateutil.parser.parse(dayfirst=True)` da 104 y el mismo rango erróneo en ambas versiones | El comportamiento de `mixed` depende de la versión de pandas, lo que refuerza R8.2: el parseo explícito por patrón da el mismo resultado en ambas |
| Dif. máx. USD × 19.50 vs catálogo | 0.095 | 0.10 | Ya documentada por Leslie: el diagnóstico no redondeó el precio convertido; el pipeline aplica `ROUND_HALF_UP` (R6.4). La comparación usa tolerancia ±0.01 |
| Cambio a `Decimal` en la conversión | — | 0 valores distintos respecto a la versión `float` en los 1,220 registros | Verificado comparando ambas versiones sobre los datos oficiales; el cambio evita errores de redondeo en otros datos |

## 6. Decisiones que siguen pendientes

1. **A8 – zona horaria del epoch** (UTC vs México): confirmar con el docente. Cambia 49 fechas; se cambia con un parámetro.
2. **D-Y1 – registros inválidos con importe acotado vs `None`**: acordar con Nono.
3. **A9 / A2 (heredadas de Leslie):** recalcular o rechazar los 12 totales ×80 y calcular el IQR después de convertir.
4. **R8.5 – fecha futura:** implementarla en el validador de Nono.
5. Cuarentena esperada (116) y limpias (1,104): **no verificadas aquí**; dependen de la Etapa 3.

## 7. Limitaciones y lo que no se verificó

- Las evidencias de `salidas/etapa_yerik/` se generaron con el `.venv` del proyecto (pandas 3.1.0). Leslie documentó pandas 3.0.5; no se probó 3.0.5 exactamente, sí 3.1.0 y 2.3.3.
- El Python del sistema no tenía `pytest` ni `tzdata`: se instalaron ahí para una verificación cruzada y se añadió `tzdata` a `requirements.txt` (sin él, `fechas.py` usa UTC−6 fijo).
- Alguien ejecutó `scripts/ejecutar_etapa_leslie.py` con el `.venv` durante esta sesión (no lo hice yo): `salidas/etapa_leslie/` tiene 17 archivos modificados por ruido numérico/versión (p. ej. asimetría 2.168824689 vs 2.168824699, `00_ejecucion.json`, PNG). **No se deben incluir en el commit sin decisión** (ver el resumen de la sesión).
- No hay capturas de pantalla: las toma el equipo (`evidencias/GUIA_CAPTURAS_YERIK.md`).
- La comparación con el diagnóstico de §5 es de las métricas que corresponden a la etapa de Yerik; las de Leslie ya están en `salidas/etapa_leslie/07_comparacion_referencia.csv`.

## 8. Cómo reproducir

```bash
pip install -r requirements.txt
python -m pytest                          # 150 passed
python scripts/ejecutar_etapa_yerik.py    # 28/28; evidencias en salidas/etapa_yerik/
```
