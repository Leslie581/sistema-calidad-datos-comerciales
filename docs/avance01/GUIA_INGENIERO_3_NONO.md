# GUÍA DE TRABAJO · INGENIERO 3: NONO
## Validación, Resiliencia y Base de Datos

**Entregable clave (según la guía del profesor):** esquemas Pydantic + script de carga a la BD + pruebas de estrés.
**Rúbrica que defiendes directamente:** criterio 4, Validación Pydantic y Cuarentena (20 pts); criterio 5, Persistencia y Transacciones (15 pts); y la mayor parte del criterio 6, Resiliencia (15 pts). En total, hasta **50 puntos** dependen de tu módulo.
**Tus archivos (solo tú los editas):** `src/validacion/esquemas.py`, `src/validacion/cuarentena.py`, `src/persistencia/esquema.sql`, `src/persistencia/carga.py`, `src/pipeline.py`, `tests/test_validacion.py`, `tests/test_persistencia.py`, `tests/test_estres.py`, `datos/estres/*`, `requirements.txt`.
**Además, el Día 1:** creas el repositorio, `src/config.py`, `src/contratos.py` y el README con los roles (los contenidos se acuerdan entre los tres).

> El código de esta guía (modelo, validación, DDL, carga y rollback) **se ejecutó y comprobó** con Python 3 y Pydantic 2 antes de incluirlo. Puedes usarlo como punto de partida, pero debes entender cada línea porque te lo preguntarán.

---

## 0. Tu lugar en el pipeline

| Paso | Recibes | Función | Produces |
|---|---|---|---|
| F6 · Validación | `df_transformado` de Yerik (1,220 filas) | `validar_lote(df, lote_id)` | `validos: list[dict]`, `cuarentena: list[dict]` |
| F7 · Carga | las dos listas | `cargar_lote(conn, validos, cuarentena, lote_id)` | tablas en `salidas/comercial.db` |
| Orquestación | rutas de los datos | `ejecutar_pipeline()` | resumen de ejecución; **nunca** una excepción sin controlar |
| Resiliencia | archivos corruptos de `datos/estres/` | `pytest tests/test_estres.py` | evidencia de *no crash* |

**Eres el único punto de rechazo.** Leslie y Yerik marcan con banderas, y tú decides con Pydantic. Por eso la regla de conservación es tu responsabilidad:

```
len(validos) + len(cuarentena) == len(df_transformado) == 1,220
```

---

## 1. Qué recibes de Yerik

Un DataFrame de **1,220 filas** con las columnas de `GUIA_GENERAL_PROYECTO.md §9`. Las que tu modelo usa para decidir:

| Columna | Qué te dice | Si está mal → código |
|---|---|---|
| `es_duplicado` (Leslie) | fila repetida | `DUPLICADO_EXACTO` |
| `es_id_conflicto` (Leslie) | mismo ID con contenido distinto | `ID_REPETIDO_CONFLICTO` |
| `id_transaccion` | formato del ID | `ID_FORMATO_INVALIDO` |
| `fecha_venta` (Yerik) | ISO o `None` | `FECHA_INVALIDA` |
| `en_catalogo` (Yerik) | producto existe | `PRODUCTO_HUERFANO` |
| `cantidad`, `cantidad_cap` | entero > 0 | `CANTIDAD_INVALIDA` |
| `moneda_original` | MXN/USD | `MONEDA_NO_SOPORTADA` |
| `precio_unitario_mxn` | > 0 | `PRECIO_FALTANTE` / `PRECIO_INVALIDO` |
| `monto_total_mxn` | > 0 y = cantidad × precio | `MONTO_INVALIDO` / `MONTO_INCONSISTENTE` |
| `email_cliente` | regex o `SIN_CORREO` | `EMAIL_MALFORMADO` |
| `monto_minmax` | [0, 1] | `ESCALA_FUERA_DE_RANGO` |
| `segmento_importe` | Bajo/Medio/Alto | `TIPO_INVALIDO` |

**Mientras Yerik termina:** programa contra un DataFrame de ejemplo escrito a mano con estas columnas (los ejemplos de §4 sirven tal cual). No necesitas esperar a nadie para tener el Día 3 listo.

---

## 2. Modelo Pydantic (`src/validacion/esquemas.py`)

### 2.1 Decisiones de diseño

