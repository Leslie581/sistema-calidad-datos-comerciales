# KOVA · Mejoras: Pulso comercial, monedas originales y refinamiento de interfaz

**Rama:** `feat/kova-refinamiento-comercial` (creada desde `origin/main` = `c3ddb1e`, sin commits todavía)
**Alcance:** solo FastAPI y React. No se tocó el ETL (siete fases, reglas estadísticas, paridad 19.50, cuarentena), ni el esquema SQLite, ni los datasets, ni evidencias o guías existentes.
**Verificado:** 2026-10-27 · `.venv` (Python 3.13, pandas 3.1.0) · Node 24.

---

## 1. Mejoras implementadas

| # | Mejora | Dónde |
|---|---|---|
| 1 | **Pulso comercial**: página `/pulso-comercial` con ventas, comparación entre períodos, canales, productos y diagnóstico en lenguaje natural | `src/api/comercial.py`, `frontend/src/pages/PulsoComercial.tsx`, `frontend/src/components/pulso/` |
| 2 | **Tarjeta «Pulso comercial» en el Panel ejecutivo** (resumen + acceso), sin alterar el dashboard de calidad | `frontend/src/components/pulso/TarjetaPulso.tsx` |
| 3 | **API comercial** de solo lectura: `/api/comercial/opciones`, `/resumen`, `/tendencia`, `/canales`, `/productos` | `src/api/main.py`, `src/api/esquemas.py` |
| 4 | **Moneda original visible**: panel «Moneda y conversión» en el detalle de cada transacción (USD → MXN) | `servicios._moneda`, `Trazabilidad.tsx › PanelMoneda` |
| 5 | **Catálogo simplificado**: título + filtros de categoría; sin párrafo descriptivo; cabecera más baja | `Catalogo.tsx` |
| 6 | **Encabezados homogéneos**: «Panel ejecutivo», «Pulso comercial», «Centro ETL», «Calidad de datos», «Historial de ejecuciones», «Transacciones», «Cuarentena», «Catálogo de productos», cada uno con un subtítulo breve | todas las páginas |
| 7 | **Refinamientos de UX**: controles segmentados que se ajustan en móvil, avisos de atípicos junto al titular, variaciones con flecha + signo + texto (no solo color), estados vacíos y de error propios del pulso, `KOVA_API_URL`/`KOVA_WEB_PORT` para puertos alternos | varios |

**Cómo abrir Pulso comercial:** menú lateral → *Pulso comercial*, o la tarjeta del Panel ejecutivo, o `http://127.0.0.1:5173/pulso-comercial` (arranque en el README).

## 2. Qué importe se usa (punto obligatorio)

Se inspeccionó el contrato del ETL (`contratos.py`), el DDL real y los datos antes de elegir la columna.

| Columna SQLite (`transacciones_limpias`) | Qué es | ¿La usa Pulso comercial? |
|---|---|---|
| `monto_total_origen` | Dato crudo en la moneda original, a veces inconsistente (ej. `WEB-00508`: 826,360.80; `WEB-00237`: 17,304.80 USD) | No (solo se muestra en el detalle como «original») |
| `precio_unitario_original` | Precio crudo en la moneda original | No (detalle) |
| **`monto_total_mxn`** | **`ROUND(cantidad × precio_unitario_mxn, 2)`: importe corregido y normalizado a MXN, antes del capping** | **Sí: es el importe comercial** |
| `monto_cantidad_cap_mxn`, `monto_total_mxn_cap` | Con capping IQR (cantidad y/o importe recortados); sirven para escalar y segmentar | No (es el importe del Panel ejecutivo) |

Comprobaciones hechas sobre la base real: `monto_total_mxn = ROUND(cantidad × precio_unitario_mxn, 2)` en el 100 % de las 1,104 filas; el total con `monto_total_mxn` ($11,583,998.43) difiere del total con capping ($4,585,211.65) en $7.0 M, así que **no son intercambiables**; `transacciones_limpias` no contiene registros de cuarentena, por lo que éstos nunca suman como ventas. La leyenda visible en pantalla es: *«Importes de transacciones conformes, normalizados a MXN, sin recorte estadístico»*, seguida de «No es ingreso contable auditado, utilidad ni margen».

