"""Carga el modelo local antes de abrir el tótem para evitar esperas en la primera consulta."""

import sys
import time

import httpx

from .app import KEEP_ALIVE, MODEL, OLLAMA_URL


def main() -> int:
    start = time.monotonic()
    with httpx.Client(trust_env=False) as client:
        models = None
        for _ in range(15):
            try:
                response = client.get(f"{OLLAMA_URL}/api/tags", timeout=1)
                response.raise_for_status()
                models = response.json().get("models", [])
                break
            except (httpx.HTTPError, ValueError):
                time.sleep(1)
        if models is None:
            print("Ollama local no está iniciado. Quíbar seguirá en modo básico.", flush=True)
            return 1
        if not any(item.get("name") == MODEL for item in models):
            print(f"Falta el modelo local. Instálalo con: ollama pull {MODEL}", flush=True)
            return 1

        print(f"Cargando {MODEL} en este equipo; la primera vez puede tardar…", flush=True)
        try:
            response = client.post(f"{OLLAMA_URL}/api/generate",
                                   json={"model": MODEL, "stream": False, "keep_alive": KEEP_ALIVE},
                                   timeout=90)
            response.raise_for_status()
            if not response.json().get("done"):
                raise ValueError("Ollama no confirmó que el modelo esté cargado")
        except httpx.HTTPStatusError as error:
            print(f"Ollama no pudo cargar el modelo: {error.response.text[:250]}", flush=True)
            return 1
        except (httpx.HTTPError, ValueError) as error:
            print(f"Ollama no pudo cargar el modelo: {error}", flush=True)
            return 1
    print(f"IA local lista ({int(time.monotonic() - start)} s).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