1. **Un solo modelo** `TransaccionLimpia` para ambos canales, porque la tabla final es una sola. Las diferencias por canal se resuelven dentro de los validadores (por ejemplo, el correo solo se exige en `ONLINE`).
2. **Cada mensaje empieza con un CÓDIGO** (`PRODUCTO_HUERFANO: …`). Así se puede filtrar y contar la cuarentena con SQL.
3. **Se usan `@field_validator`** (lo que pide el profesor). Para validar entre campos (monto = cantidad × precio) se usa `info.data`, que contiene los campos **ya validados y declarados antes**; por eso el orden de los campos importa.
4. `mode="before"` en la cantidad: se valida **antes** de que Pydantic intente convertir el tipo, para dar un mensaje propio en lugar del genérico ("Input should be a valid integer").
5. `extra="ignore"`: las columnas auxiliares (`registro_original`, `alertas`, …) no hacen fallar el modelo.
6. Pydantic **acumula todos los errores** de un registro. Un pedido huérfano con correo malformado se reporta con los dos motivos.

### 2.2 Código (probado)

```python
import math, re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

RE_ID = re.compile(r"(POS-\d{4}-\d{4}|WEB-\d{5})")
RE_PROD = re.compile(r"PROD-\d{3}")
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
ETIQUETA_SIN_CORREO = "SIN_CORREO"
COLUMNAS_CONTROL = {"es_duplicado", "es_id_conflicto", "en_catalogo"}


class TransaccionLimpia(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # ---- control (se validan, pero no se guardan en la tabla) ----
    es_duplicado: bool = False
    es_id_conflicto: bool = False
    # ---- identidad ----
    id_transaccion: str
    origen: Literal["FISICA", "ONLINE"]
    fecha_venta: Optional[str]
    punto_venta: str
    # ---- producto ----
    id_producto: Optional[str]
    en_catalogo: bool
    nombre_producto: Optional[str] = None
    categoria: Optional[str] = None
    # ---- cantidades e importes ----
    cantidad: int
    cantidad_cap: int
    moneda_original: str
    precio_unitario_mxn: Optional[float]
    tipo_cambio_aplicado: Optional[float]
    monto_total_origen: Optional[float] = None
    monto_total_mxn: Optional[float]
    monto_total_mxn_cap: float
    monto_minmax: float
    segmento_importe: Literal["Bajo", "Medio", "Alto"]
    # ---- cliente / venta ----
    id_cliente: Optional[str] = None
    email_cliente: Optional[str] = None
    direccion_envio: Optional[str] = None
    metodo_pago: str
    estado_pedido: Optional[str] = None
    es_outlier_cantidad: bool
    es_outlier_monto: bool
    correcciones: list[str] = []

    @field_validator("es_duplicado")
    @classmethod
    def v_duplicado(cls, v):
        if v:
            raise ValueError("DUPLICADO_EXACTO: repite exactamente una fila anterior del mismo archivo")
        return v

    @field_validator("es_id_conflicto")
    @classmethod
    def v_conflicto(cls, v):
        if v:
            raise ValueError("ID_REPETIDO_CONFLICTO: el identificador aparece con contenido distinto")
        return v

    @field_validator("id_transaccion")
    @classmethod
    def v_id(cls, v):
        if not RE_ID.fullmatch(str(v)):
            raise ValueError(f"ID_FORMATO_INVALIDO: '{v}' no cumple POS-AAAA-NNNN ni WEB-NNNNN")
        return v

    @field_validator("fecha_venta")
    @classmethod
    def v_fecha(cls, v):
        if v is None:
            raise ValueError("FECHA_INVALIDA: la fecha original no tiene un formato reconocido o no existe")
        f = date.fromisoformat(v)
        if f > date.today():
            raise ValueError(f"FECHA_INVALIDA: {v} es posterior a la fecha de ejecución")
        return v

    @field_validator("en_catalogo")
    @classmethod
    def v_catalogo(cls, v, info):
        if not v:
            raise ValueError(f"PRODUCTO_HUERFANO: '{info.data.get('id_producto')}' no existe en el catálogo maestro")
        return v

    @field_validator("cantidad", "cantidad_cap", mode="before")
    @classmethod
    def v_cantidad(cls, v, info):
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"CANTIDAD_INVALIDA: {info.field_name}={v!r} no es numérica")
        if isinstance(v, bool) or math.isnan(n) or not n.is_integer() or n <= 0:
            raise ValueError(f"CANTIDAD_INVALIDA: {info.field_name}={v!r}; debe ser entero mayor que 0")
        return int(n)

    @field_validator("moneda_original")
    @classmethod
    def v_moneda(cls, v):
        if v not in ("MXN", "USD"):
            raise ValueError(f"MONEDA_NO_SOPORTADA: '{v}' (solo MXN o USD)")
        return v

    @field_validator("precio_unitario_mxn")
    @classmethod
    def v_precio(cls, v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            raise ValueError("PRECIO_FALTANTE: no hay precio unitario en MXN")
        if v <= 0:
            raise ValueError(f"PRECIO_INVALIDO: {v} debe ser mayor que 0")
        return v

    @field_validator("monto_total_mxn")
    @classmethod
    def v_monto(cls, v, info):
        if v is None or v <= 0:
            raise ValueError(f"MONTO_INVALIDO: {v}")
        c, p = info.data.get("cantidad"), info.data.get("precio_unitario_mxn")
        if c is not None and p is not None and abs(round(c * p, 2) - v) > 0.01:
            raise ValueError(f"MONTO_INCONSISTENTE: {v} ≠ {c} × {p}")
        return v

    @field_validator("monto_minmax")
    @classmethod
    def v_minmax(cls, v):
        if not 0 <= v <= 1:
            raise ValueError(f"ESCALA_FUERA_DE_RANGO: monto_minmax={v}")
        return v

    @field_validator("email_cliente")
    @classmethod
    def v_email(cls, v, info):
        if info.data.get("origen") == "ONLINE" and v != ETIQUETA_SIN_CORREO:
            if v is None or not RE_EMAIL.fullmatch(v):
                raise ValueError(f"EMAIL_MALFORMADO: '{v}' no es una dirección de correo válida")
        return v
```

