# GUÍA DE TRABAJO · INGENIERA 1: LESLIE
## Calidad, Nulos y Outliers

**Entregable clave (según la guía del profesor):** funciones de limpieza + reporte comparativo de calidad antes/después.
**Rúbrica que defiendes directamente:** criterio 2, Calidad de Datos (20 pts). También aportas al criterio 1 (justificaciones de `REGLAS_DE_NEGOCIO.md`).
**Tus archivos (solo tú los editas):** `src/calidad/perfilado.py`, `src/calidad/limpieza.py`, `src/calidad/outliers.py`, `src/calidad/reporte.py`, `tests/test_calidad.py`.
**Archivos compartidos que lees pero no cambias sin acuerdo:** `src/config.py`, `src/contratos.py`.

---

## 0. Tu lugar en el pipeline

Participas en **tres momentos**, y en cada uno recibes un DataFrame y devuelves otro:

| Momento | Recibes de | Función | Entregas a |
|---|---|---|---|
| F1 · Diagnóstico "antes" | `extraer_fuentes()` (Yerik) | `perfilar_fuentes(fuentes)` | reporte (dict + CSV) |
| F2 · Faltantes e imputación | `homologar_columnas()` (Yerik) | `limpiar_registros(df)` | `integrar()` (Yerik) |
| F3 · Outliers IQR | `integrar()` (Yerik) | `tratar_outliers(df)` | `transformar()` (Yerik) |
| F1 bis · "después" | base de datos (Nono) | `comparar_calidad(...)` | reporte final |

**Regla de oro de tu módulo:** tú **no eliminas filas**. Corriges, imputas y **marcas** con banderas. Quien manda a cuarentena es Nono (R1.3). Así el conteo siempre cuadra.

---

## 1. Qué debes analizar (Fase 1)

Ya existe un diagnóstico de referencia en `diagnostico/diagnostico_inicial.py`. Tu tarea es convertirlo en **funciones reutilizables** dentro de `src/calidad/perfilado.py`, para que el mismo perfil se pueda calcular **antes** (archivos crudos) y **después** (tablas finales).

### 1.1 Métricas obligatorias por columna

| Métrica | Fórmula / cómo se calcula | Ejemplo real |
|---|---|---|
| Completitud | `100 × (1 − nulos / filas)` | `id_cliente`: 100 × (1 − 127/620) = **79.52 %** |
| % de nulos | `nulos / filas × 100` (cuenta también `""` y espacios) | `customer_email`: 20/600 = **3.33 %** (15 null + 5 `""`) |
| Unicidad | `df.duplicated().sum()` (duplicados exactos) | POS: **20**; web: **0** |
| Tipos inferidos | `df.dtypes` con lectura normal de pandas | `cantidad` → int64; `order_timestamp` → object (mezcla int y str) |
| Completitud global | `100 × (1 − total_nulos / (filas × columnas))` | POS **97.15 %** · web **98.53 %** |

> ⚠️ **Detalle técnico:** si lees el CSV con `pd.read_csv()` normal, la cadena vacía se convierte en `NaN`. En el JSON, en cambio, `""` **no** es `null`. Por eso hay que contar como faltante `isna() | str.strip() == ""`. Si no lo haces, reportarás 15 correos faltantes en lugar de 20.

### 1.2 Funciones a programar en `perfilado.py`

```python
def es_vacio(serie: pd.Series) -> pd.Series:
    """True si el valor es nulo o texto vacío/espacios."""

def perfilar_dataframe(df: pd.DataFrame, nombre: str) -> dict:
    """Devuelve {'fuente', 'filas', 'columnas', 'dtypes', 'nulos', 'pct_nulos',
    'completitud_global_pct', 'duplicados_exactos'}."""

def perfilar_fuentes(fuentes: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Aplica perfilar_dataframe a 'fisica', 'online' y 'catalogo'."""

def clasificar_faltantes(df, col_faltante: str, cols_grupo: list[str]) -> dict:
    """Prueba χ² del indicador de faltante contra cada variable de grupo.
    Devuelve p-valores y la clasificación 'MCAR' o 'MAR(<col>)'."""

def perfil_a_tabla(perfil: dict) -> pd.DataFrame:
    """Convierte el perfil en una tabla columna | dtype | nulos | % (para el reporte)."""
```

