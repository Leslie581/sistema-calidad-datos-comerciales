# GUÍA DE TRABAJO · INGENIERO 2: YERIK
## Transformación e Integración

**Entregable clave (según la guía del profesor):** módulo de integración multifuente y normalización de variables.
**Rúbrica que defiendes directamente:** criterio 3, Integración y Transformación (20 pts).
**Tus archivos (solo tú los editas):** `src/extraccion.py`, `src/integracion/homologacion.py`, `src/integracion/fechas.py`, `src/integracion/moneda.py`, `src/integracion/catalogo.py`, `src/integracion/transformacion.py`, `tests/test_integracion.py`.
**Archivos compartidos:** `src/config.py`, `src/contratos.py` (cambios solo por acuerdo).

---

## 0. Tu lugar en el pipeline

Eres quien **más veces** aparece en el flujo, porque conviertes dos fuentes distintas en una sola tabla coherente:

| Paso | Recibes | Función | Entregas a |
|---|---|---|---|
| Extracción | rutas de `datos/crudos/` | `extraer_fuentes()` | Leslie (perfil) y tu homologación |
| Homologación | dict de fuentes crudas | `homologar_columnas()` | Leslie (`limpiar_registros`) |
| F4 · Integración | `df_limpio` de Leslie + catálogo | `integrar()` | Leslie (`tratar_outliers`) |
| F5 · Transformación | `df_outliers` de Leslie | `transformar()` | Nono (`validar_lote`) |

**Regla de oro:** igual que Leslie, **no eliminas filas**. Un producto huérfano o una fecha imposible se **marcan** (`en_catalogo = False`, `fecha_venta = None`) y Nono los manda a cuarentena.

---

## 1. Extracción (`src/extraccion.py`)

```python
def extraer_fuentes(rutas: dict[str, Path] | None = None) -> dict[str, pd.DataFrame]:
    """Devuelve {'catalogo', 'fisica', 'online'} SIN interpretar valores.
    - CSV de ventas: pd.read_csv(ruta, dtype=str, keep_default_na=False)  → todo texto
    - JSON: json.load(); se conserva el tipo Python original (int/str/None)
    - Agrega id_fila_origen (1 = primera fila de datos) y registro_original (json.dumps de la fila cruda)
    - Si un archivo no existe o el JSON está corrupto: lanza ErrorExtraccion con mensaje claro
      (el orquestador de Nono lo captura; un archivo ilegible no es un 'registro' en cuarentena)."""
```

**Por qué leer como texto:** si dejas que pandas infiera tipos, `"01-09-2026"` sigue siendo texto, pero una cantidad `"dos"` haría que toda la columna pase a `object` sin avisar, y un `id_cliente` vacío se convierte en `NaN`. Leyendo como texto, **tú decides** cada conversión y marcas los errores.

**Resultado esperado:** `fisica` 620 × 11 (9 originales + 2), `online` 600 × 13, `catalogo` 50 × 6.

---

## 2. Homologación de columnas y tipos (`src/integracion/homologacion.py`)

### 2.1 Mapeo de columnas (contrato acordado en `contratos.py`)

| Unificada | Física (CSV) | Online (JSON) | Notas |
|---|---|---|---|
| `id_transaccion` | `id_ticket` | `order_id` | `strip()` |
| `origen` | `"FISICA"` | `"ONLINE"` | constante |
| `fecha_cruda` | `fecha_venta` | `order_timestamp` | se guarda como texto; se interpreta en F4 |
| `punto_venta` | `sucursal` | `"TIENDA_ONLINE"` | |
| `id_producto` | `id_producto` | `product_id` | `strip().upper()` |
| `cantidad` | `cantidad` | `units` | a número; si no es numérico → `None` + alerta `CANTIDAD_NO_NUMERICA` |
| `precio_unitario` | `precio_unitario` | `unit_price` | a float; si no es numérico → `None` + alerta `PRECIO_INVALIDO` |
| `monto_total` | `monto_total_mxn` | `total_amount` | a float; vacío → `None` (Leslie lo recalcula) |
| `moneda` | `"MXN"` | `currency` | `strip().upper()` |
| `id_cliente` | `id_cliente` | `None` | vacío → `None` (Leslie imputa) |
| `email_cliente` | `None` | `customer_email` | `strip().lower()`; `""` → `None` |
| `direccion_envio` | `None` | `shipping_address` | |
| `metodo_pago` | `metodo_pago` | `payment_gateway` | `strip().upper()` |
| `estado_pedido` | `None` | `order_status` | `strip().upper()` |
| `registro_original`, `id_fila_origen` | de la extracción | de la extracción | intactos |
| `alertas`, `correcciones` | `[]` | `[]` | listas que alimentan todas las etapas |

