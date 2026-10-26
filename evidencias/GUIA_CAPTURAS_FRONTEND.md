# Guía de capturas · KOVA (frontend)

Esta guía **no contiene capturas**: las toma el equipo con el sistema funcionando, porque una imagen generada aquí no sería evidencia de su ejecución. Los valores esperados son los de la ejecución verificada; si en su equipo sale otro valor, **no lo corrijan a mano**: anoten la diferencia.

**Preparación** (ver `docs/RESUMEN_AVANCE_FRONTEND.md` §11): Terminal 1 `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000`; Terminal 2 `cd frontend; npm run dev`; abrir http://127.0.0.1:5173. Recomendado: ventana de 1440 px de ancho, zoom 100 %, y la base ya generada (`python -m src.pipeline`).

| Fig. | Abrir / hacer | Qué debe verse | Valor esperado | PNG sugerido | Pie de figura |
|---|---|---|---|---|---|
| F-1 | `/` (Inicio), pantalla completa | Hero con «Inteligencia comercial, datos confiables», ilustración de convergencia y el riel lateral | ilustración con 620 · 600 · 1,104 · 116 | `F1_inicio.png` | Pantalla de bienvenida de KOVA |
| F-2 | `/`, desplazar hasta las tarjetas | Última ejecución, «Originales intactos» con 3 archivos, barra de 7 fases en verde | 1,220 recibidos · 90.5 % · 3 verificaciones ✓ | `F2_inicio_estado.png` | Estado de la última carga e integridad de las fuentes |
| F-3 | `/panel`, parte superior | Anillo de salud y métricas oficiales | 72 % · 1,220 · 1,104 · 116 · 90.5 % | `F3_panel_salud.png` | Panel ejecutivo: salud de los datos |
| F-4 | `/panel`, abrir «¿Cómo se calcula la salud de origen?» | Fórmula, desglose y aclaración de que es un indicador propio | 879 ÷ 1,220 = 72.05 % (879 conformes · 225 reparados · 116 rechazados) | `F4_panel_formula_indice.png` | Fórmula explícita del índice compuesto, separado de las métricas oficiales |
| F-5 | `/panel`, bloque de canales y serie diaria | Comparación física/online y áreas por día; probar el control «Transacciones» | 562+58 y 542+58; ventas del 1 sep al 16 oct | `F5_panel_canales_serie.png` | Comparación de canales y ventas diarias |
| F-6 | `/panel`, segmentos y motivos de rechazo | Barras Bajo/Medio/Alto por canal y motivos de cuarentena | PRODUCTO_HUERFANO 62 · EMAIL_MALFORMADO 28 · DUPLICADO_EXACTO 20 · CANTIDAD 11 · MONTO 11; «15 registros tienen más de un motivo» | `F6_panel_segmentos_motivos.png` | Segmentos de importe y principales motivos de rechazo |
| F-7 | `/etl`, diagrama completo | Fuentes → 7 fases → bifurcación → SQLite, todas «Completada» con su duración | orden de flujo 1·2·4·3·5·6·7; 1,104 / 116 | `F7_centro_etl_diagrama.png` | Centro ETL: recorrido del pipeline con estado y tiempo medidos por fase |
| F-8 | `/etl`, pulsar «Ejecutar pipeline» | Diálogo de confirmación que advierte que reemplaza la base | texto «reemplazará el contenido de la base» | `F8_etl_confirmacion.png` | Confirmación previa a ejecutar el pipeline |
| F-9 | `/etl`, confirmar y capturar **mientras corre** | Botón «Ejecutando…» deshabilitado, aviso «no emite progreso por fase» | sin porcentajes; duración típica < 1 s (puede ser breve: repetir si no se alcanza a ver) | `F9_etl_en_ejecucion.png` | Estado real de ejecución, sin progreso simulado |
| F-10 | `/etl` al terminar | Mensaje verde con el resultado y tabla «Tiempo por fase» | «Ejecución completada en … ms · 1,104 válidas y 116 en cuarentena» | `F10_etl_resultado.png` | Resultado de la ejecución lanzada desde el navegador |
| F-11 | `/etl`, elegir la fase 6 y bajar al log | Métricas de «Pydantic y cuarentena» y el log del proceso | válidas 1,104 · cuarentena 116 · errores inesperados 0 | `F11_etl_fase_log.png` | Detalle de fase y registro de proceso |
| F-12 | `/calidad`, primeras secciones | Tres columnas Originales / Corregidos / Tratados y perfil inicial | tienda física: 97.15 % de completitud, 20 duplicados, 32 y 127 nulos | `F12_calidad_perfil.png` | Calidad: diagnóstico inicial |
| F-13 | `/calidad`, sección 3 (MCAR/MAR) | Nota interpretativa y tabla χ² | «compatibles con MCAR … no demuestra» · 8 pruebas con p > 0.05 | `F13_calidad_mcar.png` | Clasificación de faltantes y sus limitaciones interpretativas |
| F-14 | `/calidad`, sección 4 (IQR) | Rectas Q1–Q3 y límites del importe y de la cantidad | importe: Q1 1,563.78 · Q3 5,751.34 · LS 12,032.68; cantidad física: LS 8.5, tope 8 | `F14_calidad_iqr.png` | Límites IQR con factor 1.5 y capping |
| F-15 | `/calidad`, secciones 5–7 | Tabla antes/después, Min-Max/terciles y boxplots reales | máximo 2,109,055 → 12,032.68; cortes 2,069.07 y 4,183.67 | `F15_calidad_antes_despues.png` | Comparación antes/después y gráficas del capping |
| F-16 | `/transacciones` | Tabla con filtros y paginación | 1,104 transacciones | `F16_transacciones.png` | Consulta de transacciones limpias |
| F-17 | `/transacciones`, filtrar canal ONLINE + segmento Alto + ordenar por Importe | Filtros aplicados y total actualizado | total menor que 1,104 y orden descendente | `F17_transacciones_filtros.png` | Filtros combinados, ordenación y paginación |
| F-18 | Abrir `WEB-00508` (o buscar «WEB-00508» en la barra superior) | Panel de recorrido: tabla lado a lado y línea de tiempo | 826360.8 → $10,329.51 · código MONTO_RECALCULADO_INCONSISTENTE | `F18_trazabilidad_web00508.png` | Trazabilidad: del dato original al resultado |
| F-19 | Abrir `POS-2026-0031` | Etapa «Tratamiento estadístico» con capping | cantidad 500 → cantidad con capping 8 | `F19_trazabilidad_capping.png` | El valor original se conserva junto al valor con capping |
| F-20 | Abrir `WEB-00002` | Conversión USD→MXN y fecha normalizada | 169.59 USD → $3,307.01; fecha 2026-10-12 | `F20_trazabilidad_usd.png` | Normalización de moneda y fecha |
| F-21 | `/cuarentena`, parte superior | Total rechazado y chips de causa | 116 · chips con 62 / 28 / 20 / 11 / 11 | `F21_cuarentena_resumen.png` | Zona de cuarentena: resumen y causas |
| F-22 | `/cuarentena`, pulsar el chip PRODUCTO_HUERFANO | Chip activo y tabla filtrada | 62 registros | `F22_cuarentena_filtro.png` | Cuarentena filtrada por motivo |
| F-23 | Abrir el registro `POS-2026-0493` | Panel con 3 motivos, registro crudo y trazabilidad | CANTIDAD_INVALIDA · MONTO_INVALIDO · PRODUCTO_HUERFANO; nota de solo consulta | `F23_cuarentena_detalle.png` | Detalle de un registro con varios motivos (se cuenta una sola vez) |
| F-24 | `/catalogo`, vista de tarjetas | Categorías y tarjetas de producto, con la nota de las ilustraciones | 50 productos · 6 categorías · aviso de 62 ventas huérfanas | `F24_catalogo_tarjetas.png` | Catálogo oficial de productos |
| F-25 | `/catalogo`, cambiar a «Tabla» y ordenar por Precio | Tabla ordenada | precio base de mayor a menor | `F25_catalogo_tabla.png` | Catálogo en vista de tabla |
| F-26 | `/historial` | Historial de ejecuciones y reportes por etapa | todas «Completada»; archivos de etapa_leslie/yerik/nono | `F26_historial_reportes.png` | Historial ETL y reportes descargables |
| F-27 | `/historial`, abrir una ejecución | Panel con fases, huellas SHA-256, entorno y log | 7 fases completadas | `F27_historial_detalle.png` | Detalle verificable de una ejecución |
| F-28 | `/panel` con la API detenida (cerrar Terminal 1) | Mensaje «KOVA no puede comunicarse con el servidor» con el comando para iniciar | texto de error y botón «Reintentar» | `F28_error_sin_api.png` | Manejo de desconexión del backend |
| F-29 | Redimensionar a ~390 px de ancho (o modo móvil del navegador), `/` y el menú | Diseño adaptado y menú modal | sin desplazamiento horizontal | `F29_movil.png` | Diseño responsivo en móvil |
| F-30 | Terminal: `python -m pytest` (línea final) | Resultado en verde | `442 passed` | `F30_pytest_python.png` | Pruebas automatizadas del backend y del ETL |
| F-31 | Terminal: `cd frontend; npm test` y `npm run build` | Resultados en verde | `45 passed`; build sin errores | `F31_pruebas_frontend.png` | Pruebas y compilación del frontend |

**Para el caso de ejecución fallida (opcional, F-32):** con la API detenida, copiar `datos/crudos/ventas_online.json` a una carpeta temporal, truncarlo y ejecutar `python -m src.pipeline --online <ruta>` (los originales no se tocan); luego abrir `/historial`: la ejecución aparece como **Fallida** con la etapa «1. Extracción», no como exitosa. Pie: «Una ejecución fallida se registra y se muestra como tal».

**Consejos:** usar el modo de pantalla completa del navegador; ocultar marcadores y extensiones; para F-9, si la ejecución termina demasiado pronto, probar de nuevo o grabar un GIF corto.
