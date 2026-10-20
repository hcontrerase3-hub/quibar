#!/bin/bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"
command -v node >/dev/null || { echo "Instala Node.js 22.13 o posterior"; exit 1; }
command -v python3 >/dev/null || { echo "Instala Python 3.10 o posterior"; exit 1; }
[[ -f .env ]] || cp .env.example .env
# .env is trusted local configuration owned by the operator.
set -a
source .env
set +a
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci
npm run build
if [[ -d /Applications/Ollama.app ]] && ! curl -fsS --max-time 1 "${OLLAMA_URL:-http://127.0.0.1:11434}/api/tags" >/dev/null; then
  open -a Ollama
fi
.venv/bin/python -m backend.preload || true
.venv/bin/python -m uvicorn backend.app:app --host "${QUIBAR_API_HOST:-127.0.0.1}" --port "${QUIBAR_API_PORT:-8000}" &
api_pid=$!
cleanup() { kill "$api_pid" 2>/dev/null || true; wait "$api_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
url="http://${QUIBAR_API_HOST:-127.0.0.1}:${QUIBAR_API_PORT:-8000}"
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if curl -fsS --max-time 1 "$url/api/quibar/health" >/dev/null; then ready=1; break; fi
  kill -0 "$api_pid" 2>/dev/null || break
  sleep 1
done
[[ "$ready" == 1 ]] || { echo "La API no pudo iniciar"; exit 1; }
if [[ -d '/Applications/Google Chrome.app' ]]; then
  open -na 'Google Chrome' --args --kiosk "$url"
elif command -v open >/dev/null; then
  open "$url"
fi
echo "Quíbar disponible en $url. Ctrl+C detiene el servidor."
wait "$api_pid"
