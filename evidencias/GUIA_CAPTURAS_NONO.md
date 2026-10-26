# Guía de capturas · Etapa de Nono

Esta carpeta **no contiene capturas**. Las toma el equipo al ejecutar el código en su propia computadora, porque una captura generada aquí no sería evidencia de su ejecución. Los valores esperados son los de la ejecución verificada (`salidas/etapa_nono/`); si en su equipo sale otro valor, **no lo corrijan a mano**: anoten la diferencia.

Preparación (Windows PowerShell, desde la raíz del proyecto):

```powershell
.venv\Scripts\Activate.ps1
python -m src.pipeline
```

La base queda en `salidas\etapa_nono\calidad_comercial.db` (abrir con DB Browser for SQLite → *Open Database*). Las consultas SQL listas para pegar en la pestaña *Execute SQL* están en `salidas\etapa_nono\07_consultas_verificacion.txt`.

| Fig. | Ejecutar / abrir | Sección exacta a capturar | Valor esperado | PNG recomendado | Pie sugerido |
|---|---|---|---|---|---|
| N-1 | VS Code / editor: `src\validacion\esquemas.py` | La clase `TransaccionLimpia` y dos validadores (`v_catalogo` y `v_email`) en la misma imagen | `@field_validator("en_catalogo")` y `@field_validator("email_cliente")` visibles | `N1_modelo_pydantic.png` | Modelo Pydantic con validadores personalizados |
| N-2 | `python -m src.pipeline` | Bloque final de la consola: línea `Entrada: 1220 → limpias: 1104 + cuarentena: 116` y la lista de códigos | PRODUCTO_HUERFANO 62 · EMAIL_MALFORMADO 28 · DUPLICADO_EXACTO 20 · CANTIDAD_INVALIDA 11 · MONTO_INVALIDO 11 | `N2_consola_pipeline.png` | Ejecución del pipeline completo sobre los datasets oficiales |
| N-3 | DB Browser → pestaña *Database Structure* → `transacciones_limpias` | Lista de columnas con PK, NOT NULL y las 4 tablas | 4 tablas: `ejecuciones`, `catalogo_productos`, `transacciones_limpias`, `cuarentena_errores` | `N3_estructura_limpias.png` | Esquema de la tabla de transacciones limpias |
| N-4 | DB Browser → *Browse Data* → `cuarentena_errores` | Columnas `id_registro`, `codigos_error`, `motivo_rechazo_cuarentena` y `registro_original` | 116 filas; p. ej. `POS-2026-0216`: `CANTIDAD_INVALIDA;MONTO_INVALIDO` | `N4_cuarentena_errores.png` | Zona de cuarentena con trazabilidad |
| N-5 | DB Browser → *Execute SQL*: consultas 1 y 2 de `07_consultas_verificacion.txt` | Resultado de la consulta 1 (conservación) y de la 2 (motivos) | 1104 · 116 · 1220; PRODUCTO_HUERFANO 57, EMAIL_MALFORMADO 25, DUPLICADO_EXACTO 19, CANTIDAD+MONTO 10, EMAIL+HUERFANO 3, triple 1, DUPLICADO+HUERFANO 1 | `N5_conservacion_motivos.png` | Conservación del conteo: limpias + cuarentena = 1,220 |
| N-6 | `python -m pytest tests\test_persistencia.py -v -k rollback` | Líneas `test_rollback_*` en verde | 3 pruebas `rollback` aprobadas | `N6_rollback.png` | Rollback ante una falla en la carga: 0 filas parciales |
| N-7 | `python -m pytest -v` (final de la salida) | Última línea con el total | `357 passed` (78 Leslie + 74 Yerik + 205 Nono) | `N7_pytest_completo.png` | Batería de pruebas completa, incluidas las de estrés |
| N-8 | PowerShell: ver comando abajo (JSON truncado) | Sección «FALLIDO» sin `Traceback`; luego `echo $LASTEXITCODE` | `Estado: FALLIDO` · `ErrorExtraccion` · código de salida `1` | `N8_resiliencia_json_corrupto.png` | Resiliencia ante un archivo corrupto |
| N-9 | `python datos\estres\generar_estres.py` | Tabla de escenarios y la línea final | `OK: 48 / 48` | `N9_pruebas_estres.png` | Resultados de las pruebas de estrés con datos corruptos |
| N-10 | DB Browser → *Execute SQL*: consulta 4 | Ventas por canal y segmento | FISICA Alto 262 · Bajo 144 · Medio 156 · ONLINE Alto 110 · Bajo 226 · Medio 206 | `N10_ventas_canal_segmento.png` | Transacciones limpias por canal y segmento de importe |
| N-11 | DB Browser → *Execute SQL*: consulta 5 | `WEB-00508` con `monto_total_origen` y `monto_total_mxn_cap` | 826360.8 → 10329.51; correcciones con `MONTO_RECALCULADO_INCONSISTENTE` | `N11_trazabilidad_original_tratado.png` | Trazabilidad: el valor original se conserva junto al tratado |
| N-12 | `salidas\etapa_nono\graficas\cuarentena_por_motivo.png` | Gráfico completo | PRODUCTO_HUERFANO 62 · EMAIL 28 · DUPLICADO 20 · MONTO 11 · CANTIDAD 11 | (ya es PNG; puede insertarse tal cual) | Motivos de cuarentena (un registro puede tener varios) |
| N-13 | `salidas\etapa_nono\graficas\conservacion_por_canal.png` | Gráfico completo | Física 562 + 58 · Online 542 + 58 | (ya es PNG) | Conservación de registros por canal |
| N-14 | Abrir `salidas\etapa_nono\09_comparacion_estimaciones.csv` | Tabla completa | 11 de 12 coinciden; difiere «más de un motivo» (16 vs 15) con su nota | `N14_comparacion_estimaciones.png` | Comparación con las estimaciones del diagnóstico |

**Comando para N-8** (copia temporal con el JSON truncado; no modifica los originales ni la base real):

```powershell
$t = New-TemporaryFile; '[{"order_id": "WEB-' | Set-Content $t -Encoding utf8
python -m src.pipeline --bd "$env:TEMP\prueba_fallo.db" --salida "$env:TEMP\salida_fallo" --online $t
echo $LASTEXITCODE
```

Salida esperada (resumen): `Estado: FALLIDO`, `FALLIDO en «1. Extracción» (ErrorExtraccion): … no es un JSON válido…`, y `1`. Una versión real de esta salida está en `salidas/etapa_nono/estres/consola_json_truncado.txt`.

**Sugerencia:** para N-4, N-5 y N-10 conviene ensanchar las columnas en DB Browser (doble clic en el borde del encabezado) para que se lean los motivos completos.
