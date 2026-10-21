#!/bin/sh
set -eu
mkdir -p /state/routing
if [ ! -e /custom_files/region.osm.pbf ] && [ ! -L /custom_files ]; then
  rmdir /custom_files
  ln -s /state/routing /custom_files
fi
# No downloads or fake roads at normal startup. Preparation is an explicit action.
while [ ! -s /custom_files/region.osm.pbf ] && [ ! -s /custom_files/valhalla_tiles.tar ]; do
  echo 'Datos viales pendientes: ejecuta quibar preparar-rutas /ruta/region.osm.pbf'
  sleep 30
done
exec /valhalla/scripts/docker-entrypoint.sh build_tiles
