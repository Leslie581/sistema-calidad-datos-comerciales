# Sistema de Integración y Calidad de Datos Comerciales *(nombre provisional)*

Proyecto integrador · Ingeniería de Datos (ATD-2602) · Unidad 2: Limpieza y Preprocesamiento de Datos
TecNM · Instituto Tecnológico de Colima · Prof. Armando Román Gallardo Heredia · Ago-Dic 2026

## Equipo y roles (guía oficial, sección 2)

| Rol | Integrante | Módulos |
|---|---|---|
| Ingeniero/a 1 · Calidad, Nulos y Outliers | **Leslie** | `src/calidad/` |
| Ingeniero/a 2 · Transformación e Integración | **Yerik** | `src/extraccion.py`, `src/integracion/` |
| Ingeniero/a 3 · Validación, Resiliencia y BD | **Nono** | `src/validacion/`, `src/persistencia/`, `src/pipeline.py`, `datos/estres/` |

## Estado por etapa

| Etapa | Estado | Evidencia |
|---|---|---|
| Avance 01 (reglas, diagrama, diagnóstico) | ✅ entregado | `docs/avance01/`, `diagnostico/` |
| **Etapa 1 · Leslie** (F1 perfil, F2 limpieza, F3 IQR/capping) | ✅ ejecutada y probada | `salidas/etapa_leslie/`, `docs/RESUMEN_AVANCE_LESLIE.md` |
| **Etapa 2 · Yerik** (extracción, homologación, fechas ISO, USD→MXN, catálogo, Min-Max, terciles) | ✅ ejecutada y probada | `salidas/etapa_yerik/`, `docs/RESUMEN_AVANCE_YERIK.md` |
| **Etapa 3 · Nono** (Pydantic, cuarentena, SQLite, pipeline, estrés) | ✅ ejecutada y probada · pendiente de commit | `salidas/etapa_nono/`, `docs/RESUMEN_AVANCE_NONO.md` |
| Interfaz web | ⬜ fuera de alcance por ahora | — |

## Instalación y ejecución

**Windows PowerShell** (desde la carpeta del proyecto):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # si PowerShell bloquea el script: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt

python -m src.pipeline                 # ETL completo → salidas\etapa_nono\calidad_comercial.db (SQLite) y evidencias
python -m pytest                       # 357 pruebas (Leslie 78 · Yerik 74 · Nono 205)
python datos\estres\generar_estres.py  # 48 escenarios con datos corruptos → salidas\etapa_nono\estres\
python scripts\ejecutar_etapa_leslie.py   # regenera salidas\etapa_leslie\
python scripts\ejecutar_etapa_yerik.py    # regenera salidas\etapa_yerik\
```

Linux/macOS: `source .venv/bin/activate` y las mismas órdenes con `/` en las rutas.

**Resultado del pipeline con los datasets oficiales:** 1,220 registros de entrada (620 físicos + 600 online) → **1,104** en `transacciones_limpias` + **116** en `cuarentena_errores`. Opciones de `python -m src.pipeline`: `--bd RUTA`, `--salida CARPETA`, `--no-reemplazar`, `--catalogo/--fisica/--online RUTA` (archivos alternos para pruebas). Código de salida 0 = completado, 1 = fallido controlado (sin traceback). La base `.db` y los logs `.log` están en `.gitignore`: se regeneran con el comando anterior. Ábrala con DB Browser for SQLite; consultas de ejemplo en `salidas\etapa_nono\07_consultas_verificacion.txt`.

En Google Colab: sube la carpeta (o clona el repositorio), ejecuta `!pip install -r requirements.txt` y luego los mismos comandos con `!`.

## Estructura

```
datos/crudos/            archivos oficiales · SOLO LECTURA (verificados por SHA-256 en cada ejecución)
datos/estres/            generar_estres.py: escenarios con datos corruptos (copias de registros reales)   [Nono]
diagnostico/             script y resultados del Avance 01 (valores de referencia)
docs/                    PDF del profesor, Avance 01 y resúmenes de las etapas (Leslie, Yerik, Nono)
src/config.py            constantes del profesor (19.50, 1.5) y del equipo                               [compartido]
src/contratos.py         columnas por etapa, códigos de corrección, alerta y rechazo                      [compartido]
src/extraccion.py        lectura sin conversiones silenciosas                                             [Yerik]
src/integracion/         homologacion · fechas · moneda · catalogo · transformacion                       [Yerik]
src/calidad/             perfilado · limpieza · outliers · reporte                                        [Leslie]
src/validacion/          esquemas.py (Pydantic) · cuarentena.py (segregación)                             [Nono]
src/persistencia/        esquema.sql · carga.py (SQLite transaccional)                                    [Nono]
src/pipeline.py          orquestador: python -m src.pipeline                                              [Nono]
src/reporte_final.py     evidencias, tablas y gráficos de la ejecución                                    [Nono]
tests/                   pruebas unitarias, de estrés y contra los datasets oficiales
scripts/                 ejecutar_etapa_leslie.py · ejecutar_etapa_yerik.py
salidas/etapa_*/         evidencias generadas por las ejecuciones reales
evidencias/              guías de capturas (las toma el equipo; no se incluyen capturas inventadas)
```