---

## 2. Columnas que necesitan limpieza (tu parte)

| Columna unificada | Problema | Casos | Acción | Regla |
|---|---|---|---|---|
| (fila completa) | duplicado exacto | 20 (POS) | `es_duplicado = True` | R2.3 |
| `id_transaccion` | mismo ID con contenido distinto | 0 | `es_id_conflicto = True` | R2.4 |
| `monto_total` | nulo y recalculable | 32 (POS) | `cantidad × precio_unitario` | R6.2 |
| `monto_total` | ≠ cantidad × precio (×80) | 12 (web) | recalcular + guardar original | R6.3 |
| `id_cliente` | faltante (POS) | 127 | `ANONIMO` | R3.8 |
| `email_cliente` | `null` o `""` (web) | 20 | `SIN_CORREO` | R3.8 |
| `direccion_envio` | faltante (web) | 77 | `SIN_DIRECCION` | R3.8 |
| `cantidad` | faltante | 0 (sí en estrés) | mediana por canal | R3.5 |
| `cantidad` | atípica (99, 500) | 13 (POS) | `cantidad_cap = 8` | R5.3 |
| `monto_total_mxn` | atípico | 80 (referencia) | `monto_total_mxn_cap = LS` | R5.4 |

**Lo que NO es tuyo:** las fechas, las monedas y los huérfanos (Yerik); los correos malformados y las cantidades ≤ 0 (Nono los rechaza con Pydantic). Tú solo **excluyes** las cantidades ≤ 0 de tus cálculos estadísticos.

---

## 3. Fase 2 paso a paso: `src/calidad/limpieza.py`

Todas las funciones reciben `df` y devuelven **una copia** (`df = df.copy()` al inicio). Cada corrección agrega un código a la lista `correcciones` de la fila.

### Paso 3.1 · Marcar duplicados exactos

```python
def marcar_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # registro_original es el JSON de la fila cruda: dos filas idénticas tienen el mismo texto
    df["es_duplicado"] = df.duplicated(subset=["origen", "registro_original"], keep="first")
    # mismo ID con contenido distinto → conflicto (ambas filas)
    contenidos = df[~df["es_duplicado"]].groupby("id_transaccion")["registro_original"].nunique()
    conflictos = contenidos[contenidos > 1].index
    df["es_id_conflicto"] = df["id_transaccion"].isin(conflictos) & ~df["es_duplicado"]
    return df
```

**Ejemplo real:** `POS-2026-0001` aparece en la fila de datos 1 y otra vez en la **613**, con todos los campos iguales (13-09-2026, Colima Centro, PROD-010, 1 × 1227.12). La fila 1 se conserva y la 613 queda con `es_duplicado = True`. **Resultado esperado:** 20 filas marcadas (las filas 601–620), 0 conflictos.

### Paso 3.2 · Reconstruir importes

```python
def recalcular_montos(df: pd.DataFrame, tolerancia: float = 0.01) -> pd.DataFrame:
    df = df.copy()
    df["monto_total_origen"] = df["monto_total"]          # trazabilidad: valor crudo intacto
    calculado = (df["cantidad"] * df["precio_unitario"]).round(2)
    se_puede = df["cantidad"].notna() & df["precio_unitario"].notna() & (df["cantidad"] > 0)

    nulo = df["monto_total"].isna() & se_puede
    inconsistente = df["monto_total"].notna() & se_puede & ((df["monto_total"] - calculado).abs() > tolerancia)

    df.loc[nulo | inconsistente, "monto_total"] = calculado[nulo | inconsistente]
    _agregar_correccion(df, nulo, "MONTO_RECALCULADO_NULO")
    _agregar_correccion(df, inconsistente, "MONTO_RECALCULADO_INCONSISTENTE")
    return df
```

**Ejemplos reales:**

| Registro | cantidad | precio | monto crudo | monto corregido | Código |
|---|---|---|---|---|---|
| `POS-2026-0075` | 1 | 1,437.14 | *(vacío)* | 1,437.14 | `MONTO_RECALCULADO_NULO` |
| `POS-2026-0082` | 2 | 3,306.99 | *(vacío)* | 6,613.98 | `MONTO_RECALCULADO_NULO` |
| `WEB-00508` | 3 | 3,443.17 MXN | 826,360.80 | 10,329.51 | `MONTO_RECALCULADO_INCONSISTENTE` |
| `WEB-00237` | 1 | 216.31 USD | 17,304.80 | 216.31 (USD, Yerik lo convierte después) | `MONTO_RECALCULADO_INCONSISTENTE` |

