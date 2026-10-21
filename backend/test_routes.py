"""Rutas, desvíos y voz: grafo simulado, nunca datos reales de visitantes."""
import copy
import unittest
import os
from unittest.mock import patch
import httpx
from . import test_territory as fixtures
from . import routes


class RouteAcceptance(unittest.TestCase):
    login = fixtures.TerritoryAcceptance.login
    tearDown = fixtures.TerritoryAcceptance.tearDown
    def setUp(self):
        fixtures.TerritoryAcceptance.setUp(self)
        self.client.put('/api/quibar/admin/station', json=dict(name='Origen sintético', latitude=-37.67, longitude=-72.02,
                         source='Fixture de prueba', verified=True), headers=self.headers).raise_for_status()
        self.dest = self.client.post('/api/quibar/admin/interests', json={**self.place, 'name':'Destino sintético'}, headers=self.headers).json()
        self.near = self.client.post('/api/quibar/admin/interests', json={**self.place, 'name':'Parada sintética', 'category':'Cultura',
                         'latitude':-37.775, 'longitude':-71.82}, headers=self.headers).json()
        self.data = {'destination':'interest:'+self.dest['id'], 'profile':'walking', 'stops':[]}
        routes._cache.clear()

    def engine(self, points, profile):
        coords = [[p['longitude'], p['latitude']] for p in points]
        return {'geometry':{'type':'LineString','coordinates':coords},'duration_s':1000+max(0,len(points)-2)*120,
                'distance_m':3000,'boundaries':list(range(1,len(points))), 'maneuvers':[{'instruction':'Sigue el camino de prueba','distance_m':3000,'duration_s':1000}]}

    def test_migration_preserves_catalog_without_inventing_coordinates(self):
        # The parent test covers an unconfigured station; this fixture configures one.
        self.assertTrue(self.client.get('/api/quibar/places').json()['station']['configured'])

    def test_base_route_never_adds_suggested_stops(self):
        with patch('backend.routes.road_route', side_effect=self.engine):
            result=self.client.post('/api/quibar/routes', json=self.data)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['stops'],[])
            options=self.client.post('/api/quibar/routes/suggestions',json=self.data).json()['suggestions']
            self.assertEqual(len(options),1)
            self.assertEqual(options[0]['extra_duration_s'],120)
            result=self.client.post('/api/quibar/routes',json={**self.data,'stops':options[0]['stop_order']})
            self.assertEqual(result.json()['stops'][0]['id'],self.near['id'])
            self.assertEqual(len(result.json()['geometry']['coordinates']),3)

    def test_graph_detour_and_mode_limits_are_enforced(self):
        def costly(points,profile):
            result=self.engine(points,profile)
            if len(points)>2: result['duration_s']+=400
            return result
        with patch('backend.routes.road_route',side_effect=costly):
            self.assertEqual(self.client.post('/api/quibar/routes/suggestions',json=self.data).json()['suggestions'],[])
            options=self.client.post('/api/quibar/routes/suggestions',json={**self.data,'profile':'driving'}).json()['suggestions']
            self.assertEqual(len(options),1)

    def test_revocation_invalidates_route_and_speech(self):
        with patch('backend.routes.road_route',side_effect=self.engine):
            trip=self.client.post('/api/quibar/routes',json=self.data).json()
        self.client.put('/api/quibar/admin/interests/'+self.dest['id'],json={**self.dest,'status':'Suspendido'},headers=self.headers)
        self.assertEqual(self.client.post('/api/quibar/routes',json=self.data).status_code,404)
        self.assertEqual(self.client.post('/api/quibar/routes/speech',json={'narration_id':trip['narration_id']}).status_code,410)

    def test_no_route_and_unavailable_voice_have_explicit_errors(self):
        from fastapi import HTTPException
        with patch('backend.routes.road_route',side_effect=HTTPException(422,'No hay camino')):
            self.assertEqual(self.client.post('/api/quibar/routes',json=self.data).status_code,422)
        with patch('backend.routes.road_route',side_effect=self.engine):
            trip=self.client.post('/api/quibar/routes',json=self.data).json()
        with patch('backend.routes.httpx.Client') as transport:
            transport.return_value.__enter__.return_value.post.side_effect=httpx.ConnectError('Voz ausente')
            self.assertEqual(self.client.post('/api/quibar/routes/speech',json={'narration_id':trip['narration_id']}).status_code,503)
        self.assertEqual(self.client.post('/api/quibar/routes',json={**self.data,'stops':[self.data['destination']]}).status_code,422)

    def test_fallback_narration_and_origin_required(self):
        with patch('backend.routes.road_route',side_effect=self.engine),patch('backend.routes.httpx.Client') as transport:
            transport.return_value.__enter__.return_value.post.side_effect=httpx.ConnectError('Datacenter ausente')
            result=self.client.post('/api/quibar/routes/narration',json={**self.data,'suggestions':['interest:'+self.near['id']]})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['mode'],'basico')
            self.assertIn(self.near['name'],result.json()['text'])
        self.client.put('/api/quibar/admin/station',json=dict(name='Tótem',latitude=-37.67,longitude=-72.02,source='Fixture prueba',verified=False),headers=self.headers)
        self.assertEqual(self.client.post('/api/quibar/routes',json=self.data).status_code,409)

    def test_valhalla_transport_decodes_roads_and_profiles(self):
        # Encoded polyline6 for two points, generated here rather than a fabricated engine response in production.
        def encode(points):
            out=''; previous=[0,0]
            for point in points:
                for i,number in enumerate(point):
                    value=round(number*1e6)-previous[i];previous[i]=round(number*1e6)
                    value=~(value<<1) if value<0 else value<<1
                    while value>=32:out+=chr((32|(value&31))+63);value>>=5
                    out+=chr(value+63)
            return out
        shape=encode([[-37.67,-72.02],[-37.88,-71.62]])
        payload={'trip':{'status':0,'summary':{'time':1234,'length':5.5},'legs':[{'shape':shape,'maneuvers':[{'instruction':'Sigue el camino','length':5.5,'time':1234}]}]}}
        response=httpx.Response(200,json=payload,request=httpx.Request('POST','http://routing/route'))
        with patch('backend.routes.httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value=response
            result=routes.road_route([dict(latitude=-37.67,longitude=-72.02),dict(latitude=-37.88,longitude=-71.62)],'walking')
            self.assertEqual(result['distance_m'],5500)
            self.assertEqual(result['geometry']['coordinates'][1],[-71.62,-37.88])
            self.assertEqual(client.return_value.__enter__.return_value.post.call_args.kwargs['json']['costing'],'pedestrian')

    def test_editing_place_invalidates_previous_audio(self):
        with patch('backend.routes.road_route',side_effect=self.engine):
            trip=self.client.post('/api/quibar/routes',json=self.data).json()
        self.client.put('/api/quibar/admin/interests/'+self.dest['id'],json={**self.dest,'name':'Nombre sintético actualizado'},headers=self.headers).raise_for_status()
        self.assertEqual(self.client.post('/api/quibar/routes/speech',json={'narration_id':trip['narration_id']}).status_code,410)
