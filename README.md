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
| **Etapa 3 · Nono** (Pydantic, cuarentena, SQLite, pipeline, estrés) | ✅ ejecutada y probada | `salidas/etapa_nono/`, `docs/RESUMEN_AVANCE_NONO.md` |
| **Etapa 4 · KOVA** (API FastAPI + interfaz React) | ✅ implementada y probada · pendiente de commit | `docs/RESUMEN_AVANCE_FRONTEND.md`, `evidencias/GUIA_CAPTURAS_FRONTEND.md` |

## Instalación y ejecución

**Windows PowerShell** (desde la carpeta del proyecto):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # si PowerShell bloquea el script: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt

python -m src.pipeline                 # ETL completo → salidas\etapa_nono\calidad_comercial.db (SQLite) y evidencias
python -m pytest                       # 516 pruebas (etapas 1-3: 357 · API y comercial: 159)
python datos\estres\generar_estres.py  # 48 escenarios con datos corruptos → salidas\etapa_nono\estres\
python scripts\ejecutar_etapa_leslie.py   # regenera salidas\etapa_leslie\
python scripts\ejecutar_etapa_yerik.py    # regenera salidas\etapa_yerik\
```

### KOVA · plataforma web (etapa 4)

Requiere Node.js 20+ (probado con 24). Una sola vez: `cd frontend; npm install; cd ..`.

```powershell
# Terminal 1 · API (FastAPI, solo lectura sobre SQLite)
.venv\Scripts\Activate.ps1
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2 · interfaz (React + Vite)
cd frontend
npm run dev                            # abre http://127.0.0.1:5173
```

**Pulso comercial** (nuevo): `http://127.0.0.1:5173/pulso-comercial` (ventas, comparación entre períodos, canales y productos; API en `/api/comercial/*`). Si 5173 u 8000 ya están ocupados, usa otros puertos: `$env:KOVA_API_URL="http://127.0.0.1:8001"; $env:KOVA_WEB_PORT="5174"; npm run dev` y `python -m uvicorn src.api.main:app --port 8001`. Detalle en `docs/MEJORAS_KOVA_PULSO_COMERCIAL.md`.

Con una sola terminal: `cd frontend; npm run build` y abrir http://127.0.0.1:8000 (FastAPI sirve `frontend\dist`). Desde el **Centro ETL** se puede ejecutar el pipeline real (con confirmación y sin ejecuciones simultáneas). Pruebas del frontend: `cd frontend; npm run lint; npm test; npm run build`. Detalle completo: `docs/RESUMEN_AVANCE_FRONTEND.md`; capturas: `evidencias/GUIA_CAPTURAS_FRONTEND.md`.

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
src/api/                 API FastAPI de KOVA (solo lectura + ejecución protegida del pipeline)            [Etapa 4]
frontend/                KOVA: React + TypeScript + Vite + Tailwind                                       [Etapa 4]
src/reporte_final.py     evidencias, tablas y gráficos de la ejecución                                    [Nono]
tests/                   pruebas unitarias, de estrés y contra los datasets oficiales
scripts/                 ejecutar_etapa_leslie.py · ejecutar_etapa_yerik.py
salidas/etapa_*/         evidencias generadas por las ejecuciones reales
evidencias/              guías de capturas (las toma el equipo; no se incluyen capturas inventadas)
```
