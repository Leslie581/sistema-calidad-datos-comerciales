# Resumen técnico · Etapa 4: KOVA · Plataforma web de inteligencia y calidad de datos comerciales

**Rama:** `feat/frontend-comercio` (sin commits todavía; parte de `main` con las etapas 1–3 integradas)
**Verificado:** 2026-10-26 · Windows 11 · Python 3.13.15 · Node 24.20 · npm 11.19
**Marca:** *KOVA — Inteligencia comercial, datos confiables.* Nombre propio y breve; no es un acrónimo.

---

## 1. Qué se desarrolló

| Entregable | Estado | Cómo se comprobó |
|---|---|---|
| API FastAPI de solo lectura sobre SQLite + ejecución protegida del pipeline | ✅ | 81 pruebas contra una base **real** generada por el pipeline |
| Frontend React + TypeScript + Vite + Tailwind | ✅ | `tsc`, `eslint`, `vite build` sin errores · 45 pruebas |
| Identidad visual propia (isotipo SVG, fondos por sección, ilustraciones, animaciones) | ✅ | revisado en el navegador a escritorio, tablet y móvil (sin desbordes horizontales) |
| Pantallas: Inicio, Panel, Centro ETL, Calidad, Transacciones (+trazabilidad), Cuarentena, Catálogo, Historial y reportes | ✅ | pruebas de componentes con respuestas reales + recorrido manual |
| Ejecución real del pipeline desde el navegador | ✅ | ejecutada en el navegador: 1,104 limpias + 116 en cuarentena, 7 fases COMPLETADA con duraciones medidas |
| Sin ejecuciones simultáneas | ✅ | prueba con ejecutor lento: segundo POST → 409 |
| Python original (Leslie, Yerik, Nono) intacto | ✅ | 442 pruebas de Python pasan (357 previas + 85 nuevas) |
| Capturas de pantalla | ⏳ las toma el equipo | `evidencias/GUIA_CAPTURAS_FRONTEND.md` |

## 2. Hitos

| Hito | Implementado | Comprobado |
|---|---|---|
| 1 · Auditoría y arquitectura | Se confirmó la rama (`feat/frontend-comercio`, ya con la etapa 3), las 357 pruebas previas, las 4 tablas reales de SQLite y las bitácoras JSON que ya escribe el pipeline | `git status`, `pytest` (357 ✓), inspección de la BD |
| 2 · Base técnica | FastAPI (15 rutas), servicios SQLite, proyecto Vite, tokens de diseño, layout y navegación | `curl`/`TestClient` y compilación |
| 3 · Funcionalidad principal | Panel, transacciones, cuarentena, catálogo | pruebas + navegador |
| 4 · Funcionalidad avanzada | Centro ETL con ejecución, historial, calidad, trazabilidad, reportes | ejecución real desde el navegador |
| 5 · Acabado visual | isotipo, 6 fondos, ilustraciones, marcas de agua, animaciones, estados vacíos, responsivo | recorrido a 375, 768 y 1440 px |
| 6 · Verificación | 85 pruebas de Python + 45 de React, build, lint, documentación | ver §9 |

## 3. Arquitectura

```
Navegador (React) ──HTTP /api──▶ FastAPI (src/api/) ──solo lectura──▶ SQLite  salidas/etapa_nono/calidad_comercial.db
                                       │                         └──▶ bitácoras y reportes JSON/CSV/PNG de salidas/
                                       └─ POST /api/pipeline/ejecutar ─▶ src.pipeline.ejecutar_pipeline()  (el mismo pipeline, sin copiarlo)
```

- **El navegador nunca toca SQLite.** La API abre la base con `mode=ro` y `PRAGMA query_only`: ni un bug podría escribir desde ella.
- **No se duplica lógica:** ningún cálculo estadístico ni validación está en TypeScript. El frontend solo formatea y presenta lo que entrega la API. La API ejecuta el pipeline existente; no hay una segunda implementación.
- **Una sola carga en la base:** las tablas contienen la **última carga completada** (snapshot por ejecución, decisión de la etapa 3). La historia disponible es la tabla `ejecuciones` y las bitácoras; KOVA no reconstruye snapshots anteriores y lo dice en pantalla.
- **Lectura consistente:** el pipeline carga en una sola transacción; la API lee dentro de una transacción de lectura, así que ve la carga anterior completa o la nueva completa.

