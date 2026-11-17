"""Keep provenance next to generated data; no private catalogue contents."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3

import mapnik

root = Path('/work')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--package', choices=['circuit.mbtiles', 'circuit-atlas.mbtiles'], default='circuit.mbtiles')
args = parser.parse_args()
records = {}
for name in ('chile-latest.osm.pbf', 'region.osm.pbf', args.package):
    path = root / name
    with path.open('rb') as stream:
        records[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
record = {'source': 'https://download.geofabrik.de/south-america/chile-latest.osm.pbf',
          'license': 'ODbL 1.0; © OpenStreetMap contributors',
          'license_url': 'https://www.openstreetmap.org/copyright',
          'prepared_at': datetime.now(timezone.utc).isoformat(),
          'routing_bounds': [-72.45, -38.30, -70.95, -37.30],
          'raster_bounds': [-72.2, -38.05, -71.35, -37.55],
          'raster_zoom': [8, 16], 'files': records,
          'tools': {'mapnik': mapnik.mapnik_version_string(),
                    'osmium': subprocess.check_output(['osmium', '--version'], text=True).strip()},
          'source_osm_header': json.loads(subprocess.check_output(['osmium', 'fileinfo', '-j', str(root / 'chile-latest.osm.pbf')])),
          'osm_header': json.loads(subprocess.check_output(['osmium', 'fileinfo', '-j', str(root / 'region.osm.pbf')]))}
with sqlite3.connect(f'file:{root / args.package}?mode=ro', uri=True) as db:
    record['raster_metadata'] = dict(db.execute('SELECT name,value FROM metadata'))
destination = root / 'provenance.json'
if args.package == 'circuit-atlas.mbtiles':
    record['relief'] = json.loads((root / 'relief/relief.json').read_text())
    record['tools']['gdal'] = record['relief']['gdal']
    destination = root / 'provenance-atlas.json'
destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(f'Procedencia y SHA256 guardados en {destination.name}')