**Resultado esperado:** 32 `MONTO_RECALCULADO_NULO` + 12 `MONTO_RECALCULADO_INCONSISTENTE`.

> **Por qué es correcto recalcular los ×80:** el precio coincide con el catálogo, las unidades están en el rango normal (1–3) y el total es **exactamente** 80 veces el producto. La variable derivada está corrupta, no las primarias. El valor original queda en `monto_total_origen`, así que no se pierde nada. *(Esta decisión está marcada como "consultar al docente", ambigüedad A9.)*

### Paso 3.3 · Imputar categóricas con etiquetas controladas

```python
ETIQUETAS = {  # va en src/config.py
    ("FISICA", "id_cliente"): "ANONIMO",
    ("ONLINE", "email_cliente"): "SIN_CORREO",
    ("ONLINE", "direccion_envio"): "SIN_DIRECCION",
}

def imputar_categoricas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for (origen, col), etiqueta in ETIQUETAS.items():
        mask = (df["origen"] == origen) & es_vacio(df[col])
        df.loc[mask, col] = etiqueta
        _agregar_correccion(df, mask, f"IMPUTADO_{col.upper()}")
    return df
```

Fíjate en que **solo se imputa dentro del canal donde la columna existe**. `id_cliente` en ventas online queda `None`, porque no es un faltante sino un "no aplica" (R3.9).

**Ejemplos reales:** `POS-2026-0005` (id_cliente vacío) → `ANONIMO`; `WEB-00040` (correo `""`) → `SIN_CORREO`; `WEB-00003` (dirección `null`) → `SIN_DIRECCION`.
**Resultado esperado:** 127 + 20 + 77 = **224** imputaciones categóricas.

### Paso 3.4 · Imputar numéricas con la mediana

```python
def imputar_mediana(df: pd.DataFrame, columna: str = "cantidad") -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    base = df[~df["es_duplicado"] & (df[columna] > 0)]          # en F2 aún no existe en_catalogo
    medianas = base.groupby("origen")[columna].median().to_dict()  # {'FISICA': 2.0, 'ONLINE': 1.0}
    faltante = df[columna].isna() & ~df["alertas"].apply(lambda a: "CANTIDAD_NO_NUMERICA" in a)
    df.loc[faltante, columna] = df.loc[faltante, "origen"].map(medianas)
    _agregar_correccion(df, faltante, f"IMPUTADO_MEDIANA_{columna.upper()}")
    return df, medianas
```

- **En los datos oficiales hay 0 cantidades faltantes.** No inventes casos: en el reporte escribe "0 imputaciones por mediana en los datos oficiales; la función se comprobó con el dataset de estrés de Nono".
- Una cantidad **no numérica** (`"dos"`) **no** se imputa: es un dato corrupto, no faltante. Yerik la marca con la alerta `CANTIDAD_NO_NUMERICA` y Nono la rechaza.
- Después de imputar la cantidad, vuelve a llamar a `recalcular_montos()` para completar el monto.

### Paso 3.5 · Función de la etapa (la que llama el orquestador)

```python
def limpiar_registros(df_homologado: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = marcar_duplicados(df_homologado)
    df, medianas = imputar_mediana(df, "cantidad")
    df = recalcular_montos(df)
    df = imputar_categoricas(df)
    bitacora = {"medianas": medianas, "conteo_correcciones": _contar_correcciones(df)}
    return df, bitacora
```

---

## 4. Clasificar y justificar los faltantes (MCAR / MAR)

### 4.1 Procedimiento

1. Crear el indicador `falta = es_vacio(df[col])`.
2. Para cada variable categórica observada (sucursal, método de pago, estado, pasarela, moneda), construir `pd.crosstab(df[grupo], falta)`.
3. Aplicar `scipy.stats.chi2_contingency(tabla)`. Con **p ≥ 0.05**, no hay evidencia de dependencia.
4. Si todas dan p ≥ 0.05, la columna es **MCAR**. Si alguna da p < 0.05, es **MAR respecto a esa variable**.
5. Declarar la limitación: MNAR (que la ausencia dependa del propio valor faltante) **no se puede probar** con los datos observados.

