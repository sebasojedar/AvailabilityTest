#!/usr/bin/env python3
"""
Metodo 1 — Validacion de enrutamiento (disponibilidad)

Envia las consultas de test_cases_m1.json al endpoint /validate/classify,
captura quality_attribute e intent resueltos por el clasificador y escribe
los resultados en results_m1_<timestamp>.csv.

Columnas del CSV:
  id, group, query,
  quality_attribute_esperado, quality_attribute_obtenido, qa_match,
  intent_esperado, intent_obtenido, intent_match,
  keyword_match, source, elapsed_s

  qa_match      : True | False
  intent_match  : True | False | N/A  (N/A cuando el caso no define intent_esperado)

Uso:
  python tests/validation/run_method1.py
"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' no esta instalado. Ejecuta: pip install requests")

BASE_URL  = "http://localhost:8000"
TIMEOUT_S = 60
DELAY_S   = 1.0

HERE            = Path(__file__).parent
TEST_CASES_PATH = HERE / "test_cases_m1.json"
TIMESTAMP       = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS_PATH    = HERE / f"results_m1_{TIMESTAMP}.csv"


def classify(query: str) -> dict:
    try:
        resp = requests.post(
            f"{BASE_URL}/validate/classify",
            data={"message": query},
            timeout=TIMEOUT_S,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError:
        return {"error": "connection_refused"}
    except requests.exceptions.HTTPError as exc:
        body = ""
        try:
            body = exc.response.json().get("detail", "")
        except Exception:
            pass
        return {"error": f"HTTP {exc.response.status_code}: {body}"}
    except Exception as exc:
        return {"error": str(exc)}


def run():
    if not TEST_CASES_PATH.exists():
        sys.exit(f"ERROR: no se encuentra {TEST_CASES_PATH}")

    try:
        requests.get(f"{BASE_URL}/docs", timeout=5)
    except requests.exceptions.ConnectionError:
        sys.exit(f"ERROR: no se puede conectar a {BASE_URL}")

    cases   = json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))
    results = []

    for idx, case in enumerate(cases, 1):
        t0     = time.time()
        result = classify(case["query"])
        elapsed = round(time.time() - t0, 1)

        intent_esperado = case.get("intent_esperado", "")

        if "error" in result:
            qa_obtenido    = "ERROR"
            intent_obtenido = ""
            kw_match       = ""
            source         = result["error"]
            qa_match       = False
            intent_match   = "N/A"
        else:
            raw_qa = result.get("quality_attribute")
            qa_obtenido = raw_qa if (raw_qa is not None and raw_qa != "") else "null"

            intent_obtenido = result.get("intent", "")
            kw_match        = result.get("keyword_match", "")
            source          = result.get("source", "")
            qa_match        = (qa_obtenido == case["quality_attribute_esperado"])
            intent_match    = (
                str(intent_obtenido == intent_esperado)
                if intent_esperado
                else "N/A"
            )

        results.append({
            "id":                         case["id"],
            "group":                      case["group"],
            "query":                      case["query"],
            "quality_attribute_esperado": case["quality_attribute_esperado"],
            "quality_attribute_obtenido": qa_obtenido,
            "qa_match":                   qa_match,
            "intent_esperado":            intent_esperado,
            "intent_obtenido":            intent_obtenido,
            "intent_match":               intent_match,
            "keyword_match":              kw_match,
            "source":                     source,
            "elapsed_s":                  elapsed,
        })

        if idx < len(cases):
            time.sleep(DELAY_S)

    with open(RESULTS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    run()
