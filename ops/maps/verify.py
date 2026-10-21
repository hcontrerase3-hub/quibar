"""Validate the upstream checksum before accepting a country download."""
import hashlib
from pathlib import Path

root = Path('/work')
source = root / 'chile-latest.osm.pbf.part'
expected = (root / 'chile-latest.osm.pbf.md5').read_text().split()[0]
with source.open('rb') as stream:
    actual = hashlib.file_digest(stream, 'md5').hexdigest()
if actual != expected:
    raise ValueError('La descarga no coincide con la suma publicada por Geofabrik')
source.rename(root / 'chile-latest.osm.pbf')
print('Descarga OSM verificada:', actual)