### Estructura de carpetas

```
src/api/                 config.py · db.py (solo lectura) · servicios.py (consultas) · esquemas.py (Pydantic) · ejecucion.py · main.py
frontend/src/
  components/brand/      Marca.tsx (isotipo, logotipo, marca de agua) · Fondos.tsx (6 fondos) · Ilustraciones.tsx
  components/ui/         Basicos · Controles · Drawer (panel lateral y diálogo) · Estados (vacío, error, carga)
  components/charts/     Graficos.tsx (anillo de salud, canales, serie diaria, segmentos, motivos)
  components/trace/      Trazabilidad.tsx (línea de tiempo y comparación lado a lado)
  layouts/ hooks/ services/ lib/ pages/ styles/ test/
tests/test_api.py · tests/test_contrato_fixtures.py · tests/test_overflow_conocido.py
scripts/generar_fixtures_frontend.py
```

## 4. Librerías (versiones instaladas)

| Capa | Paquete | Versión | Para qué |
|---|---|---|---|
| API | fastapi · uvicorn · httpx · starlette | 0.162.0 · 0.54.0 · 0.28.1 · 1.10.0 | servicio HTTP, servidor y cliente de pruebas |
| API | pydantic | 2.14.1 | contratos de respuesta (ya usado por el ETL) |
| Frontend | react · react-dom · react-router-dom | 19.3 · 19.3 · 7.18 | interfaz y rutas |
| Frontend | recharts | 3.10 | serie diaria (el resto de visualizaciones son SVG propios) |
| Frontend | lucide-react | 1.61 | iconos de interfaz (el isotipo NO es un icono de librería) |
| Frontend | tailwindcss (+ @tailwindcss/vite) | 4.3 | sistema de utilidades sobre tokens propios |
| Frontend | @fontsource-variable/bricolage-grotesque · dm-sans | 5.3 | tipografías (licencia OFL, empaquetadas: sin CDN) |
| Herramientas | vite · typescript · vitest · @testing-library/* · eslint | 8.3 · 6.0 · 5.0 · 16/14/7 · 10 | build, tipos, pruebas y lint |

Se evitó cualquier dependencia no justificada (sin librería de componentes ni de estado: React + hooks propios).

## 5. Decisiones de diseño

**Dirección:** *Modern Organic Tech / Premium Commerce Intelligence*: verde bosque profundo como protagonista, crema cálido de lienzo, ámbar como acento de atención (nunca de decoración vacía) y coral solo para rechazo.

| Decisión | Detalle |
|---|---|
| **Isotipo** | Cuatro módulos que convergen en un nodo ámbar: canales físico y digital × dato original y dato confiable. SVG original (`Marca.tsx`, `public/kova-isotipo.svg`); funciona como wordmark, icono de app, favicon, elemento de navegación y marca de agua |
| **Tipografía** | *Bricolage Grotesque* (titulares, con carácter) + *DM Sans* (texto y datos). Cifras tabulares (`tnum`) en KPIs, importes y tablas |
| **Navegación** | Riel lateral que **flota** con esquinas orgánicas, agrupado en Resumen · Proceso · Datos (8 destinos); marca ámbar en el activo; estado real del sistema al pie. En móvil: menú modal. Migas de pan, búsqueda global por ID y chip de estado en la barra superior |
| **Composición** | Jerarquías distintas en cada pantalla: bloque protagonista oscuro (salud), comparación de canales, serie principal, tarjetas compactas y panel de anomalías. No hay una rejilla de tarjetas iguales |
| **Fondos por sección** | Inicio/Panel: haces de curvas que convergen · Centro ETL: trayectorias que cruzan 7 marcas · Calidad: puntos que se ordenan · Cuarentena: bloques con piezas desprendidas y rayado ámbar · Catálogo: mosaico modular · Historial: arcos editoriales. Solo en cabeceras y estados vacíos: nunca detrás de tablas |
| **Movimiento** | Entrada escalonada, deslizamiento de paneles, números animados, flujo en conectores **solo mientras corre el pipeline**. `prefers-reduced-motion` desactiva todo. No hay progreso simulado |
| **Contraste (WCAG AA)** | Salvia, ámbar y coral de marca no alcanzan AA como *texto* sobre claro, así que existen variantes de texto: grafito/crema 13.7:1 · texto suave/crema 5.5:1 · ámbar-texto/blanco 6.1:1 · coral-texto/blanco 6.0:1 · menta/bosque 9.8:1 · ámbar/bosque 5.5:1. El salvia solo se usa en decoración y bordes (2.7:1). Calculado con la fórmula de WCAG |
| **Accesibilidad** | Enlace de salto, regiones con nombre, tablas con `caption` y `aria-sort`, paneles `role=dialog` con foco atrapado y Escape, `alertdialog` en la confirmación, estado `aria-live`, gráficos con descripción textual, foco visible ámbar, botones principales y filtros de ≥ 44 px (los botones de icono de paginación y descarga miden 40 px) |
| **Ilustraciones del catálogo** | Glifos por *categoría*, nunca por producto, y con la leyenda «el dataset no incluye fotografías». No se inventan fotos, marcas ni inventario |
| **Índice propio** | «Salud de origen KOVA» = registros que llegaron sin reparación de valor y sin rechazo ÷ registros de entrada (con estos datos: 879 ÷ 1,220 = 72.05 %). Se rotula como **indicador compuesto de KOVA**, se muestra su fórmula y su desglose, y se separa de las métricas oficiales (recibidos, válidas, cuarentena, tasa de aceptación 90.49 %). Si no hay datos, no se calcula |

## 6. Endpoints (`/api`)

| Método y ruta | Qué entrega | Validaciones |
|---|---|---|
| `GET /salud` | API viva y estado de la base | — |
| `GET /dashboard` | totales, índice de salud, canales, segmentos, motivos, serie diaria, categorías, anomalías, actividad | — |
| `GET /facetas` | valores para filtros (categorías, segmentos, estados, rango de fechas, códigos de rechazo) | — |
| `GET /transacciones` | página de transacciones limpias | `q` ≤ 80 car., `canal`, `segmento`, `desde`/`hasta` (fecha real y orden), `categoria`, `estado`, `orden` y `direccion` en lista blanca, `pagina` ≥ 1, `tam` 1–100 |
| `GET /transacciones/{id}` | detalle + trazabilidad por etapas + glosario + cuarentena relacionada | 404 si no existe |
| `GET /cuarentena` · `/{id_error}` | registros rechazados · detalle con todos los motivos, registro crudo y trazabilidad | `codigo` solo `[A-Z_]`, `etapa` en lista blanca |
| `GET /catalogo` | productos con estadísticas de ventas válidas | filtros y orden en lista blanca |
| `GET /calidad` | limpieza, IQR, transformación (bitácora) + perfil, MCAR/MAR, antes/después y gráficas (reportes de Leslie) | — |
| `GET /ejecuciones` · `/{lote}` | historial (incluye las fallidas) · detalle con fases, huellas, entorno y log | `lote` con formato `L…-…-xxxx` |
| `GET /reportes` · `/reportes/{carpeta}/{ruta}` | lista y descarga de reportes | solo 3 carpetas, solo `.csv .json .txt .png .md`, sin salir de la carpeta |
| `GET /pipeline/estado` | ejecutor (inactivo/en ejecución/último resultado), última ejecución y estado de las 7 fases | — |
| `POST /pipeline/ejecutar` | inicia el pipeline en segundo plano → 202 | exige `{"confirmar": true}`; rechaza orígenes no locales (403); 409 si ya corre |

Errores con forma estable `{"codigo", "mensaje"}` (422 parámetro inválido, 404, 409, 503 base ausente o sin esquema, 500 genérico sin detalles internos). Todas las consultas son parametrizadas; ninguna ruta acepta SQL ni rutas de archivo; CORS solo para `localhost`/`127.0.0.1` (puertos de Vite y de la API).

## 7. Integración con Python

- `src/api/servicios.py` solo **lee**: tablas `transacciones_limpias`, `cuarentena_errores`, `catalogo_productos`, `ejecuciones`, y los archivos `bitacoras/`, `logs/` y `salidas/etapa_*/` que ya generaba el pipeline. No se cambió una línea de `src/calidad`, `src/integracion`, `src/validacion`, `src/persistencia` ni `src/pipeline.py`.
- El Centro ETL llama a `ejecutar_pipeline()` en un hilo con candado no bloqueante. El estado «en ejecución» se consulta cada 1.5 s; al terminar, las pantallas vuelven a consultar solas.
- **Fases oficiales ↔ etapas internas:** 1 Diagnóstico = extracción + perfilado · 2 Faltantes = homologación + limpieza · 3 Outliers = IQR · 4 Integración · 5 Transformación · 6 Pydantic y cuarentena · 7 Carga. El diagrama sigue el **orden real de ejecución** (la integración corre antes que el IQR) y lo explica en pantalla. El estado y la duración de cada fase salen de la bitácora medida.
- **Trazabilidad por transacción:** «Dato original → Homologación → Correcciones → Capping → Transformación → Validación → Resultado», construida solo con campos persistidos (`registro_original`, `*_origen`, `*_cap`, `correcciones`…). Una vista «lado a lado» compara original · normalizado · corregido · con capping · final. Para la cuarentena solo existen tres etapas documentables (original, detección, resultado) y solo esas se muestran.

## 8. Advertencia de desbordamiento numérico (investigada)

`RuntimeWarning: overflow encountered in multiply` aparece con el caso de estrés E30 (`total_amount = 1e308`). **Causa:** `recalcular_montos` resume el factor de inconsistencia con `(monto / calculado).round(4)`; con un cociente de ~1e306, `round(4)` multiplica por 10⁴ y desborda `float64` a `inf`. **Efecto:** solo la clave de diagnóstico `factores_inconsistencia` registra `{'inf': 1}`; el importe se corrige a 100.00, el original se conserva y el registro es válido. **Decisión:** no se modificó el módulo estadístico; `tests/test_overflow_conocido.py` fija el comportamiento (y comprueba que los datos oficiales dan `{80.0: 12}` sin advertencias).

## 9. Pruebas ejecutadas

| Suite | Resultado | Cobertura |
|---|---|---|
| `python -m pytest` (toda la batería) | **442 passed** | 357 de las etapas 1–3 + 85 nuevas |
| `tests/test_api.py` | 81 | contratos y valores contra SQLite real, paginación, filtros, orden, parámetros inválidos (422), inyección SQL y comodines, base inexistente/vacía (503), solo lectura, ejecución fallida no mostrada como exitosa, descargas y *path traversal*, confirmación, origen no local, ejecución simultánea (409), candado liberado tras fallo, ejecución real desde la API, CORS, error 500 opaco, frontend compilado |
| `tests/test_contrato_fixtures.py` | 1 | si la API cambia de forma, los fixtures de React quedan marcados como desactualizados |
| `tests/test_overflow_conocido.py` | 3 | investigación del desbordamiento |
| `npm test` (Vitest + Testing Library) | **45 passed** | formato MXN/fechas, cliente de la API (errores, abortos, conexión caída), navegación, accesibilidad estructural, panel con datos reales, estados de error/vacío/sin base, transacciones (filtros, orden, panel de recorrido, Escape), cuarentena (chips, detalle, solo lectura), catálogo, Centro ETL (diagrama, confirmación, POST, 409, sin progreso inventado, fallo), historial, reportes, calidad (MCAR con su advertencia) |
| `npx tsc --noEmit` · `npx eslint .` · `npm run build` | sin errores ni advertencias | build de producción en < 1 s; el gráfico de Recharts va en un *chunk* aparte |

Los fixtures de React son **respuestas reales** de la API (`python scripts/generar_fixtures_frontend.py`), no objetos escritos a mano.

## 9.1 Hallazgos corregidos durante el desarrollo
- El anillo de salud mostraba todo en coral: una clase CSS de animación pisaba `stroke-dasharray`. Corregido.
- Los paneles laterales quedaban *debajo* de la barra superior (un ancestro con animación crea su propio contexto de apilamiento). Ahora usan *portal* a `document.body`.
- Empates de segundos en `ejecuciones.inicio` podían elegir mal «la última» ejecución: se desempata con `rowid`.
- Desbordes horizontales en móvil (ETL, Historial, Calidad): los hijos de rejillas ahora pueden encogerse.
- El diagrama del ETL mostraba «620/600/50» fijos: ahora usa los conteos de la última ejecución.

## 10. Limitaciones y decisiones técnicas

| # | Limitación / decisión |
|---|---|
| L1 | **Sin progreso granular:** `ejecutar_pipeline` solo devuelve el resultado al final. Mientras corre, KOVA muestra «en ejecución» y el tiempo transcurrido, no porcentajes ni fases «completándose». Las duraciones por fase se muestran al terminar |
| L2 | **Una sola carga en SQLite:** no hay snapshots históricos; el historial muestra conteos, estado y bitácora por ejecución |
| L3 | **Ejecutar el pipeline reescribe `salidas/etapa_nono/`** (reportes y una bitácora nueva por ejecución) y el contenido de la base. Es el mismo comportamiento que `python -m src.pipeline`; por eso la confirmación lo advierte |
| L4 | **Los reportes de Leslie** (perfil inicial, MCAR/MAR, antes/después, boxplots) se leen de `salidas/etapa_leslie/` (estáticos); si esa carpeta no existe, la pantalla de Calidad lo indica y sigue funcionando con la bitácora |
| L5 | **Aplicación local y académica:** sin autenticación, enlazada a `127.0.0.1`. No debe exponerse a internet |
| L6 | **Una sola ejecución a la vez dentro del proceso API**; entre procesos distintos protege `BEGIN IMMEDIATE` de SQLite (no probado con dos procesos simultáneos) |
| L7 | La suite de Python se verificó con el `.venv` del proyecto (pandas 3.1.0). Las 85 pruebas nuevas necesitan FastAPI/httpx: `pip install -r requirements.txt` |
| L8 | Los *warnings* de `httpx` en el `TestClient` de Starlette (deprecación) son externos |
| L9 | `npm audit`: 0 vulnerabilidades reportadas al instalar |
| L10 | El tamaño del *chunk* de Recharts (~370 kB, ~108 kB gzip) está aislado en el Panel; no afecta la carga de las demás pantallas |

## 11. Instrucciones de ejecución (Windows PowerShell)

**Una sola vez:**

```powershell
cd "C:\Users\Leslie Valadez\Documents\Proyectos\sistema-calidad-datos-comerciales"
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