### 2.2 Homologación de categóricas: efecto real

| Columna | Antes | Después |
|---|---|---|
| `metodo_pago` (física) | `Efectivo` 104 + `efectivo` 89 | `EFECTIVO` 193 |
| `estado_pedido` (online) | `COMPLETADO` 94 + `completado` 98 | `COMPLETADO` 192 |
| Total de categorías de método de pago (ambos canales) | 6 + 4 | 5 + 4 = 9 |

### 2.3 Funciones

```python
def a_numero(valor) -> float | None:
    """'3' → 3.0 · 2 → 2.0 · '' / None → None · 'dos' → lanza ValueError (el llamador agrega la alerta)."""

def homologar_columnas(fuentes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Concatena física + online con el esquema unificado. Filas = 620 + 600 = 1,220."""
```

**Prueba rápida:** `df_homologado.groupby("origen").size()` → `FISICA 620`, `ONLINE 600`.

---

## 3. Fase 4, paso 1: fechas a YYYY-MM-DD (`src/integracion/fechas.py`)

### 3.1 Lo que hay en los datos

| Fuente | Formato | Ejemplo real | Registros |
|---|---|---|---|
| Física | `DD/MM/YYYY` | `26/09/2026` (`POS-2026-0003`) | 208 |
| Física | `YYYY-MM-DD` | `2026-10-03` (`POS-2026-0002`) | 207 |
| Física | `DD-MM-YYYY` | `13-09-2026` (`POS-2026-0001`) | 205 |
| Online | ISO con hora | `2026-10-12T02:23:00` (`WEB-00002`) | 392 |
| Online | Unix epoch (int) | `1789105020` (`WEB-00005`) | 208 |

**¿Cómo sabemos que es día/mes y no mes/día?** En 105 fechas con `/` y 92 con `-`, el primer número es **mayor que 12**, así que no puede ser un mes.

### 3.2 La trampa que debes evitar (y explicar en la defensa)

```python
pd.to_datetime(serie, format="mixed", dayfirst=True)   # ❌ PROHIBIDO (R8.2)
```
El diagnóstico demostró que esta línea interpreta mal **104 fechas**: con `dayfirst=True`, la fecha ISO `2026-09-01` se lee como 9 de enero. El rango resultante (2026-01-09 a 2026-12-10) es falso; el real es **2026-09-01 a 2026-10-15**.

### 3.3 Implementación (probada contra los 1,220 registros reales: 0 fallos)

```python
import math, re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo          # en Windows: pip install tzdata

ZONA_NEGOCIO = ZoneInfo("America/Mexico_City")   # Colima usa UTC−6
PATRONES = [
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "%Y-%m-%d"),
    (re.compile(r"\d{2}/\d{2}/\d{4}"), "%d/%m/%Y"),
    (re.compile(r"\d{2}-\d{2}-\d{4}"), "%d-%m-%Y"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"), "%Y-%m-%dT%H:%M:%S"),
]
RE_EPOCH = re.compile(r"\d{9,11}")

def normalizar_fecha(valor) -> str | None:
    """Devuelve 'YYYY-MM-DD' o None si no se puede interpretar (Nono lo rechaza con FECHA_INVALIDA)."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return None
    texto = str(valor).strip()
    if RE_EPOCH.fullmatch(texto):                                   # epoch en segundos (UTC)
        return (datetime.fromtimestamp(int(texto), tz=timezone.utc)
                .astimezone(ZONA_NEGOCIO).date().isoformat())
    for patron, formato in PATRONES:
        if patron.fullmatch(texto):
            try:
                return datetime.strptime(texto, formato).date().isoformat()
            except ValueError:                                      # p. ej. 31/02/2026
                return None
    return None

def normalizar_fechas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fecha_venta"] = df["fecha_cruda"].map(normalizar_fecha)
    # registrar en 'correcciones' el formato detectado (FECHA_DESDE_DD/MM/YYYY, FECHA_DESDE_EPOCH, ...)
    return df
```

**Resultados verificados con esta función:**

