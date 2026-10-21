#!/bin/bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
project="quibar-acceptance-$$"
export QUIBAR_PORT=0 QUIBAR_WEB_PORT=0 OLLAMA_URL=http://127.0.0.1:1
dc=(docker compose -p "$project" --env-file docker.env.example -f compose.yaml --profile tools)
cleanup() {
  status=$?
  if [[ "$status" != 0 ]]; then "${dc[@]}" logs --tail 80 || true; fi
  # Only this script's unique, disposable project is removed with its volumes.
  "${dc[@]}" down --volumes --remove-orphans
  docker volume rm "${project}_import" >/dev/null 2>&1 || true
}
trap cleanup EXIT
"${dc[@]}" up -d --build --wait app nginx maintenance
"${dc[@]}" run --rm --no-deps -e QUIBAR_DB_PATH=/tmp/tests.sqlite3 tools python -m unittest backend.test_quibar backend.test_stack backend.test_container backend.test_territory backend.test_routes -v
"${dc[@]}" run --rm --no-deps -e QUIBAR_SMOKE=temporary-data-only tools python -m backend.container_smoke
"${dc[@]}" up -d --force-recreate --wait app nginx
"${dc[@]}" run --rm --no-deps -e QUIBAR_SMOKE=temporary-data-only -e QUIBAR_SMOKE_PHASE=persist tools python -m backend.container_smoke
"${dc[@]}" stop app maintenance
"${dc[@]}" run --rm -T --no-deps tools python -m backend.container_ops backup /tmp/verified-backup.tar.gz
"${dc[@]}" run --rm --no-deps --user 0:0 -v "${project}_state:/import:ro" -v "${project}_import:/state" tools python -m backend.container_ops import /import
"${dc[@]}" run --rm --no-deps -v "${project}_import:/state" tools python -c 'from backend.db import approved; assert len(approved()) == 7; print("Importación accesible sin privilegios verificada")'
dev_dc=(docker compose -p "$project" --env-file docker.env.example -f compose.yaml -f compose.dev.yaml --profile tools)
dc=("${dev_dc[@]}")
"${dev_dc[@]}" up -d --wait app nginx web
"${dev_dc[@]}" exec -T web node -e "Promise.all(['/', '/api/quibar/health', '/app/page.tsx'].map(async p=>{const r=await fetch('http://127.0.0.1:3000'+p);if(!r.ok)throw Error(p+': '+r.status)})).catch(e=>{console.error(e);process.exit(1)})"
touch backend/app.py
reloaded=0
for attempt in {1..20}; do
  if "${dev_dc[@]}" logs app 2>&1 | grep 'Reloading' >/dev/null; then reloaded=1; break; fi
  sleep 1
done
[[ "$reloaded" == 1 ]] || { echo 'No se detectó recarga de Python' >&2; exit 1; }
"${dev_dc[@]}" exec -T web node -e "(async()=>{for(let i=0;i<30;i++){try{if((await fetch('http://127.0.0.1:3000/api/quibar/health')).ok)return}catch{}await new Promise(r=>setTimeout(r,500))}process.exit(1)})()"
"${dev_dc[@]}" stop web
"${dev_dc[@]}" rm -f web
echo 'Aceptación Docker completada; los datos de producción no se usaron.'
