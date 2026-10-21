"""Render genuine OSM geometry into an offline raster MBTiles, without tile scraping."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import sqlite3
from xml.sax.saxutils import escape

import mapnik
from PIL import Image

BOUNDS = (-72.2, -38.05, -71.35, -37.55)
MERCATOR = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +no_defs'
WGS84 = '+proj=longlat +datum=WGS84 +no_defs'
WORLD = 20037508.342789244


def categorize(source, directory):
    groups = {key: [] for key in ('forest', 'land', 'water', 'rivers', 'roads', 'buildings', 'places')}
    for feature in json.loads(source.read_text())['features']:
        tags = feature['properties']
        geometry = feature.get('geometry') or {}
        shape = geometry.get('type', '')
        polygon = shape in ('Polygon', 'MultiPolygon')
        line = shape in ('LineString', 'MultiLineString')
        group = kind = None
        if polygon:
            if tags.get('natural') == 'water' or tags.get('water') or tags.get('landuse') == 'reservoir':
                group, kind = 'water', 'water'
            elif tags.get('natural') in ('wood', 'scrub') or tags.get('landuse') == 'forest':
                group, kind = 'forest', 'forest'
            elif tags.get('landuse') in ('residential', 'commercial', 'industrial', 'farmland', 'meadow', 'orchard'):
                group, kind = 'land', tags['landuse']
            elif tags.get('building'):
                group, kind = 'buildings', 'building'
        elif line:
            if tags.get('highway'):
                group, kind = 'roads', tags['highway']
            elif tags.get('waterway'):
                group, kind = 'rivers', tags['waterway']
        elif shape == 'Point' and tags.get('place') in ('city', 'town', 'village', 'hamlet', 'locality', 'suburb'):
            group, kind = 'places', tags['place']
        if group:
            # Do not publish commercial POIs or guess names. Labels come only from OSM.
            groups[group].append({'type': 'Feature', 'geometry': geometry,
                                  'properties': {'name': tags.get('name', ''), 'ref': tags.get('ref', ''), 'kind': kind}})
    for group, features in groups.items():
        (directory / (group + '.geojson')).write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))
    print('Geometrías OSM:', {k: len(v) for k, v in groups.items()}, flush=True)
    return groups


def style(directory, zoom):
    styles, layers = [], []
    def add(name, group, rules):
        styles.append(f'<Style name="{name}">{rules}</Style>')
        path = escape(str(directory / (group + '.geojson')))
        layers.append(f'<Layer name="{name}" srs="{WGS84}"><StyleName>{name}</StyleName><Datasource><Parameter name="type">geojson</Parameter><Parameter name="file">{path}</Parameter></Datasource></Layer>')
    def rule(symbol, condition=None):
        return '<Rule>' + (f'<Filter>{escape(condition)}</Filter>' if condition else '') + symbol + '</Rule>'
    add('land', 'land', rule('<PolygonSymbolizer fill="#ece9df"/>'))
    add('forest', 'forest', rule('<PolygonSymbolizer fill="#d5e3c8"/>'))
    add('water', 'water', rule('<PolygonSymbolizer fill="#aad2df"/>'))
    add('rivers', 'rivers', rule(f'<LineSymbolizer stroke="#8ebfce" stroke-width="{1 if zoom < 13 else 2}"/>'))
    if zoom >= 14:
        add('buildings', 'buildings', rule('<PolygonSymbolizer fill="#d5c9b9"/><LineSymbolizer stroke="#c2b7a8" stroke-width="0.3"/>'))
    main = "[kind] = 'motorway' or [kind] = 'trunk' or [kind] = 'primary' or [kind] = 'secondary' or [kind] = 'tertiary'"
    minor = "[kind] = 'residential' or [kind] = 'unclassified' or [kind] = 'service' or [kind] = 'living_street'"
    path = "[kind] = 'track' or [kind] = 'path' or [kind] = 'footway' or [kind] = 'cycleway' or [kind] = 'steps'"
    width = max(1.5, (zoom - 9) * .75)
    add('road-casing', 'roads', rule(f'<LineSymbolizer stroke="#bbad96" stroke-width="{width + 1.5}" stroke-linejoin="round" stroke-linecap="round"/>', main))
    add('main-roads', 'roads', rule(f'<LineSymbolizer stroke="#fff5d5" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>', main))
    if zoom >= 12:
        add('minor-roads', 'roads', rule(f'<LineSymbolizer stroke="#fffefa" stroke-width="{max(1, width - 1)}" stroke-linejoin="round"/>', minor))
    if zoom >= 14:
        add('trails', 'roads', rule('<LineSymbolizer stroke="#a3947e" stroke-width="1" stroke-dasharray="3,3"/>', path))
    if zoom >= 12:
        add('road-refs', 'roads', rule('<TextSymbolizer face-name="DejaVu Sans Book" size="10" fill="#6a5b43" halo-fill="#fff9e9" halo-radius="1.5" placement="line" spacing="350" minimum-distance="160">[ref]</TextSymbolizer>', main + " and [ref] != ''"))
    if zoom >= 15:
        add('street-names', 'roads', rule('<TextSymbolizer face-name="DejaVu Sans Book" size="10" fill="#5b6257" halo-fill="#fffefa" halo-radius="1.3" placement="line" spacing="250" minimum-distance="100">[name]</TextSymbolizer>', "[name] != ''"))
    types = ['city', 'town'] + (['village'] if zoom >= 10 else []) + (['hamlet', 'suburb'] if zoom >= 12 else []) + (['locality'] if zoom >= 14 else [])
    # Large settlements first so label collision gives them priority.
    for kind in types:
        size = 14 if kind in ('city', 'town') else 12 if kind == 'village' else 10
        add('place-' + kind, 'places', rule(f'<TextSymbolizer face-name="DejaVu Sans Book" size="{size}" fill="#344a3c" halo-fill="#f7f7ee" halo-radius="2" wrap-width="110" minimum-distance="60">[name]</TextSymbolizer>', f"[kind] = '{kind}' and [name] != ''"))
    return f'<Map srs="{MERCATOR}" background-color="#f1f0e5" buffer-size="64">' + ''.join(styles + layers) + '</Map>'


def tile(longitude, latitude, zoom):
    count = 2 ** zoom
    return (int((longitude + 180) / 360 * count),
            int((1 - math.asinh(math.tan(math.radians(latitude))) / math.pi) / 2 * count))


def render(source, target, min_zoom, max_zoom):
    if target.exists():
        raise ValueError('El destino ya existe; conserva el paquete previo antes de generar otro')
    directory = source.parent / 'layers'
    directory.mkdir(exist_ok=True)
    groups = categorize(source, directory)
    west, south, east, north = BOUNDS
    temporary = target.with_suffix('.mbtiles.part')
    if temporary.exists():
        raise ValueError('Existe una generación incompleta; revisa el archivo .part antes de continuar')
    db = sqlite3.connect(temporary)
    db.executescript('CREATE TABLE metadata(name TEXT PRIMARY KEY,value TEXT); CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB, PRIMARY KEY(zoom_level,tile_column,tile_row));')
    metadata = {'name': 'Quíbar · Santa Bárbara–Huequecura–Ralco', 'type': 'baselayer', 'version': '1.0',
                'description': 'Cartografía simplificada generada localmente desde OpenStreetMap/Geofabrik. No certifica accesos ni apertura.',
                'format': 'png', 'bounds': ','.join(map(str, BOUNDS)), 'minzoom': str(min_zoom), 'maxzoom': str(max_zoom),
                'attribution': '© OpenStreetMap contributors · ODbL · Datos Geofabrik · Estilo Quíbar',
                'source': 'https://download.geofabrik.de/south-america/chile.html',
                'generated_at': datetime.now(timezone.utc).isoformat()}
    db.executemany('INSERT INTO metadata VALUES (?,?)', metadata.items())
    counts = Counter()
    for zoom in range(min_zoom, max_zoom + 1):
        left, top = tile(west, north, zoom)
        right, bottom = tile(east, south, zoom)
        # A tile of margin prevents missing-tile warnings around the first viewport.
        left, top = max(0, left - 1), max(0, top - 1)
        right, bottom = min(2 ** zoom - 1, right + 1), min(2 ** zoom - 1, bottom + 1)
        m = mapnik.Map(1152, 1152)
        mapnik.load_map_from_string(m, style(directory, zoom), True)
        step = 2 * WORLD / 2 ** zoom
        # 4x4 metatiles plus 64px padding keep labels continuous at tile seams.
        for x in range(left // 4 * 4, right + 1, 4):
            for y in range(top // 4 * 4, bottom + 1, 4):
                pad = step / 4
                m.zoom_to_box(mapnik.Box2d(-WORLD + x * step - pad, WORLD - (y + 4) * step - pad,
                                          -WORLD + (x + 4) * step + pad, WORLD - y * step + pad))
                image = mapnik.Image(1152, 1152)
                mapnik.render(m, image)
                pixels = Image.open(io.BytesIO(image.tostring('png')))
                for dx in range(4):
                    for dy in range(4):
                        tx, ty = x + dx, y + dy
                        if not (left <= tx <= right and top <= ty <= bottom):
                            continue
                        output = io.BytesIO()
                        pixels.crop((64 + dx * 256, 64 + dy * 256, 320 + dx * 256, 320 + dy * 256)).save(output, format='PNG')
                        db.execute('INSERT INTO tiles VALUES (?,?,?,?)', (zoom, tx, 2 ** zoom - 1 - ty, output.getvalue()))
                        counts[zoom] += 1
            db.commit()
        print(f'Zoom {zoom}: {counts[zoom]} teselas', flush=True)
    assert db.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    db.close()
    temporary.rename(target)
    print(json.dumps({'output': str(target), 'tiles': dict(counts), 'bytes': target.stat().st_size,
                      'features': {k: len(v) for k, v in groups.items()}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--min-zoom', type=int, default=8)
    parser.add_argument('--max-zoom', type=int, default=16)
    args = parser.parse_args()
    if not 0 <= args.min_zoom <= args.max_zoom <= 19:
        parser.error('El rango de zoom debe estar entre 0 y 19')
    render(args.source, args.target, args.min_zoom, args.max_zoom)
