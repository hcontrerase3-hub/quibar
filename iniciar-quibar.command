#!/bin/bash
set -e

cd "$(dirname "$0")"
export NEXT_TELEMETRY_DISABLED=1

pause_on_error() {
  echo "Revisa el error indicado arriba."
  read -r -p "Presiona Enter para cerrar..." _
}
trap pause_on_error ERR

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Instala Node.js 22.13 o posterior antes de iniciar Quíbar."
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
  echo "Instala Python 3.10 o posterior antes de iniciar Quíbar."
  exit 1
fi
if command -v lsof >/dev/null 2>&1; then
  for port in 3000 8000; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "El puerto $port está ocupado. Cierra el servidor anterior y vuelve a intentarlo."
      exit 1
    fi
  done
fi

if [ ! -d .venv ]; then
  echo "Creando el entorno Python local..."
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi, uvicorn, httpx' >/dev/null 2>&1; then
  echo "Instalando dependencias del asistente local..."
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
if [ ! -d node_modules ]; then
  echo "Instalando dependencias del sitio..."
  npm ci
fi
if [ ! -f .next/BUILD_ID ]; then
  echo "Preparando el prototipo..."
  npm run build
fi

# Ollama se ejecuta en el propio computador; sin él sigue el modo básico.
if ! curl -fsS --max-time 1 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && [ -d "/Applications/Ollama.app" ]; then
  open -a Ollama || true
fi
if ! .venv/bin/python -m backend.preload; then
  echo "El catálogo seguirá disponible aunque la IA no pueda iniciarse."
fi

.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
api_pid=$!
web_pid=""
cleanup() {
  [ -z "$web_pid" ] || kill "$web_pid" 2>/dev/null || true
  kill "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ready=0
for attempt in {1..30}; do
  if curl -fs --max-time 1 -o /dev/null http://127.0.0.1:8000/api/quibar/health 2>/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$api_pid" 2>/dev/null; then break; fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "No pudo iniciar la API local."
  exit 1
fi

echo "Iniciando Quíbar en http://localhost:3000/"
./node_modules/.bin/next start --hostname 127.0.0.1 -p 3000 &
web_pid=$!
ready=0
for attempt in {1..30}; do
  if curl -fs --max-time 1 -o /dev/null http://127.0.0.1:3000/ 2>/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$web_pid" 2>/dev/null; then break; fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "No pudo iniciar la página local."
  exit 1
fi

if [ -d "/Applications/Google Chrome.app" ]; then
  open -na "Google Chrome" --args --kiosk http://localhost:3000/
else
  open http://localhost:3000/
fi

echo "Mantén esta ventana abierta mientras uses el tótem."
wait "$web_pid"