---

## 3. Separación de válidos e inválidos (`src/validacion/cuarentena.py`)

```python
import json
import pandas as pd
from pydantic import ValidationError
from .esquemas import TransaccionLimpia, COLUMNAS_CONTROL


def formatear_motivos(e: ValidationError) -> tuple[list[str], str]:
    codigos, mensajes = [], []
    for err in e.errors():
        msg = err["msg"].removeprefix("Value error, ")
        codigo = msg.split(":")[0]
        if not codigo.isupper() or " " in codigo:          # error nativo de Pydantic (tipo, Literal…)
            campo = ".".join(map(str, err["loc"]))
            codigo, msg = "TIPO_INVALIDO", f"TIPO_INVALIDO: {campo} → {msg}"
        codigos.append(codigo)
        mensajes.append(msg)
    return sorted(set(codigos)), " | ".join(mensajes)


def a_nativo(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):          # numpy → Python
        return v.item()
    return v


def validar_lote(df: pd.DataFrame, lote_id: str):
    validos, cuarentena = [], []
    for fila in df.to_dict(orient="records"):
        fila = {k: a_nativo(v) for k, v in fila.items()}
        try:
            modelo = TransaccionLimpia(**fila)
            reg = modelo.model_dump(exclude=COLUMNAS_CONTROL)
            reg["correcciones"] = json.dumps(reg["correcciones"], ensure_ascii=False)
            reg["lote_id"] = lote_id
            validos.append(reg)
        except ValidationError as e:
            codigos, motivo = formatear_motivos(e)
            cuarentena.append(_registro_cuarentena(fila, lote_id, "VALIDACION", codigos, motivo))
        except Exception as e:                                   # resiliencia: nunca detener el lote
            cuarentena.append(_registro_cuarentena(fila, lote_id, "VALIDACION", ["ERROR_INESPERADO"],
                                                   f"ERROR_INESPERADO: {type(e).__name__}: {e}"))
    return validos, cuarentena


def _registro_cuarentena(fila, lote_id, etapa, codigos, motivo):
    return {"lote_id": lote_id, "id_registro": str(fila.get("id_transaccion")), "origen": fila.get("origen"),
            "id_fila_origen": fila.get("id_fila_origen"), "etapa_deteccion": etapa,
            "codigos_error": ";".join(codigos), "motivo_rechazo_cuarentena": motivo,
            "registro_original": fila.get("registro_original") or json.dumps(fila, default=str, ensure_ascii=False)}
```

**Puntos clave para la defensa:**
- El `try/except` está **dentro del ciclo**, así que un registro que falla no detiene a los demás.
- El segundo `except Exception` captura cualquier error imprevisto (por ejemplo, un tipo raro) y lo manda a cuarentena con `ERROR_INESPERADO`. Esto es lo que garantiza el *no crash*.
- `a_nativo()` convierte `NaN` → `None` y los tipos de numpy a tipos de Python. Sin esto, Pydantic recibiría `nan` como número válido en campos opcionales.

### 3.1 Salida comprobada con el código anterior (casos reales y de estrés)

```
WEB-00477      → PRODUCTO_HUERFANO: 'PROD-818' no existe en el catálogo maestro | EMAIL_MALFORMADO: 'sin_arroba_dominio.org' no es una dirección de correo válida
POS-2026-0216  → CANTIDAD_INVALIDA: cantidad=-1; debe ser entero mayor que 0 | CANTIDAD_INVALIDA: cantidad_cap=-1; … | MONTO_INVALIDO: -934.83
'; DROP TABLE transacciones_limpias;--  → ID_FORMATO_INVALIDO: … no cumple POS-AAAA-NNNN ni WEB-NNNNN
WEB-99999      → MONEDA_NO_SOPORTADA: 'EUR' (solo MXN o USD) | PRECIO_FALTANTE: no hay precio unitario en MXN
WEB-99998      → FECHA_INVALIDA: … | CANTIDAD_INVALIDA: cantidad='dos' no es numérica | TIPO_INVALIDO: segmento_importe → Input should be 'Bajo', 'Medio' or 'Alto'
POS-2026-0001  → DUPLICADO_EXACTO: repite exactamente una fila anterior del mismo archivo
WEB-99997      → TIPO_INVALIDO: monto_minmax → Input should be a valid number
```