### 4.2 Resultados reales (ya calculados por el diagnóstico)

| Columna | vs | % faltante por grupo | χ² | gl | p | Conclusión |
|---|---|---|---|---|---|---|
| `id_cliente` | sucursal | 18.1 % – 23.1 % | 1.36 | 3 | 0.714 | MCAR |
| `id_cliente` | método de pago | 16.6 % – 23.4 % | 2.92 | 4 | 0.571 | MCAR |
| `monto_total_mxn` | sucursal | 3.1 % – 6.8 % | 2.48 | 3 | 0.479 | MCAR |
| `monto_total_mxn` | método de pago | 2.8 % – 7.1 % | 2.94 | 4 | 0.569 | MCAR |
| `customer_email` | pasarela | 2.2 % – 4.1 % | 1.09 | 3 | 0.779 | MCAR |
| `customer_email` | moneda | 2.7 % / 4.7 % | 1.01 | 1 | 0.314 | MCAR |
| `shipping_address` | estado | 8.1 % – 18.8 % | 5.07 | 4 | 0.280 | MCAR |
| `shipping_address` | pasarela | 9.6 % – 14.3 % | 2.20 | 3 | 0.532 | MCAR |

### 4.3 Cómo redactar la justificación (texto modelo para el reporte)

> *"El 20.48 % de `id_cliente` está ausente. La proporción de ausencias es similar entre sucursales (18.1 %–23.1 %) y métodos de pago (16.6 %–23.4 %), y la prueba χ² no detecta dependencia (p = 0.714 y p = 0.571), por lo que se clasifica como MCAR. Como es un identificador y no una medida, no tiene sentido estadístico imputarlo con una moda; se usa la etiqueta controlada `ANONIMO`, que conserva la venta sin inventar un cliente."*

> *"Se imputa la mediana y no la media porque las variables numéricas están fuertemente sesgadas: en la tienda física, `monto_total_mxn` tiene media de $16,586.74 y mediana de $3,506.37 (asimetría 14.08), y `cantidad` tiene media de 8.58 y mediana de 2 (asimetría 9.38). Trece tickets con 99 o 500 unidades arrastran la media. La mediana, al depender solo del orden, no se ve afectada por esos extremos."*

---

## 5. Fase 3: IQR y capping (`src/calidad/outliers.py`)

### 5.1 Cómo se calcula (paso a paso con datos reales)

**Cantidad, tienda física** (base: 562 registros, sin duplicados, sin cantidad ≤ 0 y sin huérfanos):

1. Q1 = percentil 25 = **1**
2. Q3 = percentil 75 = **4**
3. IQR = Q3 − Q1 = **3**
4. LI = 1 − 1.5 × 3 = **−3.5** (no aplica, porque ya excluimos las cantidades ≤ 0)
5. LS = 4 + 1.5 × 3 = **8.5**. Como la cantidad es entera, el tope es `floor(8.5)` = **8**
6. Por encima del límite: **13** registros (siete de 99 y seis de 500)

**Cantidad, tienda online:** Q1 = 1, Q3 = 2, LS = 3.5, máximo = 3, así que **0 outliers**. Ese resultado también se reporta.

**Monto unificado en MXN** (se calcula sobre `cantidad_cap × precio_unitario_mxn`, ya convertido por Yerik):

| Q1 | Q3 | IQR | LI | LS | Fuera de límite |
|---|---|---|---|---|---|
| 1,563.78 | 5,751.34 | 4,187.56 | −4,717.56 | **12,032.68** | **80** |

> ⚠️ Usa `serie.quantile(0.25)` y `serie.quantile(0.75)` (interpolación lineal, el valor por omisión de pandas) para obtener estos números. El LS del monto también depende de cómo Yerik redondea los precios convertidos: con `Decimal` + `ROUND_HALF_UP` da 12,032.68, y con el `round()` de numpy, 12,032.63. Acepta una diferencia de ±0.10 y explícala si te preguntan. Con otro método de cuartiles los límites cambian un poco y tendrás que explicarlo.

### 5.2 Funciones

