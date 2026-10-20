#!/bin/bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
project="quibar-acceptance-$$"
export QUIBAR_PORT=0 OLLAMA_URL=http://127.0.0.1:1
dc=(docker compose -p "$project" --env-file docker.env.example -f compose.yaml --profile tools)
cleanup() {
  status=$?
  if [[ "$status" != 0 ]]; then "${dc[@]}" logs --tail 80 || true; fi
  # Only this script's unique, disposable project is removed with its volumes.
  "${dc[@]}" down --volumes --remove-orphans
}
trap cleanup EXIT
"${dc[@]}" up -d --build --wait app nginx maintenance
"${dc[@]}" run --rm --no-deps -e QUIBAR_DB_PATH=/tmp/tests.sqlite3 tools python -m unittest backend.test_quibar backend.test_stack backend.test_container -v
"${dc[@]}" run --rm --no-deps -e QUIBAR_SMOKE=temporary-data-only tools python -m backend.container_smoke
"${dc[@]}" up -d --force-recreate --wait app nginx
"${dc[@]}" run --rm --no-deps -e QUIBAR_SMOKE=temporary-data-only -e QUIBAR_SMOKE_PHASE=persist tools python -m backend.container_smoke
"${dc[@]}" stop app maintenance
"${dc[@]}" run --rm -T --no-deps tools python -m backend.container_ops backup /tmp/verified-backup.tar.gz
echo 'Aceptación Docker completada; los datos de producción no se usaron.'
