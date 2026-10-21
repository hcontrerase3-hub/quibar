"""Real Valhalla/Piper acceptance with a disposable synthetic grid and database."""
import os
import time
import httpx
from .db import session
from .models import PuntoInteres, Totem


def main():
    if os.environ.get('QUIBAR_SMOKE') != 'temporary-data-only':
        raise RuntimeError('Solo ejecutar contra datos temporales del proyecto de aceptación')
    with session() as db:
        origin=db.get(Totem,1);origin.name='Tótem sintético de aceptación';origin.latitude=-37.6701;origin.longitude=-72.0199;origin.source='Grafo sintético de prueba';origin.verified=True
        for identifier,latitude,longitude in [('destination',-37.6719,-72.0181),('stop',-37.671,-72.019)]:
            db.add(PuntoInteres(id='test-'+identifier,name='Lugar sintético '+identifier,category='Mirador',commune='Santa Bárbara',sector='Santa Bárbara',description='Lugar sintético exclusivamente para aceptación Docker',latitude=latitude,longitude=longitude,access='Camino sintético de prueba',source='Fixture de aceptación',access_verified=True,status='Aprobado'))
        db.commit()
    with httpx.Client(trust_env=False,timeout=25) as client:
        request={'destination':'interest:test-destination','profile':'walking','stops':[]}
        deadline=time.monotonic()+120
        while True:
            response=client.post('http://nginx:8080/api/quibar/routes',json=request)
            if response.status_code==200:break
            if time.monotonic()>deadline:raise RuntimeError(response.text)
            time.sleep(2)
        walking=response.json()
        assert walking['distance_m']>0 and len(walking['geometry']['coordinates'])>1 and walking['maneuvers']
        driving=client.post('http://nginx:8080/api/quibar/routes',json={**request,'profile':'driving'});driving.raise_for_status()
        suggestions=client.post('http://nginx:8080/api/quibar/routes/suggestions',json=request);suggestions.raise_for_status()
        assert suggestions.json()['suggestions'][0]['place']['id']=='test-stop'
        assert walking['stops']==[]
        with_stop=client.post('http://nginx:8080/api/quibar/routes',json={**request,'stops':['interest:test-stop']});with_stop.raise_for_status();assert len(with_stop.json()['stops'])==1
        deadline=time.monotonic()+120
        while not client.get('http://speech:5000/health').json()['ready']:
            if time.monotonic()>deadline:raise RuntimeError('Piper no pudo preparar la voz')
            time.sleep(2)
        wav=client.post('http://nginx:8080/api/quibar/routes/speech',json={'narration_id':walking['narration_id']});wav.raise_for_status();assert wav.content.startswith(b'RIFF')
        print('Valhalla real: a pie',walking['distance_m'],'m; vehículo',driving.json()['distance_m'],'m. Voz WAV:',len(wav.content),'bytes')
    with session() as db:
        db.get(PuntoInteres,'test-destination').status='Suspendido';db.commit()
    with httpx.Client(trust_env=False) as client:
        assert client.post('http://nginx:8080/api/quibar/routes',json=request).status_code==404
        assert client.post('http://nginx:8080/api/quibar/routes/speech',json={'narration_id':walking['narration_id']}).status_code==410
    print('Aprobación y revocación comprobadas a través del proxy real')


if __name__=='__main__':main()