```python
def calcular_limites_iqr(serie: pd.Series, factor: float = FACTOR_IQR) -> dict:
    s = pd.to_numeric(serie, errors="coerce").dropna()
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return {"n": len(s), "Q1": q1, "Q3": q3, "IQR": iqr,
            "LI": q1 - factor * iqr, "LS": q3 + factor * iqr,
            "outliers": int(((s < q1 - factor * iqr) | (s > q3 + factor * iqr)).sum())}

def mascara_base_estadistica(df: pd.DataFrame) -> pd.Series:
    return ~df["es_duplicado"] & (df["cantidad"] > 0) & df["en_catalogo"]

def aplicar_capping_cantidad(df) -> tuple[pd.DataFrame, dict]:
    """Por canal; tope = floor(LS); crea cantidad_cap y es_outlier_cantidad."""

def aplicar_capping_monto(df) -> tuple[pd.DataFrame, dict]:
    """monto_base = cantidad_cap × precio_unitario_mxn; LS sobre la base unificada;
    crea monto_total_mxn_cap = clip(monto_base, max(LI, 0), LS) y es_outlier_monto."""

def tratar_outliers(df_integrado) -> tuple[pd.DataFrame, dict]:
    df, lim_cant = aplicar_capping_cantidad(df_integrado)
    df, lim_monto = aplicar_capping_monto(df)
    return df, {"cantidad": lim_cant, "monto": lim_monto}
```

Los límites se calculan **con la base estadística**, pero el `clip()` se aplica **a todas las filas** (también a las que irán a cuarentena), para que ninguna fila quede con columnas vacías.

### 5.3 Ejemplos reales del efecto

| Registro | cantidad (real) | `cantidad_cap` | `monto_total_mxn` (real) | `monto_total_mxn_cap` | Banderas |
|---|---|---|---|---|---|
| `POS-2026-0031` (PROD-027, $1,025.98) | 500 | 8 | 512,990.00 | 8,207.84 | outlier de cantidad |
| `POS-2026-0021` (PROD-020, $2,107.06) | 99 | 8 | 208,598.94 | 12,032.68 | outlier de cantidad **y** de monto (8 × 2,107.06 = 16,856.48 > LS) |
| `WEB-00508` (3 × $3,443.17) | 3 | 3 | 10,329.51 | 10,329.51 | ninguna |
| `POS-2026-0001` | 1 | 1 | 1,227.12 | 1,227.12 | ninguna |

> **Por qué columnas `_cap` separadas:** la rúbrica pide tratar los outliers "sin pérdida destructiva de datos válidos" y la consigna del equipo prohíbe modificar valores financieros sin trazabilidad. La venta de 500 unidades **existió en el registro**: la conservamos en `cantidad` y `monto_total_mxn`. Para estadística, KPI, Min-Max y segmentos se usan las columnas `_cap`.

---

## 6. Qué le entregas a Yerik (contrato de salida)

### Salida de F2 → entrada de `integrar()` (Yerik)

Todas las columnas del esquema homologado (`GUIA_GENERAL_PROYECTO.md §9.1`) **más**:

| Columna | Tipo | Contenido |
|---|---|---|
| `es_duplicado` | bool | True en las 20 filas repetidas |
| `es_id_conflicto` | bool | False en los datos oficiales |
| `monto_total_origen` | float / None | valor crudo, nunca se modifica |
| `monto_total` | float / None | corregido, en la **moneda original** |
| `cantidad` | float / None | imputada si faltaba |
| `id_cliente`, `email_cliente`, `direccion_envio` | str / None | con etiquetas controladas |
| `correcciones` | list[str] | códigos de corrección aplicados |

**Mismo número de filas que la entrada (1,220).** Si cambia, hay un error.

### Salida de F3 → entrada de `transformar()` (Yerik)

Lo anterior + lo de Yerik + `cantidad_cap` (int), `monto_total_mxn_cap` (float), `es_outlier_cantidad` (bool), `es_outlier_monto` (bool), y el dict de límites IQR (para el reporte y para que Nono lo guarde en la bitácora).

---

## 7. Reporte comparativo antes/después (`src/calidad/reporte.py`)

### 7.1 Funciones