---

## 4. Qué registros aceptar o rechazar: ejemplos reales

### 4.1 Registros que deben ACEPTARSE

| Registro (dato crudo) | Qué le pasó en el pipeline | Por qué es válido |
|---|---|---|
| `POS-2026-0002` · 2026-10-03 · PROD-031 · 1 × 1,168.79 · `TRANSFERENCIA` | nada (solo formato) | todo correcto |
| `WEB-00002` · `2026-10-12T02:23:00` · PROD-041 · 1 × **169.59 USD** · `completado` | fecha → 2026-10-12; precio → 3,307.01 MXN; estado → `COMPLETADO` | corregible sin inventar |
| `POS-2026-0005` · `01-09-2026` · `id_cliente` vacío | fecha → 2026-09-01; `id_cliente` → `ANONIMO` | MCAR, etiqueta controlada |
| `POS-2026-0075` · monto vacío · 1 × 1,437.14 | monto recalculado 1,437.14 | recalculable |
| `WEB-00508` · 3 × 3,443.17 · total **826,360.80** | monto → 10,329.51 (original guardado) | total ×80 corregido |
| `POS-2026-0031` · **500** × 1,025.98 | `cantidad_cap` = 8, `monto_total_mxn_cap` = 8,207.84 | outlier tratado con capping, no eliminado |
| `WEB-00040` · correo `""` | `email_cliente` → `SIN_CORREO` | faltante ≠ malformado |

### 4.2 Registros que deben ir a CUARENTENA

| Registro (dato crudo) | Motivo(s) esperado(s) |
|---|---|
| `POS-2026-0001`, fila 613 (copia de la fila 1) | `DUPLICADO_EXACTO` |
| `POS-2026-0216` · cantidad **−1** · monto −934.83 | `CANTIDAD_INVALIDA`, `MONTO_INVALIDO` |
| `POS-2026-0035` · cantidad **0** · monto 0.00 | `CANTIDAD_INVALIDA`, `MONTO_INVALIDO` |
| `POS-2026-0017` · **PROD-976** · 4 × 500.00 | `PRODUCTO_HUERFANO` |
| `POS-2026-0493` · **PROD-928** · cantidad **−1** | `PRODUCTO_HUERFANO`, `CANTIDAD_INVALIDA`, `MONTO_INVALIDO` |
| `WEB-00004` · PROD-005 · correo `correo_invalido.com` · total ×80 | `EMAIL_MALFORMADO` (el monto sí se había corregido, pero el correo no se puede reparar) |
| `WEB-00083` · correo `sin_arroba_dominio.org` | `EMAIL_MALFORMADO` |
| `WEB-00124` · correo `usuario@@gmail..com` | `EMAIL_MALFORMADO` |
| `WEB-00001` · **PROD-890** · total 48,000 (×80) | `PRODUCTO_HUERFANO` |
| `WEB-00477` · **PROD-818** · `sin_arroba_dominio.org` | `PRODUCTO_HUERFANO`, `EMAIL_MALFORMADO` |

### 4.3 Conteos esperados al ejecutar con los datos oficiales

| | Física | Online | Total |
|---|---|---|---|
| Entrada | 620 | 600 | **1,220** |
| `transacciones_limpias` | 562 | 542 | **1,104** |
| `cuarentena_errores` | 58 | 58 | **116** |

| Código | Registros que lo contienen |
|---|---|
| `DUPLICADO_EXACTO` | 20 |
| `CANTIDAD_INVALIDA` | 11 (todos también con `MONTO_INVALIDO`) |
| `PRODUCTO_HUERFANO` | 62 (29 + 33) |
| `EMAIL_MALFORMADO` | 28 |
| Registros con más de un motivo | 5 por códigos de regla (2 físicos y 3 online), más los 11 de cantidad inválida + monto |

> Si tu ejecución da otra cifra, **no la ajustes**: busca qué registro se clasificó distinto (`SELECT codigos_error, COUNT(*) … GROUP BY`) y documenta la causa.

---

## 5. Tablas SQLite (`src/persistencia/esquema.sql`)

