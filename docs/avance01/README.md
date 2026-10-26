# Sistema de Integración y Calidad de Datos Comerciales · Paquete de arranque

*(nombre provisional)* · Ingeniería de Datos (ATD-2602) · Unidad 2 · TecNM Campus Colima

| Archivo | Para quién | Contenido |
|---|---|---|
| `AVANCE_01_PROFESOR.md` | Profesor | Primer avance: reglas, diagrama, diagnóstico real, plan y evidencias |
| `REGLAS_DE_NEGOCIO.md` | Equipo → profesor | Reglas 🟥 del profesor vs 🟦 del equipo, con firmas |
| `DIAGRAMA_PIPELINE.md` | Equipo → profesor | Flujo ETL completo (Mermaid) + contratos |
| `GUIA_GENERAL_PROYECTO.md` | Los 3 | Objetivo, requisitos, arquitectura, carpetas, contratos, cronograma, rúbrica |
| `GUIA_INGENIERO_1_LESLIE.md` | Leslie | Calidad, nulos y outliers |
| `GUIA_INGENIERO_2_YERIK.md` | Yerik | Integración y transformación |
| `GUIA_INGENIERO_3_NONO.md` | Nono | Validación, cuarentena, BD y pruebas de estrés |
| `diagnostico/diagnostico_inicial.py` | Los 3 | Script de la Fase 1 (reproducible) |
| `diagnostico/resultados_diagnostico.json` | Los 3 | Todas las cifras citadas en los documentos |
| `diagnostico/salida_consola.txt` | Los 3 | Salida completa de la ejecución |
| `diagramas/*.png` | Reporte PDF | Diagramas renderizados |
| `datos/crudos/` | — | Copia sin modificar de los 3 archivos oficiales |

## Reproducir el diagnóstico

```bash
pip install pandas numpy scipy
python diagnostico/diagnostico_inicial.py
```

Lee `datos/crudos/` y escribe `diagnostico/resultados_diagnostico.json`. Funciona igual en Google Colab.