```python
def comparar_calidad(perfil_antes: dict, perfil_despues: dict) -> pd.DataFrame:
    """Tabla: métrica | antes | después | cambio."""

def graficar_boxplot_antes_despues(antes: pd.Series, despues: pd.Series, titulo: str, ruta: Path) -> None:
    """Dos boxplots lado a lado (escala log si hace falta). Guardar en salidas/graficas/."""

def generar_reporte_calidad(...) -> Path:
    """Escribe salidas/reporte_calidad.md con las tablas y las rutas de las gráficas."""
```

### 7.2 Tabla que debe producir (los valores "antes" ya son reales)

| Métrica | Antes (real) | Después (esperado) | Cómo se mide "después" |
|---|---|---|---|
| Duplicados exactos (POS) | 20 | 0 | en `transacciones_limpias` |
| Completitud `id_cliente` (POS) | 79.52 % | 100 % | 0 nulos (con `ANONIMO`) |
| Completitud `monto_total_mxn` | 94.84 % (POS) | 100 % | 0 nulos |
| Completitud `email_cliente` (web) | 96.67 % | 100 % | `SIN_CORREO` + malformados en cuarentena |
| Completitud `direccion_envio` (web) | 87.17 % | 100 % | `SIN_DIRECCION` |
| Montos inconsistentes | 12 (web) | 0 | `|monto − cant × precio| > 0.01` |
| Cantidades ≤ 0 | 11 | 0 | en cuarentena |
| Formatos de fecha distintos | 5 | 1 (ISO) | regex |
| Monedas | 2 | 1 (MXN) | `moneda_original` se conserva aparte |
| Productos huérfanos | 62 | 0 | en cuarentena |
| Máximo de cantidad (POS) | 500 | 8 en `cantidad_cap` | — |
| Asimetría del monto (POS crudo) | 14.08 | **PENDIENTE** (calcular sobre `monto_total_mxn_cap`) | `serie.skew()` |
| Media / mediana del monto (POS) | 16,586.74 / 3,506.37 | **PENDIENTE** | — |

> Los valores "Después" se llenan **con la ejecución real**. Si un valor no coincide con el esperado, no lo cambies a mano: investiga la causa y anótala.

---

## 8. Cómo verificar que funciona (`tests/test_calidad.py`)

| Prueba | Entrada | Resultado esperado |
|---|---|---|
| `test_iqr_cantidad_fisica` | cantidades de la base POS | Q1 = 1, Q3 = 4, LS = 8.5, outliers = 13 |
| `test_iqr_conocido` | `[1,2,3,4,5,6,7,8,9,100]` | Q1 = 3.25, Q3 = 7.75, LS = 14.5 |
| `test_capping_no_borra_filas` | DataFrame de 10 filas | salen 10 filas; `cantidad` original intacta |
| `test_recalculo_nulo` | cantidad 2, precio 3306.99, monto None | 6613.98 + código |
| `test_recalculo_x80` | registro `WEB-00508` | 10,329.51; `monto_total_origen` = 826,360.80 |
| `test_no_imputa_no_numerico` | cantidad `"dos"` con alerta | sigue sin valor (no se imputa) |
| `test_mediana_por_canal` | física `[1,2,2,5,None]`, online `[1,1,3,None]` | física 2.0, online 1.0 |
| `test_etiquetas_solo_su_canal` | fila online con `id_cliente` None | sigue None (no `ANONIMO`) |
| `test_duplicados_reales` | POS crudo homologado | 20 marcados; `POS-2026-0001` fila 1 conservada |
| `test_funciones_puras` | cualquier df | el df de entrada no cambia (`pd.testing.assert_frame_equal`) |

Ejecutar con `pytest tests/test_calidad.py -v`.

---

## 9. Evidencias y capturas que debes presentar

> No pegues capturas inventadas. Cada espacio se llena con la captura de **tu** ejecución real.

> 📸 **Figura L-1.** *Capturar:* consola con la salida de `perfilar_fuentes()` para la tienda física (tabla columna / dtype / nulos / %). *Pie:* "Perfil inicial de calidad de `ventas_tienda_fisica.csv` (620 × 9)".

> 📸 **Figura L-2.** *Capturar:* lo mismo para `ventas_online.json`, mostrando los 20 correos faltantes (15 null + 5 vacíos). *Pie:* "Perfil inicial de `ventas_online.json`".

> 📸 **Figura L-3.** *Capturar:* tabla de pruebas χ² (columna, grupo, p-valor, conclusión). *Pie:* "Clasificación MCAR/MAR de las variables con faltantes".

