"""HTTP acceptance against an isolated Compose project (never a real catalog)."""
import os

import httpx

from .security import create_user


def main():
    if os.environ.get('QUIBAR_SMOKE') != 'temporary-data-only':
        raise RuntimeError('Esta prueba exige un proyecto con volúmenes temporales')
    with httpx.Client(base_url='http://nginx:8080', trust_env=False, timeout=15) as client:
        assert client.get('/api/quibar/health').status_code == 200
        assert client.get('/admin').status_code == 200
        if os.environ.get('QUIBAR_SMOKE_PHASE') == 'persist':
            assert len(client.get('/api/quibar/catalog').json()) == 7
            print('Persistencia comprobada después de recrear los contenedores')
            return
        assert len(client.get('/api/quibar/catalog').json()) == 8
        assert client.get('/api/quibar/admin/businesses').status_code == 401
        create_user('container@example.test', 'Acceptance', 'temporary-password-for-tests')
        credentials = {'email': 'container@example.test', 'password': 'temporary-password-for-tests'}
        secure = client.post('/api/quibar/admin/session', json=credentials,
                             headers={'x-forwarded-proto': 'https', 'x-forwarded-for': '192.168.5.5',
                                      'origin': 'https://nginx:8080'})
        assert secure.status_code == 200, secure.text
        assert 'Secure' in secure.headers['set-cookie']
        assert 'HttpOnly' in secure.headers['set-cookie']
        login = client.post('/api/quibar/admin/session', json=credentials)
        assert login.status_code == 200, login.text
        csrf = {'x-csrf-token': login.json()['csrf'], 'origin': 'http://nginx:8080'}
        row = client.get('/api/quibar/admin/businesses').json()[0]
        row['status'] = 'Suspendido'
        url = f"/api/quibar/admin/businesses/{row['id']}"
        assert client.put(url, json=row).status_code == 403
        assert client.put(url, json=row, headers={**csrf, 'origin': 'http://evil.test'}).status_code == 403
        response = client.put(url, json=row, headers=csrf)
        assert response.status_code == 200, response.text
        assert len(client.get('/api/quibar/catalog').json()) == 7
        response = client.post('/api/quibar/chat', json={'query': 'Un café en Quilaco'})
        assert response.status_code == 200, response.text
        assert response.json()['mode'] == 'basico'
        assert client.get('/api/quibar/map').json()['available'] is False
        assert client.post('/api/quibar/metrics', json={'event': 'QR_MOSTRADO'}).status_code == 202
        assert client.get('/api/unknown').status_code == 404
    print('HTTP: SPA, sesión, cookie HTTPS, CSRF, moderación, QR y fallback correctos')


if __name__ == '__main__':
    main()
