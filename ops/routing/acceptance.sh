#!/bin/bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
project="quibar-geographic-$$"
export QUIBAR_PORT=0 OLLAMA_URL=http://127.0.0.1:1
root="$(pwd -P)"
fixture=$(mktemp -d)
dc=(docker compose -p "$project" --env-file docker.env.example -f compose.yaml --profile tools --profile territory)
cleanup() {
  status=$?
  if [[ "$status" != 0 ]]; then "${dc[@]}" logs --tail 50 || true; fi
  "${dc[@]}" down --volumes --remove-orphans
  rm -f -- "$fixture/region.osm.pbf"
  rmdir "$fixture"
}
trap cleanup EXIT
"${dc[@]}" build app speech
"${dc[@]}" run --rm --no-deps -T -v "$root/ops/routing:/test-scripts:ro" -v "$fixture:/fixture" --user 0:0 tools python /test-scripts/fixture.py /fixture/region.osm.pbf
"${dc[@]}" run --rm --no-deps --user 0:0 -v "$fixture/region.osm.pbf:/import/region.osm.pbf:ro" tools python -m backend.cli import-roads /import/region.osm.pbf
"${dc[@]}" up -d routing speech
"${dc[@]}" up -d --wait app nginx maintenance
"${dc[@]}" run --rm --no-deps -e QUIBAR_SMOKE=temporary-data-only tools python -m backend.service_smoke
"${dc[@]}" stop app maintenance routing
"${dc[@]}" run --rm -T --no-deps tools python -m backend.container_ops backup /tmp/geographic-backup.tar.gz
printf '%s\n' 'Aceptación geográfica completada con datos sintéticos y servicios reales.'
