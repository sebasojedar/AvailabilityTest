# ArquIA — Validación Método 1: Enrutamiento

Pruebas automatizadas de validación del clasificador de atributos de calidad de **ArquIA**.
Corresponde a la versión funcional de ArquIA operativa en **junio de 2026**.

---

## Contexto

Este repositorio es independiente del repositorio original de ArquIA. Contiene únicamente la carpeta de validación del Método 1, diseñada para integrarse con el backend de ArquIA ya existente.

El Método 1 verifica que el nodo `classifier` del grafo LangGraph resuelva correctamente el atributo de calidad (`quality_attribute`) y la intención (`intent`) de una consulta de entrada, como condición previa al enrutamiento hacia los nodos especializados (`style_disponibilidad`, `tactics_disponibilidad`, etc.).

---

## Estructura

```
validation/
├── Script_enrouting.py      # Script de ejecución
├── test_cases_m1.json       # 52 casos de prueba en 8 grupos
├── results_m1_<ts>.csv      # Resultados generados (se crea al ejecutar)
└── README.md
```

---

## Integración con el repositorio original de ArquIA

### Paso 1 — Copiar la carpeta

Descarga este repositorio y copia la carpeta `validation/` dentro de `back/tests/` del repositorio original de ArquIA:

```
archIABack/
└── back/
    └── tests/
        └── validation/          ← pegar aquí
            ├── Script_enrouting.py
            ├── test_cases_m1.json
            └── README.md
```

### Paso 2 — Agregar el endpoint de validación en `main.py`

El script depende de un endpoint auxiliar `POST /validate/classify` que no existe en el backend por defecto. Agrégalo en `back/src/main.py` antes del bloque `# /feedback`:

```python
@app.post("/validate/classify")
async def validate_classify(message: str = Form(...)):
    from src.graph.nodes.classifier import _classify_cached
    from src.graph.qa_registry import normalize_qa, detect_explicit_qa, supported_qas

    qa_ids = supported_qas()
    qa_opts_str = ", ".join(f'"{q}"' for q in qa_ids + ["general"])

    qa_attr_raw = "general"
    intent_raw  = "other"
    source      = "llm"

    try:
        _, intent_raw, _, qa_attr_raw = _classify_cached(message, qa_opts_str)
    except Exception as exc:
        source = f"keyword_fallback ({exc.__class__.__name__})"

    qa_normalized = normalize_qa(qa_attr_raw)
    keyword_qa    = detect_explicit_qa(message)

    if qa_normalized != "general":
        quality_attribute = qa_normalized
    elif keyword_qa != "general":
        quality_attribute = keyword_qa
        source = source + "+keyword"
    else:
        quality_attribute = "general"

    return {
        "quality_attribute":     quality_attribute,
        "quality_attribute_raw": qa_attr_raw,
        "intent":                intent_raw,
        "keyword_match":         keyword_qa,
        "source":                source,
    }
```

> El endpoint es stateless: no crea sesión, no pasa por el flujo de intake y no escribe en la base de datos. Llama directamente a la lógica de clasificación del LLM con fallback a detección por keywords.

---

## Requisitos

- Python 3.10+
- Librería `requests`: `pip install requests`
- El backend de ArquIA corriendo en `http://localhost:8000`
- Variable `OPENAI_API_KEY` configurada en `back/.env`

---

## Ejecución

### 1. Levantar el backend de ArquIA

Desde la carpeta `back/` del repositorio original:

```bash
uvicorn src.main:app --reload
```

Esperar hasta ver en consola:
```
[startup] RAG listo
[startup] Checkpointer listo: ...
```

### 2. Ejecutar el script

Desde la raíz del repositorio original (`archIABack/`):

```bash
python back/tests/validation/Script_enrouting.py
```

El script no produce salida en consola. Al finalizar, genera un archivo `results_m1_YYYYMMDD_HHMMSS.csv` en la misma carpeta.

> Con 52 casos y ~6 segundos por llamada al LLM, la ejecución completa toma aproximadamente **5-6 minutos**.

---

## Casos de prueba

Los 52 casos están organizados en 8 grupos en `test_cases_m1.json`:

| Grupo | IDs | Descripción | QA esperado |
|---|---|---|---|
| `disponibilidad_keywords` | A01–A10 | Consultas con vocabulario técnico explícito de disponibilidad | `disponibilidad` |
| `otros_atributos` | B01–B10 | Consultas de latencia (B01–B05) y escalabilidad (B06–B10) | `latencia` / `escalabilidad` |
| `ambiguos` | C01–C10 | Disponibilidad en lenguaje de negocio, sin keywords del índice | `disponibilidad` |
| `negativos_trampa` | D01–D05 | Keywords de disponibilidad en contextos no-disponibilidad | mixto |
| `intent_estilos` | E01–E04 | Solicitudes explícitas de estilo arquitectónico | `disponibilidad`, `intent=style` |
| `intent_tacticas` | F01–F04 | Solicitudes explícitas de tácticas | `disponibilidad`, `intent=tactics` |
| `atributos_sin_nodo` | G01–G05 | Atributos sin nodo especializado (seguridad, usabilidad, etc.) | `general` |
| `limite_robustez` | H01–H04 | Casos límite: input mínimo, saludo, conflicto de atributos | mixto |

Los grupos D, E, F y H incluyen el campo `intent_esperado` para validar también la dimensión de intención.

---

## Salida — columnas del CSV

| Columna | Descripción |
|---|---|
| `id` | Identificador del caso (A01, B03, etc.) |
| `group` | Grupo al que pertenece |
| `query` | Consulta enviada |
| `quality_attribute_esperado` | QA definido como correcto en el caso |
| `quality_attribute_obtenido` | QA devuelto por el clasificador |
| `qa_match` | `True` si ambos coinciden |
| `intent_esperado` | Intención esperada (vacío si el caso no la define) |
| `intent_obtenido` | Intención devuelta por el clasificador |
| `intent_match` | `True` / `False` / `N/A` |
| `keyword_match` | QA detectado solo por búsqueda de keywords (control) |
| `source` | `llm` si clasificó el LLM, `keyword_fallback` si falló y usó keywords |
| `elapsed_s` | Tiempo de respuesta en segundos |

---

## Nota sobre `intent_match` en el grupo E

Los casos E01–E04 tienen `intent_esperado = "style"`. El script evalúa la capa LLM del clasificador en aislamiento, sin las sobreescrituras por expresiones regulares que aplica el `classifier_node` completo. En el pipeline real, la presencia de la palabra "estilo" fuerza `intent = "style"` independientemente del LLM. Por esta razón, `intent_match = False` en el grupo E es un artefacto del método de prueba, no un defecto del sistema.