| Entrada | Salida |
|---|---|
| `13-09-2026` | `2026-09-13` |
| `26/09/2026` | `2026-09-26` |
| `2026-10-12T02:23:00` (`WEB-00002`) | `2026-10-12` |
| `1789105020` (`WEB-00005`) | `2026-09-10` (en UTC sería el 11) |
| `31/02/2026` | `None` |
| `ayer`, `2026/09/01`, `None` | `None` |

Rango final: física 2026-09-01 a 2026-10-15; online 2026-09-01 a 2026-10-16.

> **Decisión pendiente de confirmar con el docente (A8):** la conversión del epoch de UTC a hora de México cambia la fecha de **49** pedidos al día anterior. Si el profesor indica que se tome en UTC, solo se quita `.astimezone(...)` y se usa `ZoneInfo("UTC")`.

---

## 4. Fase 4, paso 2: USD a MXN (`src/integracion/moneda.py`)

### 4.1 Regla

- 🟥 Paridad oficial: **1 USD = 19.50 MXN** (constante `PARIDAD_USD_MXN` en `config.py`).
- 🟦 `precio_unitario_mxn = redondear(precio_unitario × 19.50)` y, a partir de ahí, `monto_total_mxn = redondear(cantidad × precio_unitario_mxn)`.
- 🟦 Redondeo financiero con `Decimal` y `ROUND_HALF_UP`, nunca con `float` puro.

```python
from decimal import Decimal, ROUND_HALF_UP

def redondear(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def convertir_a_mxn(df: pd.DataFrame, paridad: float = PARIDAD_USD_MXN) -> pd.DataFrame:
    """Crea precio_unitario_mxn, monto_total_mxn, moneda_original, tipo_cambio_aplicado.
    Moneda ∉ {MXN, USD} → alerta MONEDA_NO_SOPORTADA y columnas MXN en None."""
```

### 4.2 Ejemplos reales

| Pedido | Moneda | unit_price | × 19.50 | Catálogo | Diferencia |
|---|---|---|---|---|---|
| `WEB-00002` (PROD-041) | USD | 169.59 | **3,307.01** | 3,306.99 | 0.02 |
| `WEB-00237` (PROD-018) | USD | 216.31 | **4,218.05** | 4,218.11 | 0.06 |
| `WEB-00003` (PROD-025) | MXN | 1,228.72 | 1,228.72 | 1,228.72 | 0 |

**Verificación global:** los **180** pedidos USD con producto en catálogo coinciden con `precio_base_mxn` con una diferencia máxima de **$0.095**. Los 387 MXN coinciden exactamente. Esto **demuestra que la paridad de 19.50 es la correcta** para este dataset.

### 4.3 ¿Por qué el monto se calcula desde el precio convertido y no convirtiendo el total?

Porque dan centavos distintos. Ejemplo: 2 unidades de 169.59 USD:
- `2 × redondear(169.59 × 19.5)` = 2 × 3,307.01 = **6,614.02**
- `redondear(2 × 169.59 × 19.5)` = **6,614.01**

En los datos reales esta diferencia aparece en **55** pedidos USD. Elegimos un solo método para que el validador de Nono (`monto = cantidad × precio`) nunca falle por un centavo.

---

## 5. Fase 4, paso 3: catálogo maestro y huérfanos (`src/integracion/catalogo.py`)

```python
def cruzar_catalogo(df: pd.DataFrame, catalogo: pd.DataFrame) -> pd.DataFrame:
    cat = catalogo[["id_producto", "nombre_producto", "categoria", "precio_base_mxn"]] \
        .rename(columns={"precio_base_mxn": "precio_catalogo_mxn"})
    out = df.merge(cat, on="id_producto", how="left", validate="many_to_one", indicator=True)
    out["en_catalogo"] = out["_merge"].eq("both")
    out["dif_precio_catalogo"] = (out["precio_unitario_mxn"] - out["precio_catalogo_mxn"]).abs()
    return out.drop(columns="_merge")
```

- `how="left"`: ninguna venta desaparece aunque el producto no exista.
- `validate="many_to_one"`: si alguien duplica un producto del catálogo, pandas lanza error en lugar de **multiplicar filas en silencio**.
- `dif_precio_catalogo` es informativa (hoy siempre ≤ 0.095). Si supera 0.50, agrega la alerta `PRECIO_DIFIERE_CATALOGO` para el reporte, pero **no rechaza**.

