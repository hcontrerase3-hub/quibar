"""Importación explícita de una extracción vial OSM PBF; nunca borra el grafo previo."""
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile

from .db import ROOT


def install_roads(source, replace=False):
    source = Path(source).resolve()
    target = Path(os.environ.get('QUIBAR_ROUTING_DIR', str(ROOT / 'data/routing'))).resolve()
    if not source.is_file() or b'OSMHeader' not in source.open('rb').read(256):
        raise ValueError('Se requiere una extracción OpenStreetMap .osm.pbf válida del circuito y sus conexiones')
    if target in source.parents:
        raise ValueError('El origen debe estar fuera del directorio de datos viales')
    if target.exists() and any(target.iterdir()) and not replace:
        raise ValueError('Ya existen datos viales. Respalda y usa --replace para sustituirlos')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix='.roads-') as temporary:
        staging = Path(temporary) / 'routing'
        staging.mkdir()
        shutil.copyfile(source, staging / 'region.osm.pbf')
        if os.geteuid() == 0:
            for item in [staging, staging / 'region.osm.pbf']:
                os.chown(item, 10001, 10001)
        if target.exists():
            if any(target.iterdir()):
                saved = target.with_name('routing.previous-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
                target.rename(saved)
            else:
                target.rmdir()
        staging.rename(target)
    return {'installed': str(target), 'status': 'Pendiente de construir por Valhalla; revisa logs routing'}