**Hallazgo que se muestra, no se oculta:** con importes sin capping, las transacciones que el ETL marcó como atípicas (`es_outlier_cantidad`/`es_outlier_monto`, p. ej. cantidades de 99 y 500) concentran una parte enorme del importe. Para que ello no distorsione la lectura, la respuesta incluye `atipicas` (número, importe y % del importe) y la **variación recalculada sin ellas**; la pantalla lo advierte junto al titular.

## 3. Métricas y fórmulas

| Indicador | Fórmula (en Python, `src/api/comercial.py`) |
|---|---|
| Importe vendido | `SUM(monto_total_mxn)` del período, filtrado por canal y tipo de venta |
| Transacciones conformes | `COUNT(*)` |
| Ticket promedio | importe ÷ transacciones |
| Promedio diario | importe ÷ **días cubiertos por los datos** del período |
| Variación porcentual | `((actual − anterior) ÷ anterior) × 100`; **`None`** si no hay período anterior o el anterior es 0 |
| Participación de un canal | importe del canal ÷ suma de ambos canales × 100 |
| Participación de producto/categoría | importe ÷ importe total del período filtrado × 100 |
| Unidades | `SUM(cantidad)` (cantidad real, sin capping) |
| Importe sin atípicos | `SUM(monto_total_mxn)` donde `es_outlier_cantidad = 0 AND es_outlier_monto = 0` |
| Acumulado, ticket diario | suma corrida / importe del día ÷ transacciones del día |

Los cálculos viven solo en Python; React únicamente formatea. Todas las consultas son parametrizadas; las fechas se validan (`YYYY-MM-DD` real, `desde ≤ hasta`, máximo 366 días).

## 4. Criterios de comparación temporal

- **Cobertura:** rango [primera fecha, última fecha] de las transacciones conformes (hoy 2026-09-01 → 2026-10-16). Los datos son históricos: **el mes inicial es el último con datos, no el mes del sistema operativo**.
- **Fechas efectivas:** cada respuesta incluye primera y última venta del período y `dias_cubiertos`/`cobertura`.
- **Período parcial:** se marca (`parcial`) cuando el mes no está completo en los datos (octubre: 16 de 31 días) o cuando un rango se sale de la cobertura. Se avisa en la cabecera, en el diagnóstico y en la comparación por mes.
- **Comparación por omisión (`equivalente`):** mismos días del mes anterior (1–16 oct vs 1–16 sep). En un rango personalizado, el período inmediato anterior de igual longitud.
- **Alternativas:** `mes_anterior_completo` (solo con mes; puede no ser homogéneo) y `ninguna`.
- **Homogeneidad:** una comparación es homogénea solo si ambos períodos tienen **el mismo número de días y cobertura completa**. Si no lo es: se muestra el total pero **no se clasifica tendencia**; se informa la variación del **promedio diario**, que sí es comparable.
- **Sin anterior:** si el período anterior queda fuera de los datos (p. ej. septiembre completo, que equivale a 1–30 ago), `anterior_kpis` es nulo, **todas las variaciones son `null`** y el diagnóstico es «No hay información suficiente para evaluar una tendencia».
- **Tipo de venta:** por omisión cuentan todas las transacciones conformes (R11.1 conserva cancelados y devueltos). «Solo efectivas» excluye `CANCELADO` y `DEVUELTO`; la pantalla indica cuánto importe representan (decisión de reportes pendiente de validar con el equipo, ver §10).
- **Canal:** `FISICA`, `ONLINE` o ambos. La tarjeta de canales muestra siempre ambos.

## 5. Reglas de los mensajes interpretativos

Todos los umbrales son **criterios propios de KOVA, no estándares del profesor**; son configurables (`Criterios` en `comercial.py`, o variables `KOVA_<NOMBRE>`, o `Ajustes.criterios_comerciales`) y se devuelven en cada respuesta (`criterios`). Cada mensaje trae su `evidencia` numérica.

