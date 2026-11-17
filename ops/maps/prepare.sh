#!/bin/bash
# Explicit, reproducible data preparation; never downloads public OSM raster tiles.
set -Eeuo pipefail
style=classic
if [[ $# -gt 0 ]]; then
  [[ $# -eq 2 && "$1" == --style && ( "$2" == classic || "$2" == atlas ) ]] || {
    echo 'Uso: ops/maps/prepare.sh [--style classic|atlas]' >&2; exit 2;
  }
  style="$2"
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
command -v docker >/dev/null || { echo 'Se requiere Docker con Compose.' >&2; exit 1; }
root=$(pwd -P)
work="$root/.quibar/cartography"
mkdir -p "$work"
lock="$work/preparing.lock"
mkdir "$lock" 2>/dev/null || { echo 'Otra preparación está activa; revisa preparing.lock.' >&2; exit 1; }
trap 'rmdir "$lock"' EXIT
image=quibar-cartography:local
docker build -t "$image" -f ops/maps/Dockerfile ops/maps
run() { docker run --rm --user "$(id -u):$(id -g)" -v "$work:/work" -v "$root/ops/maps:/scripts:ro" "$image" "$@"; }
if [[ ! -s "$work/chile-latest.osm.pbf" ]]; then
  run curl -fL --retry 3 --connect-timeout 20 -o /work/chile-latest.osm.pbf.part https://download.geofabrik.de/south-america/chile-latest.osm.pbf
  run curl -fL --retry 3 --connect-timeout 20 -o /work/chile-latest.osm.pbf.md5 https://download.geofabrik.de/south-america/chile-latest.osm.pbf.md5
  run python3 /scripts/verify.py
fi
if [[ ! -s "$work/region.osm.pbf" ]]; then
  # Buffer around the display extent retains connecting roads and complete ways.
  run osmium extract --bbox=-72.45,-38.30,-70.95,-37.30 --strategy=complete_ways --set-bounds -o /work/region.part.osm.pbf /work/chile-latest.osm.pbf
  mv "$work/region.part.osm.pbf" "$work/region.osm.pbf"
fi
if [[ ! -s "$work/circuit.geojson" ]]; then
  run osmium export /work/region.osm.pbf -o /work/circuit.part.geojson
  mv "$work/circuit.part.geojson" "$work/circuit.geojson"
fi
package=circuit.mbtiles
render_args=()
if [[ "$style" == atlas ]]; then
  package=circuit-atlas.mbtiles
  run python3 /scripts/relief.py /work/relief
  render_args=(--style atlas --hillshade /work/relief/hillshade.tif)
fi
if [[ ! -s "$work/$package" ]]; then
  run python3 /scripts/render.py /work/circuit.geojson "/work/$package" "${render_args[@]}"
fi
run python3 /scripts/provenance.py --package "$package"
printf '%s\n' 'Archivos preparados en .quibar/cartography/. Para instalarlos:' \
  "./quibar importar-mapa .quibar/cartography/$package" \
  './quibar preparar-rutas .quibar/cartography/region.osm.pbf' \
  'Los archivos existentes se conservan. Para actualizar, archiva primero la carpeta.'
