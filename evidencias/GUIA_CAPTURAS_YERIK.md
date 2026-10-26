# Guía de capturas · Etapa de Yerik

Esta carpeta **no contiene capturas**: las toma el equipo al ejecutar el código, porque una imagen generada aquí no sería evidencia de su ejecución. Los valores esperados son los de la ejecución verificada (`salidas/etapa_yerik/`); si en su equipo sale otro valor, **no lo corrijan a mano**: anoten la diferencia.

Ejecutar desde la raíz del proyecto (`python scripts/ejecutar_etapa_yerik.py`; la salida completa queda también en `salidas/etapa_yerik/salida_consola.txt`).

| Fig. | Ejecutar / abrir | Qué debe verse | Valor esperado | Pie sugerido |
|---|---|---|---|---|
| Y-1 | script, sección 1 | `groupby('origen').size()`, 18 columnas y las primeras filas unificadas | FISICA 620 · ONLINE 600 · categorías 6 → 5 | Homologación de esquemas CSV y JSON en una sola estructura |
| Y-2 | sección 2 | Tabla de formatos de fecha y muestra `fecha_cruda → fecha_venta` con un epoch | 5 formatos; `1789105020 → 2026-09-10`; 49 fechas cambian vs UTC | Normalización de 5 formatos de fecha a ISO 8601 |
| Y-3 | sección 3 + `graficas/fechas_mixed_vs_explicito.png` | Rango correcto vs rango de la lectura genérica `dayfirst` | 2026-09-01…2026-10-15 vs 2026-01-09…2026-12-10; 104 fechas mal leídas | Error de interpretación evitado con parseo explícito |
| Y-4 | sección 4 + `graficas/usd_vs_catalogo.png` | Pedidos USD con `precio_unitario`, `precio_unitario_mxn`, `precio_catalogo_mxn` | 193 USD; 180 en catálogo; dif. máx. 0.10; `WEB-00002` = 3,307.01 | Conversión USD→MXN a $19.50 verificada contra el catálogo |
| Y-5 | sección 5 | Huérfanos por canal e IDs distintos; precios fijos | 29 FISICA (22 IDs, todos 500.00) · 33 ONLINE (30 IDs, 600 MXN o 30.77 USD) | Detección de productos huérfanos mediante LEFT JOIN |
| Y-6 | sección 6 (tabla de ejemplos) | `monto_total_mxn_cap`, `monto_minmax`, `segmento_importe` de 9 pedidos | `WEB-00002` 0.254217 Medio · `POS-2026-0021` 1.0 Alto · `WEB-00508` 0.85443 Alto | Escalamiento Min-Max y discretización por terciles |
| Y-7 | `graficas/hist_monto_minmax.png` | Histograma con dos líneas de corte | cortes 2,069.07 y 4,183.67 | Distribución del importe normalizado y segmentos |
| Y-8 | sección 7 | Tabla de comparación con el diagnóstico | 28/28 | Validación contra el diagnóstico inicial |
| Y-9 | `python -m pytest tests/test_integracion.py -v` | Final de la salida en verde | `72 passed` | Pruebas del módulo de integración |
| Y-10 | `python -m pytest -v` (final) | Todas las pruebas | `150 passed` (78 de Leslie + 72 de Yerik) | Batería completa del pipeline |

`graficas/segmentos_importe.png` (registros por segmento, base vs fuera de la base) es opcional.