| Regla | Condición | Mensaje (resumen) |
|---|---|---|
| Sin datos | 0 transacciones | «No hay transacciones conformes en el período seleccionado» (+ cobertura disponible) |
| Parcial | el período no está completo | «El período es parcial: solo hay datos del … al … (n de m días)» |
| Sin comparación | sin anterior, o anterior fuera de cobertura | «No hay información suficiente para evaluar una tendencia» |
| No homogéneo | distinto número de días o cobertura < 100 % | «los períodos no son equivalentes… no se clasifica una tendencia» + variación del promedio diario |
| Anterior sin ventas | anterior = 0 | «la variación porcentual no está definida (denominador cero)» |
| Pocas transacciones | algún período < 10 transacciones (`min_transacciones_periodo`) | «la variación no es concluyente» |
| Tendencia | variación ≥ **+5 %** → «aumentaron»; ≤ **−5 %** → «disminuyeron»; entre ambos → «se mantienen relativamente estables» | cita importes, variación y ambos períodos |
| Composición | con tendencia clasificada | variación de transacciones y del ticket promedio |
| Concentración de canal | un canal ≥ **60 %** del importe | «El canal X concentró n % de las ventas»; si no, «repartidas» |
| Desempeño por canal | ambos con anterior y ≥ 10 transacciones; brecha ≥ **5 puntos** | «El canal X presentó un mejor desempeño: +a % frente a +b %»; si no, «evolucionaron de forma similar» |
| Atípicos | transacciones atípicas ≥ **20 %** del importe | advertencia + variación sin ellas |
| Pedidos no efectivos | modo «todas» y hay cancelados/devueltos | importe incluido y cómo excluirlos |
| Alcance (siempre) | — | «No hay costos, márgenes ni gastos en los datos: no permiten afirmar rentabilidad ni salud financiera» |

Una prueba verifica que ningún mensaje afirme rentabilidad, ganancia o utilidad.

## 6. Importe comercial frente a capping

El Panel ejecutivo conserva su lectura estadística (`monto_total_mxn_cap`: $4,585,212 en total) y la tarjeta de Pulso lo enlaza sin mezclarlos. Pulso comercial usa `monto_total_mxn` ($11,583,998 en total). La página incluye la nota de qué es y qué no es el importe, el nombre del campo, y un enlace al Panel para el análisis con recorte. Pruebas: el importe de Pulso es `SUM(monto_total_mxn)` y difiere del importe con capping; el Panel sigue mostrando el estadístico.

## 7. Mejoras de monedas

El detalle de transacción (`/transacciones/{id}`) incluye ahora `moneda` y la interfaz muestra, **sin saturar la tabla principal** (se usa el panel lateral), para una venta en USD: precio original (USD) · importe original reportado (USD) · tipo de cambio 1 USD = $19.50 · precio convertido · **importe normalizado a MXN** (destacado) · importe con capping («Sin recorte» si no se aplicó). Casos:

- **Importe original inconsistente** (ej. `WEB-00237`: 17,304.80 USD reportados; coherente = $216.31 USD): se conserva el valor reportado y se explica que el ETL lo recalculó.
- **Venta en MXN:** «Registrada originalmente en MXN: no hay conversión»; no se inventa tipo de cambio.
- La conversión del ETL **no se modificó**; los 174 pedidos en USD conservan precio e importe originales (`precio_unitario_original`, `monto_total_origen`) con tipo de cambio 19.5 (prueba sobre toda la base).

## 8. Cambios de interfaz