**Huérfanos reales:**

| Canal | Registros | IDs | Pista de que son artificiales |
|---|---|---|---|
| Física | 29 (uno también duplicado) | 22 IDs `PROD-9xx` (`PROD-970` ×3, `PROD-980` ×3, …) | **todos** tienen precio 500.00 |
| Online | 33 | 30 IDs `PROD-8xx` (`PROD-890` ×2, `PROD-855` ×2, …) | precio 600.00 MXN o 30.77 USD (= 600 / 19.50) |

Ejemplo: `POS-2026-0017` (PROD-976, 4 × 500 = 2,000) → `en_catalogo = False`, `nombre_producto = NaN`.

### 5.1 Función de la etapa F4

```python
def integrar(df_limpio: pd.DataFrame, catalogo: pd.DataFrame) -> pd.DataFrame:
    df = normalizar_fechas(df_limpio)
    df = convertir_a_mxn(df)
    df = cruzar_catalogo(df, catalogo)
    assert len(df) == len(df_limpio), "La integración no debe cambiar el número de filas"
    return df
```

---

## 6. Fase 5: Min-Max y discretización (`src/integracion/transformacion.py`)

Se ejecuta **después** del capping de Leslie, sobre `monto_total_mxn_cap`.

### 6.1 Min-Max [0, 1]

**Fórmula:** `x' = (x − min) / (max − min)`, donde min y max se calculan **sobre la base estadística** (sin duplicados, cantidad > 0 y en catálogo; usa `mascara_base_estadistica()` de Leslie).

Valores de referencia: **min = 332.67**, **max = 12,032.68** (el LS del capping).

| Registro | `monto_total_mxn_cap` | Cálculo | `monto_minmax` |
|---|---|---|---|
| `POS-2026-0001` | 1,227.12 | (1,227.12 − 332.67) / 11,700.01 | **0.0764** |
| `WEB-00002` | 3,307.01 | (3,307.01 − 332.67) / 11,700.01 | **0.2542** |
| `WEB-00237` | 4,218.05 | (4,218.05 − 332.67) / 11,700.01 | **0.3321** |
| `POS-2026-0031` (bot 500 → 8) | 8,207.84 | (8,207.84 − 332.67) / 11,700.01 | **0.6731** |
| `WEB-00508` (×80 corregido) | 10,329.51 | (10,329.51 − 332.67) / 11,700.01 | **0.8544** |
| `POS-2026-0021` (bot 99, topado) | 12,032.68 | máximo | **1.0000** |

```python
def escalar_min_max(df, columna="monto_total_mxn_cap", base=None) -> tuple[pd.DataFrame, dict]:
    ref = df.loc[base, columna] if base is not None else df[columna]
    mn, mx = ref.min(), ref.max()
    df = df.copy()
    df["monto_minmax"] = ((df[columna] - mn) / (mx - mn)).clip(0, 1).round(6)
    return df, {"min": mn, "max": mx}
```
- `.clip(0, 1)` protege a las filas fuera de la base (por ejemplo, la cantidad −1, cuyo monto con capping es 0), para que no salgan valores negativos.
- Si `mx == mn`, divide entre 1 y deja todo en 0. Agrega una prueba para ese caso.

**¿Por qué sobre la columna con capping?** Sin capping, el máximo sería 2,109,055 (un bot) y el 99 % de las ventas quedaría entre 0.000 y 0.005, de modo que la escala no serviría.

### 6.2 Discretización Bajo / Medio / Alto

**Método:** terciles (cuantiles 1/3 y 2/3) calculados sobre la base estadística. Después se aplican los cortes a todas las filas con `pd.cut`.

| Segmento | Rango (MXN, con capping) | Registros en la base de referencia |
|---|---|---|
| Bajo | ≤ 2,069.07 | 380 |
| Medio | 2,069.07 < x ≤ 4,183.67 | 374 |
| Alto | > 4,183.67 | 375 |

```python
def discretizar_importe(df, columna="monto_total_mxn_cap", base=None) -> tuple[pd.DataFrame, dict]:
    ref = df.loc[base, columna] if base is not None else df[columna]
    c1, c2 = ref.quantile([1/3, 2/3])
    df = df.copy()
    df["segmento_importe"] = pd.cut(df[columna], bins=[-np.inf, c1, c2, np.inf],
                                    labels=["Bajo", "Medio", "Alto"]).astype(str)
    return df, {"corte_bajo_medio": c1, "corte_medio_alto": c2}
```