```sql
CREATE TABLE IF NOT EXISTS transacciones_limpias (
    id_transaccion       TEXT PRIMARY KEY,
    origen               TEXT NOT NULL CHECK (origen IN ('FISICA','ONLINE')),
    fecha_venta          TEXT NOT NULL CHECK (fecha_venta GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    punto_venta          TEXT NOT NULL,
    id_producto          TEXT NOT NULL,
    nombre_producto      TEXT NOT NULL,
    categoria            TEXT NOT NULL,
    cantidad             INTEGER NOT NULL CHECK (cantidad > 0),
    cantidad_cap         INTEGER NOT NULL CHECK (cantidad_cap > 0),
    moneda_original      TEXT NOT NULL CHECK (moneda_original IN ('MXN','USD')),
    precio_unitario_mxn  REAL NOT NULL CHECK (precio_unitario_mxn > 0),
    tipo_cambio_aplicado REAL NOT NULL,
    monto_total_origen   REAL,
    monto_total_mxn      REAL NOT NULL CHECK (monto_total_mxn > 0),
    monto_total_mxn_cap  REAL NOT NULL,
    monto_minmax         REAL NOT NULL CHECK (monto_minmax BETWEEN 0 AND 1),
    segmento_importe     TEXT NOT NULL CHECK (segmento_importe IN ('Bajo','Medio','Alto')),
    id_cliente           TEXT,
    email_cliente        TEXT,
    direccion_envio      TEXT,
    metodo_pago          TEXT NOT NULL,
    estado_pedido        TEXT,
    es_outlier_cantidad  INTEGER NOT NULL CHECK (es_outlier_cantidad IN (0,1)),
    es_outlier_monto     INTEGER NOT NULL CHECK (es_outlier_monto IN (0,1)),
    correcciones         TEXT NOT NULL DEFAULT '[]',
    lote_id              TEXT NOT NULL,
    fecha_carga          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS cuarentena_errores (
    id_error                   INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id                    TEXT NOT NULL,
    id_registro                TEXT,
    origen                     TEXT,
    id_fila_origen             INTEGER,
    etapa_deteccion            TEXT NOT NULL,
    codigos_error              TEXT NOT NULL,
    motivo_rechazo_cuarentena  TEXT NOT NULL CHECK (length(trim(motivo_rechazo_cuarentena)) > 0),
    registro_original          TEXT NOT NULL,
    fecha_cuarentena           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_cuarentena_lote ON cuarentena_errores(lote_id);
CREATE INDEX IF NOT EXISTS ix_limpias_fecha ON transacciones_limpias(fecha_venta);
```

**Por qué hay `CHECK` en SQL si ya validó Pydantic:** es la **defensa en profundidad**. Si un día alguien inserta sin pasar por el modelo, la base rechaza el dato. Además, el `CHECK` sobre `motivo_rechazo_cuarentena` garantiza que **ningún** registro en cuarentena quede sin motivo.

**Decisiones:**
- Las fechas se guardan como `TEXT` ISO (SQLite no tiene un tipo `DATE` real; ISO se ordena y compara bien como texto).
- Los booleanos se guardan como `INTEGER` 0/1.
- `correcciones` es un JSON en texto (por ejemplo, `["IMPUTADO_ID_CLIENTE","FECHA_DESDE_DD-MM-YYYY"]`), lo que da trazabilidad por fila.
- `registro_original` guarda la fila cruda completa, para poder auditar o reprocesar.

---

## 6. Commit y rollback (`src/persistencia/carga.py`)

```python
import sqlite3
from pathlib import Path

DDL = Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")


class ErrorCarga(Exception):
    pass


def crear_tablas(conn):
    conn.executescript(DDL)


def _insertar(conn, tabla, filas):
    if not filas:
        return 0
    cols = list(filas[0].keys())
    sql = f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    conn.executemany(sql, [tuple(f[c] for c in cols) for f in filas])
    return len(filas)


def cargar_lote(conn, validos, cuarentena, lote_id, reemplazar=True):
    try:
        if reemplazar:                       # recarga completa, atómica
            conn.execute("DELETE FROM transacciones_limpias")
            conn.execute("DELETE FROM cuarentena_errores")
        n_ok = _insertar(conn, "transacciones_limpias", validos)
        n_qz = _insertar(conn, "cuarentena_errores", cuarentena)
        conn.commit()
        return {"lote_id": lote_id, "insertados": n_ok, "en_cuarentena": n_qz, "estado": "COMMIT"}
    except sqlite3.Error as e:
        conn.rollback()
        raise ErrorCarga(f"Carga revertida (rollback) del lote {lote_id}: {e}") from e
```

### 6.1 Qué demuestra este diseño (comprobado)