Encabezados nuevos (antes → ahora): «Cómo están tus datos comerciales» → **Panel ejecutivo** · «Qué tan limpio llegó el dato…» → **Calidad de datos** · «El recorrido completo de tus datos» → **Centro ETL** · «Todo lo que ha ejecutado KOVA» → **Historial de ejecuciones** · «Transacciones comerciales» → **Transacciones** · «Registros apartados, con su explicación» → **Cuarentena** · **Catálogo de productos** (sin párrafo). Menú: nueva entrada *Pulso comercial* bajo Resumen. Pulso comercial usa un fondo propio (curvas de ritmo con punto ámbar), marca de agua del isotipo, indicador protagonista, tarjeta de interpretación, gráfica diaria interactiva (Importe/Transacciones/Ticket/Acumulado, período actual frente al anterior), comparación por mes con meses parciales rayados, canales y productos destacados.

## 9. Pruebas y resultados

| Suite | Resultado |
|---|---|
| `python -m pytest` | **516 passed** (442 previas + 74 nuevas en `tests/test_comercial.py`) |
| `npm test` (Vitest) | **76 passed** (45 previas + 31 nuevas en `src/Pulso.test.tsx`) |
| `npx tsc --noEmit` · `npx eslint .` · `npm run build` | sin errores |
| Integridad de los datasets originales | SHA-256 verificado por las pruebas del pipeline (`test_originales_intactos_por_sha256`, `test_pipeline`) |
| Pipeline ETL | las pruebas lo ejecutan sobre bases temporales; no se re-ejecutó sobre `salidas/etapa_nono` |

Cobertura nueva: ventas mensuales y ticket · físicas/online y participación · variación porcentual (denominador cero, nulos, negativos) · mes parcial · ausencia de mes anterior · período sin transacciones y fuera de cobertura · rango parcialmente cubierto · umbrales de tendencia en el borde (±5 %) y configurables · pocas transacciones · canales y atípicos · pedidos efectivos · importe sin capping · productos y categorías · 20 parámetros inválidos (422) · base inexistente/sin ventas · solo lectura · USD conservados · formularios, estados vacíos, errores, navegación y tarjeta del Panel en React.
Resultados de referencia (de la base actual, **no** constantes en el código): 1–16 oct 2026 = $5,967,744 frente a $3,423,636 (+74.3 %); 32 transacciones atípicas = 79.1 % del importe y, sin ellas, la variación sería −8.8 %.

## 10. Limitaciones y decisiones abiertas

1. **No son ingresos auditados ni utilidad:** no hay costos, márgenes ni gastos.
2. **Cancelados y devueltos:** por omisión cuentan (R11.1); «Solo efectivas» los excluye. Queda por decidir con el equipo cuál es el predeterminado para reportes.
3. **Los atípicos dominan el importe sin capping** (79 % en octubre): el titular «+74.3 %» debe leerse con el aviso adjunto. No se cambió la regla estadística.
4. **Septiembre completo no tiene anterior** (no hay datos de agosto): no se compara.
5. Solo dos meses de datos: la «tendencia» es la comparación entre dos períodos equivalentes, no una serie larga.
6. Los umbrales (5 %, 60 %, 5 pp, 10 transacciones, 20 %) son propuestas de KOVA, no del profesor.
7. El ticket promedio es por transacción, no por cliente (los datos no permiten identificarlo con fiabilidad en el canal online).
8. Los procesos `uvicorn` y `vite` que ya estuvieran abiertos antes de esta rama usan código anterior: hay que reiniciarlos.
9. Los gráficos se revisaron en el navegador integrado; las capturas finales las toma el equipo.

## 11. Capturas a actualizar

Todas las de las pantallas con encabezado o contenido distinto: **F-3/F-6 (Panel: título y tarjeta Pulso), F-7 a F-11 (Centro ETL: título), F-12 a F-15 (Calidad: título), F-16 a F-20 (Transacciones: título; F-18/F-20 ahora incluyen «Moneda y conversión»), F-21 a F-23 (Cuarentena: título), F-24/F-25 (Catálogo: cabecera simplificada), F-26/F-27 (Historial: título)**. Nuevas: Pulso comercial completo (hero + filtros, importe + diagnóstico, gráfica diaria, canales y meses, productos), el aviso de atípicos, el período parcial, un rango personalizado, el estado «sin comparación válida» (septiembre) y el panel de moneda de `WEB-00237` (USD) frente a `WEB-00003` (MXN).
