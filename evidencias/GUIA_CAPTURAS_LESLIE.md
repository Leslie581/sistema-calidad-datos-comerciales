# Guía de capturas · Etapa de Leslie

Esta carpeta **no contiene capturas**. Las toma el equipo al ejecutar el código en su propia computadora o en Colab, porque una captura generada aquí no sería evidencia de su ejecución. Cada figura indica qué ejecutar, qué debe verse y el pie sugerido. Los valores esperados son los de la ejecución verificada (`salidas/etapa_leslie/`); si en su ejecución sale otro valor, **no lo corrijan a mano**: anoten la diferencia.

| Fig. | Ejecutar / abrir | Qué debe verse en la captura | Valor esperado | Pie sugerido |
|---|---|---|---|---|
| L-1 | `python scripts/ejecutar_etapa_leslie.py` (sección 0) | Las tres huellas SHA-256 en `True` | `True` ×3 | Verificación de integridad de los archivos originales |
| L-2 | misma ejecución, sección 2 (`fisica`) | Tabla columna / tipo / nulos / % / completitud | 97.15 %; 32 y 127 nulos; 20 duplicados | Perfil inicial de `ventas_tienda_fisica.csv` |
| L-3 | sección 2 (`online`) | Tabla del JSON, incluido `order_timestamp` mixto | 98.53 %; correo 20 (15 null + 5 vacíos); dirección 77 | Perfil inicial de `ventas_online.json` |
| L-4 | sección 4 | Tabla χ² (columna, vs, p, clasificación) | 8 pruebas, todas MCAR | Clasificación MCAR/MAR de los faltantes |
| L-5 | sección 5 | Bitácora de limpieza (JSON) | 20 duplicados · 32 + 12 montos · 127/20/77 etiquetas · medianas 2 y 1 | Correcciones aplicadas en la Fase 2 |
| L-6 | sección 7 | Límites IQR de cantidad (física y online) y de monto | LS 8.5 → tope 8 (13); online LS 3.5 (0); monto LS 12,032.68 (80 en la base) | Límites IQR con factor 1.5 |
| L-7 | sección 10 | Ejemplos `POS-2026-0031`, `POS-2026-0021`, `WEB-00508` con columnas originales y tratadas | 500 → 8; 208,598.94 conservado; 826,360.80 → 10,329.51 | Trazabilidad: valor original y valor tratado |
| L-8 | `salidas/etapa_leslie/graficas/boxplot_cantidad_fisica.png` | Gráfica | máx 500 → 8 | Cantidad antes y después del capping |
| L-9 | `salidas/etapa_leslie/graficas/boxplot_importe_mxn.png` | Gráfica | máx 2,109,055 → 12,032.68 | Importe en MXN antes y después del capping |
| L-10 | sección 8 | Tabla antes/después | ver `06_antes_despues.csv` | Comparativo de calidad antes y después |
| L-11 | sección 9 | Tabla de comparación con la referencia | 39/41 coinciden; 2 diferencias explicadas | Validación contra el diagnóstico inicial |
| L-12 | `python -m pytest -v` | Final de la salida | `78 passed` | Pruebas unitarias del módulo de calidad |

**Sugerencia para Colab:** ejecutar cada sección en una celda distinta facilita capturas limpias. Las gráficas L-8 y L-9 pueden insertarse directamente como imagen, porque las genera el código.