1. **Atomicidad:** las dos tablas se escriben en **una sola transacción**. O se guardan ambas, o ninguna.
2. **Recarga segura:** con `reemplazar=True` se borra el contenido anterior **dentro de la misma transacción**. Si la nueva carga falla, el `rollback()` **restaura los datos anteriores**. En la prueba, el lote L2 falló por una llave primaria repetida y la tabla conservó intactas las filas del lote L1.
3. **Consultas parametrizadas (`?`):** el ID malicioso `'; DROP TABLE transacciones_limpias;--` se trata como texto. Además, Pydantic ya lo había rechazado por formato.
4. En Python, `sqlite3` abre la transacción implícitamente con el primer `DELETE`/`INSERT`; `commit()` la confirma y `rollback()` la deshace.

---

## 7. Orquestador (`src/pipeline.py`)

```python
def ejecutar_pipeline(rutas=None, ruta_bd=RUTA_BD) -> dict:
    lote_id = datetime.now().strftime("L%Y%m%d-%H%M%S")
    resumen = {"lote_id": lote_id, "estado": "INICIADO", "etapas": {}}
    try:
        fuentes = extraer_fuentes(rutas)                                   # Yerik
        resumen["perfil_antes"] = perfilar_fuentes(fuentes)               # Leslie
        df = homologar_columnas(fuentes)                                   # Yerik
        df, resumen["etapas"]["limpieza"] = limpiar_registros(df)          # Leslie
        df = integrar(df, fuentes["catalogo"])                             # Yerik
        df, resumen["etapas"]["iqr"] = tratar_outliers(df)                 # Leslie
        df, resumen["etapas"]["transformacion"] = transformar(df, mascara_base_estadistica(df))  # Yerik
        validos, cuarentena = validar_lote(df, lote_id)                    # Nono
        if len(validos) + len(cuarentena) != len(df):
            raise ErrorConservacion(f"{len(validos)} + {len(cuarentena)} ≠ {len(df)}")
        with sqlite3.connect(ruta_bd) as conn:   # nota: 'with' NO cierra la conexión, solo hace commit/rollback
            crear_tablas(conn)
            resumen["carga"] = cargar_lote(conn, validos, cuarentena, lote_id)
        resumen["estado"] = "COMPLETADO"
    except (ErrorExtraccion, ErrorCarga, ErrorConservacion) as e:
        resumen.update(estado="FALLIDO", error=str(e))                    # error previsto, mensaje claro
    except Exception as e:
        resumen.update(estado="FALLIDO", error=f"{type(e).__name__}: {e}") # imprevisto, pero controlado
    finally:
        guardar_bitacora(resumen)                                          # salidas/bitacora_<lote>.json
    return resumen

if __name__ == "__main__":
    r = ejecutar_pipeline()
    print(json.dumps({k: r[k] for k in ("lote_id", "estado") if k in r} | r.get("carga", {}), indent=2))
    sys.exit(0 if r["estado"] == "COMPLETADO" else 1)
```

**Diferencia que debes saber explicar:** un *registro* corrupto va a **cuarentena** y el lote continúa. Un *archivo* ilegible (JSON truncado) o una falla de la BD **no son registros**: el pipeline termina con estado `FALLIDO`, un mensaje claro y la bitácora escrita, sin traza de error sin controlar y sin datos parciales.

---

## 8. Pruebas de estrés (`tests/test_estres.py` + `datos/estres/`)

### 8.1 Archivo de datos corruptos

Crea `datos/estres/generar_estres.py`, que **copia** registros reales y les inyecta defectos. Los originales nunca se tocan. Cada caso lleva el motivo esperado:

| # | Inyección | Archivo | Resultado esperado |
|---|---|---|---|
| E1 | `cantidad = "dos"` | CSV | cuarentena · `CANTIDAD_INVALIDA` |
| E2 | `cantidad = 2.5` | CSV | cuarentena · `CANTIDAD_INVALIDA` |
| E3 | cantidad **y** monto vacíos | CSV | **válido**: cantidad = mediana (2), monto recalculado (prueba la imputación de Leslie) |
| E4 | `precio_unitario = -10` | CSV | cuarentena · `PRECIO_INVALIDO` |
| E5 | `precio_unitario = "abc"` | CSV | cuarentena · `PRECIO_FALTANTE` |
| E6 | `fecha = "31/02/2026"` | CSV | cuarentena · `FECHA_INVALIDA` |
| E7 | `fecha = "2027-01-01"` (futura) | CSV | cuarentena · `FECHA_INVALIDA` |
| E8 | `order_timestamp = "ayer"` | JSON | cuarentena · `FECHA_INVALIDA` |
| E9 | `currency = "EUR"` | JSON | cuarentena · `MONEDA_NO_SOPORTADA` |
| E10 | `product_id = null` | JSON | cuarentena · `PRODUCTO_HUERFANO` |
| E11 | `customer_email = "a@b"` | JSON | cuarentena · `EMAIL_MALFORMADO` |
| E12 | `order_id = "WEB-1"` | JSON | cuarentena · `ID_FORMATO_INVALIDO` |
| E13 | `order_id = "'; DROP TABLE transacciones_limpias;--"` | JSON | cuarentena; **la tabla sigue existiendo** |
| E14 | mismo `order_id` con dos contenidos | JSON | ambos en cuarentena · `ID_REPETIDO_CONFLICTO` |
| E15 | registro sin el campo `units` | JSON | **válido**: un campo ausente es un faltante, así que la cantidad se imputa con la mediana online (1) y el monto se recalcula |
| E16 | campos extra (`"hacker": true`) | JSON | se ignoran; registro válido |
| E17 | `total_amount = 1e308` | JSON | monto recalculado (válido) |
| E18 | dirección con emoji / acentos | JSON | válido (UTF-8) |
| E19 | archivo JSON vacío `[]` | JSON | estado `COMPLETADO`, 0 + 0 en esa fuente |
| E20 | JSON truncado (`[{"order_id": "WEB-`) | JSON | estado `FALLIDO`, mensaje claro, **sin excepción sin controlar** |
| E21 | falla forzada a mitad de la carga (`monkeypatch` de `_insertar`) | BD | `rollback`; **0 filas parciales** |
| E22 | volumen: los 1,220 registros reales × 10, barajados | ambos | conservación del conteo y tiempo registrado (**PENDIENTE** medir) |

### 8.2 Afirmaciones que deben cumplirse en TODAS las pruebas

```python
def verificar_invariantes(resumen, conn, n_entrada):
    n_ok = conn.execute("SELECT COUNT(*) FROM transacciones_limpias").fetchone()[0]
    n_qz = conn.execute("SELECT COUNT(*) FROM cuarentena_errores").fetchone()[0]
    assert resumen["estado"] == "COMPLETADO"
    assert n_ok + n_qz == n_entrada                                            # nada se pierde
    assert conn.execute("SELECT COUNT(*) FROM cuarentena_errores "
                        "WHERE trim(motivo_rechazo_cuarentena) = ''").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM transacciones_limpias "
                        "WHERE fecha_venta NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'").fetchone()[0] == 0
```

### 8.3 Cómo comprobar que el sistema no colapsa

1. `pytest tests/test_estres.py -v`: todas las pruebas en verde.
2. Ejecutar `python -m src.pipeline` con el JSON truncado (E20): el código de salida es 1, la consola muestra `estado: FALLIDO` con el motivo, **no aparece ningún `Traceback`**, y la BD anterior queda intacta.
3. Revisar la bitácora `salidas/bitacora_<lote>.json`.

---

## 9. Consultas de verificación (para la defensa y las capturas)

```sql
-- 1. Conservación
SELECT (SELECT COUNT(*) FROM transacciones_limpias) AS limpias,
       (SELECT COUNT(*) FROM cuarentena_errores)    AS cuarentena;

-- 2. Cuarentena por motivo
SELECT codigos_error, COUNT(*) AS n FROM cuarentena_errores GROUP BY codigos_error ORDER BY n DESC;

-- 3. Integridad referencial (debe dar 0): nombre_producto solo existe si el cruce con el catálogo tuvo éxito
SELECT COUNT(*) FROM transacciones_limpias WHERE nombre_producto IS NULL OR id_producto NOT GLOB 'PROD-0[0-4][0-9]' AND id_producto <> 'PROD-050';

-- 4. Ventas por canal y segmento
SELECT origen, segmento_importe, COUNT(*), ROUND(SUM(monto_total_mxn_cap), 2)
FROM transacciones_limpias GROUP BY origen, segmento_importe;

-- 5. Trazabilidad de un registro corregido
SELECT id_transaccion, monto_total_origen, monto_total_mxn, correcciones
FROM transacciones_limpias WHERE id_transaccion = 'WEB-00508';
```

---

## 10. Qué archivos y funciones debes desarrollar (checklist)

| Archivo | Funciones / contenido | Día |
|---|---|---|
| `README.md` | equipo, roles, instalación, cómo ejecutar | 1 |
| `src/config.py` | `RUTA_DATOS`, `RUTA_BD`, `PARIDAD_USD_MXN = 19.50`, `FACTOR_IQR = 1.5`, etiquetas | 1 |
| `src/contratos.py` | listas de columnas por etapa (acordadas) | 1 |
| `src/validacion/esquemas.py` | `TransaccionLimpia` + validadores | 2–3 |
| `src/validacion/cuarentena.py` | `validar_lote`, `formatear_motivos`, `a_nativo` | 3 |
| `src/persistencia/esquema.sql` | DDL de las 2 tablas + índices | 3 |
| `src/persistencia/carga.py` | `crear_tablas`, `cargar_lote`, `ErrorCarga` | 4 |
| `src/pipeline.py` | `ejecutar_pipeline`, bitácora, `__main__` | 4 |
| `datos/estres/generar_estres.py` | casos E1–E22 | 4 |
| `tests/test_validacion.py` | un caso por validador + uno válido | 3 |
| `tests/test_persistencia.py` | commit, rollback y recarga | 4 |
| `tests/test_estres.py` | invariantes con datos corruptos | 4 |

