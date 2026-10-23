"""Lotes de demostración: transacciones, migración y conservación de datos."""
import copy
import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import select, text

from .db import db_path, engine, initialize, session, _initialized
from .demo_points import BATCH, COUNTS, apply, identifier, validate
from .models import Auditoria, Comercio, PuntoInteres
from .security import create_user
from .territory import public_places


def manifest():
    entries = []
    numbers = {'business': 0, 'interest': 0}
    for sector, counts in COUNTS.items():
        for kind, count in zip(['business', 'interest'], counts):
            for _ in range(count):
                numbers[kind] += 1
                data = dict(name=f'Lugar ficticio de test {len(entries)}', category='Comercio' if kind == 'business' else 'Mirador',
                            commune='Alto Biobío' if sector == 'Ralco' else 'Santa Bárbara', sector=sector,
                            latitude=-37.8 + len(entries) * .0001, longitude=-71.8,
                            description='Fixture sintético exclusivo de pruebas', hours='Horario ficticio', demo=True, status='Aprobado')
                if kind == 'business':
                    data.update(summary='Ficha sintética de prueba', area='Referencia sintética', offerings=['Producto de prueba'],
                                location_source='Fixture sintético', location_verified=True)
                else:
                    data.update(access='Acceso sintético', source='Fixture sintético', access_verified=True)
                entries.append(dict(kind=kind, id=identifier(kind, numbers[kind]), data=data,
                                    routes={'walking': {}, 'driving': {}}))
    return {'batch': BATCH, 'entries': entries}


class DemoPointsAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'QUIBAR_DB_PATH': self.tmp.name + '/demo.sqlite3'})
        self.env.start()
        initialize()
        create_user('admin@demo.test', 'Admin de prueba', 'password-demo-test-only')
        self.routes = patch('backend.routes.road_route', return_value={})
        self.route = self.routes.start()
        self.origin = patch('backend.demo_points.station', return_value={
            'configured': True, 'latitude': -37.727, 'longitude': -71.812, 'name': 'Tótem de test'})
        self.origin.start()

    def tearDown(self):
        self.origin.stop()
        self.routes.stop()
        self.env.stop()
        self.tmp.cleanup()

    def test_load_is_idempotent_preserves_edits_and_suspends_only_its_batch(self):
        with session() as db:
            original = db.scalar(select(Comercio).where(Comercio.public_id == 'bosque-sereno'))
            original.nombre_fantasia = 'Camping editado que se conserva'
            db.commit()
        data = manifest()
        self.assertEqual(apply(data, 1)['changed'], 50)
        self.assertEqual(self.route.call_count, 100)
        with session() as db:
            row = db.scalar(select(Comercio).where(Comercio.public_id == identifier('business', 1)))
            row.nombre_fantasia = 'Edición manual del ejemplo'
            db.commit()
        self.assertEqual(apply(data, 1), dict(batch=BATCH, changed=0, skipped=50, operation='load'))
        self.assertEqual(self.route.call_count, 100)
        with session() as db:
            self.assertEqual(len(db.scalars(select(Comercio)).all()), 38)
            self.assertEqual(len(db.scalars(select(PuntoInteres)).all()), 20)
            self.assertEqual(db.scalar(select(Comercio).where(Comercio.public_id == identifier('business', 1))).nombre_fantasia, 'Edición manual del ejemplo')
            self.assertEqual(db.scalar(select(Comercio).where(Comercio.public_id == 'bosque-sereno')).nombre_fantasia, 'Camping editado que se conserva')
            self.assertEqual(len(db.scalars(select(Auditoria)).all()), 1)
        batch = [p for p in public_places() if p['id'].startswith('demo-' + BATCH)]
        self.assertEqual(len(batch), 50)
        self.assertTrue(all(p['demo'] and p['located'] for p in batch))
        self.assertEqual(apply(data, 1, suspend=True)['changed'], 50)
        self.assertFalse(any(p['id'].startswith('demo-' + BATCH) for p in public_places()))
        self.assertEqual(apply(data, 1, suspend=True)['changed'], 0)

    def test_failure_rolls_back_the_whole_batch(self):
        self.route.side_effect = [None] * 6 + [ValueError('Ruta no comprobada')]
        with self.assertRaises(ValueError):
            apply(manifest(), 1)
        with session() as db:
            self.assertEqual(len(db.scalars(select(Comercio)).all()), 8)
            self.assertEqual(len(db.scalars(select(PuntoInteres)).all()), 0)
            self.assertEqual(len(db.scalars(select(Auditoria)).all()), 0)

    def test_invalid_manifest_and_non_demo_collision_are_rejected(self):
        valid = manifest()
        for mutation in ['missing', 'foreign', 'real', 'duplicate_point']:
            data = copy.deepcopy(valid)
            if mutation == 'missing': data['entries'].pop()
            if mutation == 'foreign': data['entries'][0]['id'] = 'bosque-sereno'
            if mutation == 'real': data['entries'][0]['data']['demo'] = False
            if mutation == 'duplicate_point': data['entries'][1]['data']['latitude'] = data['entries'][0]['data']['latitude']
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(data)
        with self.assertRaises(ValueError):
            apply(valid, 999)
        apply(valid, 1)
        with session() as db:
            db.get(PuntoInteres, identifier('interest', 1)).demo = False
            db.commit()
        with self.assertRaises(ValueError):
            apply(valid, 1, suspend=True)
        self.assertEqual(len([p for p in public_places() if p['id'].startswith('demo-' + BATCH)]), 50)

    def test_upgrade_preserves_existing_real_interests(self):
        with engine().begin() as connection:
            connection.execute(text("INSERT INTO punto_interes (id,name,category,commune,sector,description,latitude,longitude,access,hours,source,access_verified,status,demo) VALUES ('existing','Lugar anterior','Mirador','Santa Bárbara','Santa Bárbara','Descripción anterior',-37.7,-71.8,'Acceso anterior','','Fuente anterior',1,'Aprobado',0)"))
            connection.execute(text('ALTER TABLE punto_interes DROP COLUMN demo'))
            connection.execute(text("UPDATE alembic_version SET version_num='0003_territory'"))
        _initialized.discard(str(db_path()))
        initialize()
        with session() as db:
            self.assertFalse(db.get(PuntoInteres, 'existing').demo)
            self.assertEqual(len(db.scalars(select(Comercio)).all()), 8)