> 📸 **Figura L-4.** *Capturar:* `df[df.es_duplicado][['id_transaccion','id_fila_origen']]` con los 20 duplicados. *Pie:* "Duplicados exactos detectados en el POS".

> 📸 **Figura L-5.** *Capturar:* antes/después de `WEB-00508` y `POS-2026-0075` (columnas `monto_total_origen`, `monto_total`, `correcciones`). *Pie:* "Reconstrucción de importes con trazabilidad".

> 📸 **Figura L-6.** *Capturar:* impresión de los límites IQR (Q1, Q3, IQR, LS) para la cantidad y el monto. *Pie:* "Límites IQR con factor 1.5".

> 📸 **Figura L-7.** *Capturar:* gráfica `salidas/graficas/boxplot_cantidad_antes_despues.png`. *Pie:* "Distribución de la cantidad antes y después del capping".

> 📸 **Figura L-8.** *Capturar:* gráfica del monto antes/después (eje log si los bots aplastan la caja). *Pie:* "Distribución del importe antes y después del capping".

> 📸 **Figura L-9.** *Capturar:* `pytest tests/test_calidad.py -v` en verde. *Pie:* "Pruebas unitarias del módulo de calidad".

> 📸 **Figura L-10.** *Capturar:* tabla final antes/después. *Pie:* "Comparativo de calidad antes y después del pipeline".

---

## 10. Qué debes explicar en la defensa oral

**Tu guion (1.5 a 2 minutos):**
1. "Medí la calidad antes de tocar nada: el POS tenía 97.15 % de completitud, 20 duplicados y 32 totales vacíos; la web, 20 correos faltantes y 77 direcciones vacías."
2. "Clasifiqué los faltantes con χ²: todos dieron p > 0.05, es decir, MCAR."
3. "Imputé con mediana y no con media porque la media del monto era 4.7 veces la mediana por culpa de los bots."
4. "Reconstruí 44 importes con `cantidad × precio`, guardando siempre el valor original."
5. "Apliqué IQR con 1.5: la cantidad tenía LS = 8.5, así que topé a 8 los 13 bots de 99 y 500 unidades, sin borrar ninguna fila."
6. "Al final comparo antes y después." *(mostrar tabla y boxplot)*

**Preguntas probables y respuesta corta:**

| Pregunta | Respuesta |
|---|---|
| ¿Por qué mediana y no media? | Distribución sesgada (asimetría 14.08 en el monto POS); la media 16,586 está inflada por los bots; la mediana 3,506 es robusta. |
| ¿Qué es MCAR y cómo lo demostraste? | La ausencia no depende de ninguna variable. Prueba χ² del indicador de faltante contra los grupos, p ≥ 0.05. No se puede descartar MNAR. |
| ¿Diferencia entre MCAR y MAR? | MAR: la ausencia depende de otra variable observada (por ejemplo, más faltantes en una sucursal). |
| ¿Por qué no eliminaste los outliers? | La guía pide capping; eliminar pierde ventas válidas. Además, el valor original se conserva en otra columna. |
| ¿Qué es Winsorizing? | Reemplazar los valores fuera de los límites por el límite, en lugar de eliminarlos. |
| ¿Por qué el tope es 8 y no 8.5? | La cantidad es entera; `floor(LS)` mantiene el tipo sin superar el límite. |
| ¿Por qué el IQR del monto se calcula después de convertir? | Mezclar USD y MXN en una misma distribución da cuartiles sin sentido. |
| ¿Qué pasa si falta la cantidad **y** el monto? | Mediana de la cantidad por canal y después se recalcula el monto. Hoy son 0 casos; se probó con datos de estrés. |
| ¿Por qué las cantidades ≤ 0 no se recortan al límite inferior? | Son valores **imposibles**, no atípicos; la guía ordena eliminarlas, y nosotros las mandamos a cuarentena. |
| ¿Recalcular el ×80 no es "inventar"? | No: precio (verificado con el catálogo) y unidades son coherentes; solo la derivada estaba alterada. El original queda guardado. |

**Prepárate también para una pregunta de los otros módulos:** cómo se convierte el epoch a fecha (Yerik) y qué hace `rollback()` (Nono).