**Justificación (texto para el reporte):** *"El negocio no definió umbrales de importe. Los terciles generan tres grupos de tamaño comparable (380/374/375), lo que evita segmentos vacíos y hace que 'Alto' signifique 'el tercio superior de las ventas'. Se calculan sobre el importe con capping para que los bots no desplacen los cortes."*

Ejemplos: `POS-2026-0001` (1,227.12) → **Bajo**; `WEB-00002` (3,307.01) → **Medio**; `WEB-00237` (4,218.05) → **Alto**.

### 6.3 Función de la etapa F5

```python
def transformar(df_outliers: pd.DataFrame, base: pd.Series) -> tuple[pd.DataFrame, dict]:
    df, escala = escalar_min_max(df_outliers, base=base)
    df, cortes = discretizar_importe(df, base=base)
    return df, {"minmax": escala, "segmentos": cortes}
```

---

## 7. Qué recibes de Leslie y qué entregas a Nono

### 7.1 Recibes de Leslie

- **Después de F2:** el esquema homologado + `es_duplicado`, `es_id_conflicto`, `monto_total_origen`, `monto_total` corregido (en la moneda original), etiquetas controladas y `correcciones`.
- **Después de F3:** lo anterior + tus columnas de F4 + `cantidad_cap`, `monto_total_mxn_cap`, `es_outlier_cantidad`, `es_outlier_monto` y la función `mascara_base_estadistica()`.

### 7.2 Entregas a Nono (`df_transformado`, 1,220 filas)

| Grupo | Columnas |
|---|---|
| Identidad | `id_transaccion`, `origen`, `id_fila_origen`, `registro_original` |
| Fecha | `fecha_venta` (ISO o `None`) |
| Producto | `id_producto`, `nombre_producto`, `categoria`, `en_catalogo` |
| Cantidades | `cantidad`, `cantidad_cap` |
| Importes | `precio_unitario_mxn`, `moneda_original`, `tipo_cambio_aplicado`, `monto_total_origen`, `monto_total_mxn`, `monto_total_mxn_cap`, `monto_minmax`, `segmento_importe` |
| Cliente / venta | `punto_venta`, `id_cliente`, `email_cliente`, `direccion_envio`, `metodo_pago`, `estado_pedido` |
| Banderas | `es_duplicado`, `es_id_conflicto`, `es_outlier_cantidad`, `es_outlier_monto`, `alertas`, `correcciones` |

> **Antes de entregar:** convierte `NaN` a `None` y los tipos de numpy a tipos de Python (`df.astype(object).where(df.notna(), None)`), porque Pydantic y `sqlite3` no entienden `NaN` como nulo.

---

## 8. Pruebas que debes realizar (`tests/test_integracion.py`)

| Prueba | Resultado esperado |
|---|---|
| `test_homologacion_filas` | 1,220 filas; 620 FISICA y 600 ONLINE |
| `test_columnas_contrato` | `set(df.columns) ⊇ COLUMNAS_HOMOLOGADAS` de `contratos.py` |
| `test_fechas_tres_formatos` | `13-09-2026`, `26/09/2026` y `2026-09-13` producen ISO |
| `test_fecha_epoch_zona` | `1789105020` → `2026-09-10` |
| `test_fecha_imposible` | `31/02/2026` → `None` |
| `test_todas_las_fechas_reales` | 0 `None` en los 1,220 registros oficiales |
| `test_no_usa_mixed` | rango físico 2026-09-01 a 2026-10-15 (no enero ni diciembre) |
| `test_conversion_usd` | `WEB-00002` → 3,307.01 |
| `test_usd_vs_catalogo` | 180 USD con diferencia ≤ 0.10 |
| `test_moneda_desconocida` | `EUR` → alerta `MONEDA_NO_SOPORTADA` |
| `test_huerfanos` | 29 físicos + 33 online con `en_catalogo = False` |
| `test_merge_no_duplica` | filas antes = filas después del merge |
| `test_minmax_rango` | 0 ≤ `monto_minmax` ≤ 1; el máximo de la base vale 1 |
| `test_minmax_constante` | todos los montos iguales → sin división entre 0 |
| `test_segmentos` | solo {Bajo, Medio, Alto}; cortes ≈ 2,069.07 / 4,183.67 |

---