**Terminal 1 · API** (si no existe la base, KOVA te llevará al Centro ETL para generarla; o corre antes `python -m src.pipeline`):

```powershell
cd "C:\Users\Leslie Valadez\Documents\Proyectos\sistema-calidad-datos-comerciales"
.venv\Scripts\Activate.ps1
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 · interfaz:**

```powershell
cd "C:\Users\Leslie Valadez\Documents\Proyectos\sistema-calidad-datos-comerciales\frontend"
npm run dev
```

Abre **http://127.0.0.1:5173**. Alternativa con una sola terminal: `cd frontend; npm run build` y abre **http://127.0.0.1:8000** (FastAPI sirve `frontend/dist`).

**Verificaciones:**

```powershell
python -m pytest                                  # 442 pruebas de Python
cd frontend; npm run lint; npm test; npm run build
python scripts\generar_fixtures_frontend.py        # solo si cambia la forma de la API
```

Variables opcionales para probar sin tocar la base oficial: `$env:KOVA_BD="C:\ruta\prueba.db"; $env:KOVA_SALIDA="C:\ruta\salida"` antes de iniciar uvicorn.

## 12. Pendientes

1. Tomar las capturas (`evidencias/GUIA_CAPTURAS_FRONTEND.md`).
2. Decisiones heredadas: zona horaria del epoch (A8), 12 totales ×80 (A9), IQR antes/después de convertir (A2), y si el `.db` va en el repositorio.
3. Revisar la rama, commit autorizado (`feat: etapa 4 frontend KOVA - Equipo`) y merge acordado. Los archivos `salidas/etapa_leslie|yerik|nono` que aparecen modificados provienen de ejecuciones anteriores del pipeline: no son de esta etapa y no deben incluirse sin decisión.
