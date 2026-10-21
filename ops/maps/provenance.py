"""Keep provenance next to generated data; no private catalogue contents."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import mapnik

root = Path('/work')
records = {}
for name in ('chile-latest.osm.pbf', 'region.osm.pbf', 'circuit.mbtiles'):
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
(root / 'provenance.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print('Procedencia y SHA256 guardados en provenance.json')