## 9. Capturas y evidencias que debes presentar

> 📸 **Figura Y-1.** *Capturar:* `df_homologado.head()` con las columnas unificadas y `groupby('origen').size()`. *Pie:* "Homologación de esquemas CSV y JSON en una sola estructura".

> 📸 **Figura Y-2.** *Capturar:* `value_counts()` de los formatos de fecha antes y una muestra de `fecha_cruda` → `fecha_venta`, incluido un epoch. *Pie:* "Normalización de 5 formatos de fecha a ISO 8601".

> 📸 **Figura Y-3.** *Capturar:* comparación de rangos entre `format="mixed"` (incorrecto) y el parseo explícito (correcto). *Pie:* "Error de interpretación evitado con parseo explícito".

> 📸 **Figura Y-4.** *Capturar:* pedidos USD con `precio_unitario`, `precio_unitario_mxn` y `precio_catalogo_mxn`. *Pie:* "Conversión USD→MXN a $19.50 verificada contra el catálogo".

> 📸 **Figura Y-5.** *Capturar:* la lista de huérfanos (`en_catalogo == False`) agrupada por canal. *Pie:* "Detección de productos huérfanos mediante LEFT JOIN".

> 📸 **Figura Y-6.** *Capturar:* tabla de ejemplos con `monto_total_mxn_cap`, `monto_minmax` y `segmento_importe`. *Pie:* "Escalamiento Min-Max y discretización por terciles".

> 📸 **Figura Y-7.** *Capturar:* histograma de `monto_minmax` con las líneas de los cortes. *Pie:* "Distribución del importe normalizado y segmentos".

> 📸 **Figura Y-8.** *Capturar:* `pytest tests/test_integracion.py -v` en verde. *Pie:* "Pruebas del módulo de integración".

---

## 10. Qué debes explicar en la defensa oral

**Tu guion (1.5 a 2 minutos):**
1. "Recibimos dos fuentes con esquemas distintos: 9 columnas en español en CSV y 11 en inglés en JSON. Las homologué a un esquema único de 1,220 filas."
2. "Había 5 formatos de fecha. No usé el parseo automático porque leía 104 fechas al revés; programé un parseo explícito por patrón y convertí los epoch de UTC a hora de México."
3. "Convertí los 193 pedidos en dólares a 19.50. Lo verifiqué: los precios convertidos coinciden con el catálogo con menos de 10 centavos de diferencia."
4. "Crucé con el catálogo con un LEFT JOIN y marqué 62 ventas de productos que no existen. Todos tenían precios fijos de 500 o 600: claramente artificiales."
5. "Normalicé con Min-Max sobre el importe ya topado y segmenté por terciles: Bajo hasta $2,069, Medio hasta $4,184 y Alto por encima."

**Preguntas probables:**

| Pregunta | Respuesta |
|---|---|
| ¿Por qué LEFT JOIN y no INNER? | INNER **borraría** los huérfanos sin rastro; LEFT los conserva marcados para enviarlos a cuarentena. |
| ¿Cómo sabes que la fecha es DD/MM y no MM/DD? | 197 fechas tienen el primer número > 12, así que no puede ser un mes. |
| ¿Qué es un epoch? | Segundos transcurridos desde el 1 de enero de 1970 a las 00:00 UTC. |
| ¿Por qué convertir a hora de México? | El negocio está en Colima (UTC−6); 49 pedidos cambiarían de día. Está pendiente de confirmar con el profesor. |
| ¿Por qué Decimal y no round()? | `float` no representa exactamente 3307.005; `Decimal` con HALF_UP da el redondeo financiero esperado. |
| ¿Fórmula de Min-Max? | (x − min) / (max − min). |
| ¿Para qué sirve escalar? | Llevar variables a la misma escala [0, 1] para compararlas o usarlas en modelos sensibles a la magnitud. |
| ¿Por qué Min-Max sobre la columna con capping? | Sin capping, un bot de $2.1 M haría que casi todas las ventas valieran ≈ 0. |
| ¿Terciles o reglas de negocio? | Terciles: no hay umbrales oficiales y producen grupos balanceados (380/374/375). |
| ¿Por qué `validate="many_to_one"`? | Si el catálogo tuviera un ID repetido, el merge duplicaría ventas en silencio; así falla de inmediato. |

**Prepárate también para:** qué es MCAR (Leslie) y qué pasa si un registro falla en Pydantic (Nono).
