"""Circuito geográfico, aprobación y ubicación del tótem con datos sintéticos."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from .app import app
from .db import initialize, session
from .models import Comercio
from .security import create_user, _attempts


class TerritoryAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'QUIBAR_DB_PATH': f'{self.tmp.name}/test.sqlite3', 'QUIBAR_ADMIN_NETWORKS': '127.0.0.0/8'})
        self.env.start(); initialize(); _attempts.clear()
        create_user('admin@test.local', 'Admin', 'temporary-long-password')
        create_user('operator@test.local', 'Operator', 'temporary-long-password', 'Operador Territorial')
        self.client = TestClient(app, client=('127.0.0.1', 1))
        self.login()
        self.place = dict(name='Punto sintético de prueba', category='Mirador', commune='Alto Biobío', sector='Ralco',
                          description='Datos sintéticos exclusivos para pruebas', latitude=-37.88, longitude=-71.62,
                          access='Acceso sintético verificado en test', source='Fixture sintético', access_verified=True, status='Aprobado')

    def login(self, email='admin@test.local'):
        response = self.client.post('/api/quibar/admin/session', json={'email': email, 'password': 'temporary-long-password'})
        self.headers = {'x-csrf-token': response.json()['csrf']}

    def tearDown(self):
        self.client.close(); self.env.stop(); self.tmp.cleanup()

    def test_migration_preserves_catalog_without_inventing_coordinates(self):
        result = self.client.get('/api/quibar/places').json()
        self.assertFalse(any(p['located'] for p in result['places']))
        self.assertFalse(result['station']['configured'])
        self.assertEqual(len(self.client.get('/api/quibar/catalog').json()), 8)
        self.assertIn('Alto Biobío', self.client.get('/api/quibar/admin/lookups').json()['communes'])

    def test_interest_approval_suspension_and_csrf(self):
        self.assertEqual(self.client.post('/api/quibar/admin/interests', json=self.place).status_code, 403)
        result = self.client.post('/api/quibar/admin/interests', json=self.place, headers=self.headers)
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(sum(p['kind']=='interest' for p in self.client.get('/api/quibar/places').json()['places']), 1)
        data = result.json(); data['status'] = 'Suspendido'
        self.client.put('/api/quibar/admin/interests/'+data['id'], json=data, headers=self.headers).raise_for_status()
        self.assertFalse(any(p['kind']=='interest' for p in self.client.get('/api/quibar/places').json()['places']))
        self.login('operator@test.local')
        self.assertEqual(self.client.post('/api/quibar/admin/interests', json=self.place, headers=self.headers).status_code, 403)
        pending = {**self.place, 'status': 'Pendiente'}
        self.assertEqual(self.client.post('/api/quibar/admin/interests', json=pending, headers=self.headers).status_code, 201)

    def test_station_and_business_require_verification(self):
        station = dict(name='Tótem sintético', latitude=-37.67, longitude=-72.02, source='Fixture sintético', verified=True)
        self.client.put('/api/quibar/admin/station', json=station, headers=self.headers).raise_for_status()
        self.assertTrue(self.client.get('/api/quibar/places').json()['station']['configured'])
        self.login('operator@test.local')
        self.assertEqual(self.client.put('/api/quibar/admin/station', json=station, headers=self.headers).status_code, 403)
        with session() as db:
            row = db.scalar(select(Comercio).where(Comercio.comuna.has(nombre='Santa Bárbara')))
            row.sector='Huequecura'; row.latitud=-37.74; row.longitud=-71.89; row.demo=False
            db.commit()
        place = next(p for p in self.client.get('/api/quibar/places').json()['places'] if p['sector']=='Huequecura')
        self.assertFalse(place['located']); self.assertIsNone(place['latitude'])
        with session() as db:
            row = db.scalar(select(Comercio).where(Comercio.sector=='Huequecura'))
            row.location_verified=True; row.location_source='Fixture sintético'; db.commit()
        self.assertTrue(next(p for p in self.client.get('/api/quibar/places').json()['places'] if p['sector']=='Huequecura')['located'])

    def test_unverified_access_and_outside_area_cannot_be_approved(self):
        for changes in [{'access_verified': False}, {'latitude': 20}, {'sector':'Quilaco'}]:
            response = self.client.post('/api/quibar/admin/interests', json={**self.place, **changes}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
