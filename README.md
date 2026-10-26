# Sistema de Integración y Calidad de Datos Comerciales *(nombre provisional)*

Proyecto integrador · Ingeniería de Datos (ATD-2602) · Unidad 2: Limpieza y Preprocesamiento de Datos
TecNM · Instituto Tecnológico de Colima · Prof. Armando Román Gallardo Heredia · Ago-Dic 2026

## Equipo y roles (guía oficial, sección 2)

| Rol | Integrante | Módulos |
|---|---|---|
| Ingeniero/a 1 · Calidad, Nulos y Outliers | **Leslie** | `src/calidad/` |
| Ingeniero/a 2 · Transformación e Integración | **Yerik** | `src/extraccion.py`, `src/integracion/` |
| Ingeniero/a 3 · Validación, Resiliencia y BD | **Nono** | `src/validacion/`, `src/persistencia/`, `src/pipeline.py` *(pendientes)* |

## Estado por etapa

| Etapa | Estado | Evidencia |
|---|---|---|
| Avance 01 (reglas, diagrama, diagnóstico) | ✅ entregado | `docs/avance01/`, `diagnostico/` |
| **Etapa 1 · Leslie** (F1 perfil, F2 limpieza, F3 IQR/capping) | ✅ ejecutada y probada | `salidas/etapa_leslie/`, `docs/RESUMEN_AVANCE_LESLIE.md` |
| Extracción + homologación (Yerik) | 🟡 versión mínima | Yerik la revisa en la siguiente etapa |
| USD→MXN + catálogo (Yerik) | 🟡 versión mínima (solo para el IQR en MXN) | ídem |
| Fechas ISO, Min-Max, discretización (Yerik) | ⏳ pendiente | — |
| Pydantic, cuarentena, SQLite, estrés (Nono) | ⏳ pendiente | — |
| Interfaz web | ⬜ fuera de alcance por ahora | — |

## Instalación y ejecución

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python -m pytest                              # 78 pruebas
python scripts/ejecutar_etapa_leslie.py       # regenera salidas/etapa_leslie/
python diagnostico/diagnostico_inicial.py     # diagnóstico del Avance 01 (referencia)
```

En Google Colab: sube la carpeta (o clona el repositorio), ejecuta `!pip install -r requirements.txt` y luego los mismos comandos con `!`.

## Estructura

```
datos/crudos/            archivos oficiales · SOLO LECTURA (verificados por SHA-256 en cada ejecución)
diagnostico/             script y resultados del Avance 01 (valores de referencia)
docs/                    PDF del profesor, documentos del Avance 01 y resumen de la etapa de Leslie
src/config.py            constantes del profesor (19.50, 1.5) y del equipo        [compartido]
src/contratos.py         columnas por etapa y códigos de corrección              [compartido]
src/extraccion.py        lectura sin conversiones silenciosas                     [Yerik · mínima]
src/integracion/         homologacion.py · moneda.py · catalogo.py               [Yerik · mínimas]
src/calidad/             perfilado.py · limpieza.py · outliers.py · reporte.py   [Leslie]
tests/                   pruebas unitarias y contra los datasets oficiales
scripts/                 ejecutar_etapa_leslie.py
salidas/etapa_leslie/    evidencias generadas por la ejecución real
evidencias/              guía de capturas (las toma el equipo; no se incluyen capturas inventadas)
```
