"""Lotes explícitos de lugares ficticios sobre caminos OSM, sin carga automática."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import httpx
from sqlalchemy import select

from .admin import BusinessData, apply_data
from .db import session
from .models import Auditoria, Comercio, PuntoInteres, Usuario
from .territory import InterestData, station, within

BATCH = 'circuit-v1'
COUNTS = {'Santa Bárbara': (10, 7), 'Huequecura': (10, 7), 'Ralco': (10, 6)}
BUSINESSES = [('Gastronomía', 'Cocina', 'food'), ('Alojamiento', 'Hospedaje', 'stay'),
              ('Artesanía', 'Taller artesanal', 'craft'), ('Turismo', 'Excursiones', 'outdoors'),
              ('Comercio', 'Almacén', 'shop')]
INTERESTS = ['Mirador', 'Naturaleza', 'Patrimonio', 'Plaza', 'Actividad', 'Cultura']


def distance(a, b):
    lon1, lat1, lon2, lat2 = map(radians, (*a, *b))
    value = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
    return 12742000 * asin(sqrt(min(1, value)))


def identifier(kind, index):
    return f'demo-{BATCH}-{kind}-{index:02d}'


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_route(client, url, origin, point):
    proofs = {}
    for profile, costing in [('walking', 'pedestrian'), ('driving', 'auto')]:
        response = client.post(url.rstrip('/') + '/route', json={
            'locations': [{'lat': lat, 'lon': lon, 'type': 'break', 'search_cutoff': 100, 'radius': 50}
                          for lon, lat in [(origin['longitude'], origin['latitude']), point]],
            'costing': costing, 'shape_format': 'polyline6',
            'directions_options': {'units': 'kilometers', 'language': 'es-ES'}})
        if response.status_code in (400, 404):
            return None
        response.raise_for_status()
        trip = response.json()['trip']
        if trip.get('status', 0) != 0:
            return None
        proofs[profile] = trip['summary']
    return proofs


def prepare(roads_path, places_path, output, public_url, routing_url):
    output = Path(output)
    if output.exists():
        raise ValueError('El manifiesto ya existe; se conserva el lote anterior')
    roads = json.loads(Path(roads_path).read_text())['features']
    settlements = json.loads(Path(places_path).read_text())['features']
    with httpx.Client(trust_env=False, timeout=15) as client:
        response = client.get(public_url.rstrip('/') + '/api/quibar/places')
        response.raise_for_status()
        origin = response.json()['station']
        if not origin['configured']:
            raise ValueError('Configura y verifica el tótem antes de preparar el lote')
        anchors = {'Huequecura': [origin['longitude'], origin['latitude']]}
        for name in ['Santa Bárbara', 'Ralco']:
            anchors[name] = next(f['geometry']['coordinates'] for f in settlements if f['properties'].get('name') == name)
        entries, used = [], []
        indices = Counter()
        for sector, (business_count, interest_count) in COUNTS.items():
            candidates = []
            for road in roads:
                tags = road['properties']
                if tags.get('kind') not in ('primary', 'secondary', 'tertiary', 'residential', 'unclassified', 'living_street'):
                    continue
                if road['geometry']['type'] != 'LineString':
                    continue
                for point in road['geometry']['coordinates']:
                    if within(point[1], point[0]) and distance(point, anchors[sector]) <= 5000:
                        candidates.append((distance(point, anchors[sector]), point, tags))
            candidates.sort(key=lambda item: (item[0], item[1]))
            selected = []
            for _, point, tags in candidates:
                if any(distance(point, previous) < 250 for previous in used):
                    continue
                proof = verify_route(client, routing_url, origin, point)
                if proof is None:
                    continue
                used.append(point)
                selected.append((point, tags, proof))
                if len(selected) == business_count + interest_count:
                    break
            if len(selected) != business_count + interest_count:
                raise ValueError(f'No se encontraron suficientes puntos conectados en {sector}; no se cargó nada')
            # Interleave types so a short route has both commerces and attractions.
            kinds = ['interest' if i % 2 == 0 and i // 2 < interest_count else 'business'
                     for i in range(len(selected))]
            for kind, (point, tags, proof) in zip(kinds, selected):
                indices[kind] += 1
                number = indices[kind]
                road_name = tags.get('name') or tags.get('ref') or 'camino OSM sin nombre'
                source = f'OSM local · {road_name}. Conexión técnica con Valhalla a pie y en vehículo; sin verificación en terreno.'
                common = dict(commune='Alto Biobío' if sector == 'Ralco' else 'Santa Bárbara', sector=sector,
                              latitude=point[1], longitude=point[0], demo=True, status='Aprobado',
                              hours='Horario ficticio de ejemplo: 09:00–18:00',
                              description=f'Lugar ficticio de demostración en el sector {sector}. Permite probar recomendaciones y rutas. No representa un establecimiento o atractivo real ni un acceso comprobado en terreno.')
                if kind == 'business':
                    category, title, visual = BUSINESSES[(number-1) % len(BUSINESSES)]
                    data = dict(**common, name=f'{title} de ejemplo {number:02d} · {sector}', category=category,
                                summary=f'Comercio ficticio para probar recorridos y recomendaciones en {sector}.',
                                area=f'Posición de demostración sobre {road_name}', offerings=['Servicio ficticio de demostración'],
                                visual=visual, location_source=source, location_verified=True)
                else:
                    category = INTERESTS[(number-1) % len(INTERESTS)]
                    data = dict(**common, name=f'{category} de ejemplo {number:02d} · {sector}', category=category,
                                access='Punto sobre camino cartografiado para pruebas; no representa una visita o acceso real verificado.',
                                source=source, access_verified=True)
                entries.append({'id': identifier(kind, number), 'kind': kind, 'data': data, 'road': tags, 'routes': proof})
            print(f'{sector}: {business_count} comercios y {interest_count} atractivos conectados', flush=True)
    manifest = dict(batch=BATCH, created_at=datetime.now(timezone.utc).isoformat(), origin=origin,
                    source='© OpenStreetMap contributors · ODbL; red local instalada',
                    roads_sha256=file_hash(roads_path), places_sha256=file_hash(places_path), entries=entries)
    validate(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return {'manifest': str(output), 'count': len(entries)}


def validate(manifest):
    if manifest.get('batch') != BATCH:
        raise ValueError('Lote de demostración desconocido')
    entries = manifest['entries']
    expected = {identifier(kind, i) for kind, count in [('business', 30), ('interest', 20)] for i in range(1, count+1)}
    if len(entries) != 50 or {e['id'] for e in entries} != expected:
        raise ValueError('El lote debe contener exactamente 30 comercios y 20 atractivos con identificadores propios')
    counts = Counter()
    points = set()
    for entry in entries:
        kind = entry['kind']
        if kind not in ('business', 'interest') or not entry['id'].startswith(f'demo-{BATCH}-{kind}-'):
            raise ValueError('Tipo o identificador ajeno al lote')
        data = (BusinessData if kind == 'business' else InterestData).model_validate(entry['data'])
        if not data.demo or data.status != 'Aprobado' or data.latitude is None or data.longitude is None or not within(data.latitude, data.longitude):
            raise ValueError('Todos los registros deben ser ejemplos aprobados dentro del circuito')
        if kind == 'business' and (not data.location_verified or len(data.location_source) < 5):
            raise ValueError('Falta la comprobación técnica de ubicación')
        if set(entry['routes']) != {'walking', 'driving'}:
            raise ValueError('Faltan las comprobaciones de ambos perfiles')
        points.add((data.latitude, data.longitude))
        counts[(data.sector, kind)] += 1
    if len(points) != 50 or any(counts[(s, k)] != n for s, pair in COUNTS.items() for k, n in zip(['business', 'interest'], pair)):
        raise ValueError('Coordenadas duplicadas o distribución del lote incorrecta')
    return entries


def apply(manifest, admin_id, suspend=False):
    entries = validate(manifest)
    with session() as db:
        admin = db.get(Usuario, admin_id)
        if not admin or not admin.activo or admin.rol != 'Administrador':
            raise ValueError('Indica un administrador activo para registrar la operación en auditoría')
        changed, skipped = 0, 0
        pending = []
        for entry in entries:
            if entry['kind'] == 'business':
                row = db.scalar(select(Comercio).where(Comercio.public_id == entry['id']))
            else:
                row = db.get(PuntoInteres, entry['id'])
            if row and not row.demo:
                raise ValueError(f"El registro {entry['id']} ya no está marcado como ficticio; se conserva sin cambios")
            if suspend:
                if row:
                    field = 'estado_moderacion' if entry['kind'] == 'business' else 'status'
                    if getattr(row, field) != 'Suspendido':
                        setattr(row, field, 'Suspendido')
                        changed += 1
                continue
            if row:
                skipped += 1
            else:
                pending.append(entry)
        if pending:
            origin = station()
            if not origin['configured']:
                raise ValueError('El tótem debe estar configurado')
            from .routes import road_route
            for entry in pending:
                data = entry['data']
                for profile in ['walking', 'driving']:
                    road_route([origin, data], profile)
                if entry['kind'] == 'business':
                    row = Comercio(public_id=entry['id'])
                    apply_data(db, row, BusinessData.model_validate(data), {'role': 'Administrador'})
                else:
                    row = PuntoInteres(id=entry['id'], **InterestData.model_validate(data).model_dump())
                db.add(row)
                changed += 1
        if changed:
            db.add(Auditoria(id_usuario=admin_id, tipo_operacion='SUSPENDER_DEMO' if suspend else 'CARGAR_DEMO',
                             detalle_json={'batch': BATCH, 'count': changed, 'ids': [e['id'] for e in entries]}, ip_origen='CLI local'))
            db.commit()
    return {'batch': BATCH, 'changed': changed, 'skipped': skipped, 'operation': 'suspend' if suspend else 'load'}