---

## 11. Evidencias que debes presentar

> 📸 **Figura N-1.** *Capturar:* el código de `TransaccionLimpia` mostrando dos `@field_validator` (catálogo y correo). *Pie:* "Modelo Pydantic con validadores personalizados".

> 📸 **Figura N-2.** *Capturar:* consola con los primeros registros enviados a cuarentena y su motivo. *Pie:* "Segregación de registros: motivos de rechazo".

> 📸 **Figura N-3.** *Capturar:* DB Browser for SQLite con la estructura de `transacciones_limpias`. *Pie:* "Esquema de la tabla de transacciones limpias".

> 📸 **Figura N-4.** *Capturar:* DB Browser con `cuarentena_errores` (columnas de motivo y registro original). *Pie:* "Zona de cuarentena con trazabilidad".

> 📸 **Figura N-5.** *Capturar:* el resultado de la consulta 1 (conservación) y de la 2 (motivos). *Pie:* "Conservación del conteo: limpias + cuarentena = 1,220".

> 📸 **Figura N-6.** *Capturar:* la prueba de rollback (mensaje "Carga revertida" + conteos sin cambio). *Pie:* "Rollback ante una falla en la carga: 0 filas parciales".

> 📸 **Figura N-7.** *Capturar:* `pytest tests/ -v` completo en verde. *Pie:* "Batería de pruebas, incluidas las de estrés".

> 📸 **Figura N-8.** *Capturar:* la ejecución con el JSON truncado mostrando `estado: FALLIDO` sin traceback. *Pie:* "Resiliencia ante un archivo corrupto".

---

## 12. Qué debes explicar en la defensa oral

**Tu guion (1.5 a 2 minutos):**
1. "Definí un modelo Pydantic con validadores propios; cada mensaje empieza con un código de error para poder contarlo."
2. "Valido registro por registro dentro de un `try/except`: si uno falla, va a cuarentena con todos sus motivos y el registro crudo, y el lote sigue."
3. "De 1,220 registros, 1,104 son válidos y 116 van a cuarentena: 20 duplicados, 11 cantidades imposibles, 62 productos huérfanos y 28 correos malformados." *(mostrar la consulta)*
4. "La carga es una sola transacción: si algo falla, `rollback()` deja la base como estaba. Lo demuestro con esta prueba." *(Figura N-6)*
5. "Las pruebas de estrés inyectan 22 tipos de corrupción, incluida una inyección SQL y un JSON truncado, y el pipeline no se cae."

**Preguntas probables:**

| Pregunta | Respuesta |
|---|---|
| ¿Qué es `BaseModel`? | La clase base de Pydantic: define campos con tipos y valida al construir el objeto. |
| ¿Qué hace `@field_validator`? | Ejecuta una función propia sobre un campo; si lanza `ValueError`, Pydantic lo convierte en `ValidationError`. |
| ¿Para qué `mode="before"`? | Para validar el valor crudo antes de la conversión automática de tipo y dar un mensaje propio. |
| ¿Cómo validas un campo contra otro? | Con `info.data`, que contiene los campos ya validados; por eso el monto se declara después de cantidad y precio. |
| ¿Qué pasa si un registro tiene 2 errores? | Pydantic los acumula; se guardan ambos, separados por ` \| `. |
| ¿Diferencia entre `commit` y `rollback`? | `commit` hace permanentes los cambios de la transacción; `rollback` los deshace todos desde el último commit. |
| ¿Por qué una sola transacción para las dos tablas? | Para que nunca existan limpias sin su cuarentena correspondiente (estado parcial). |
| ¿Cómo evitas la inyección SQL? | Consultas parametrizadas con `?`; nunca concateno valores en el SQL. |
| ¿Por qué `CHECK` si ya validó Pydantic? | Defensa en profundidad: la base se protege sola si alguien inserta sin pasar por el modelo. |
| ¿Qué pasa si el JSON está corrupto? | No es un registro: el pipeline termina en `FALLIDO` con un mensaje claro, sin traceback y sin datos parciales. |
| ¿SQLite o PostgreSQL? | SQLite: lo permite la guía, no necesita servidor y el `.db` es entregable. El código usa la API DB-API 2.0, que es portable. |

**Prepárate también para:** por qué la mediana y no la media (Leslie) y por qué el LEFT JOIN (Yerik).
