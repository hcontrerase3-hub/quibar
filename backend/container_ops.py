"""Container lifecycle and offline data transfer; no host Python is required."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time

import httpx

from .db import db_path, initialize

STATE = Path('/state')
SOCKET = '/run/quibar/app.sock'


def snapshot(source, target):
    with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('La base no supera la comprobación de integridad')
    target.chmod(0o600)


def backup(destination=None):
    """Caller stops writers first; stdout is exclusively the archive stream."""
    if not db_path().is_file():
        raise ValueError('No existe una base para respaldar')
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / 'quibar.sqlite3'
        snapshot(db_path(), target)
        import sys
        output = open(destination, 'xb') if destination else sys.stdout.buffer
        if destination:
            Path(destination).chmod(0o600)
        with tarfile.open(fileobj=output, mode='w|gz') as archive:
            archive.add(target, arcname='quibar.sqlite3')
            for name in ('media', 'map.mbtiles', 'routing'):
                if (STATE / name).exists():
                    archive.add(STATE / name, arcname=name)
        if destination:
            output.close()


def import_data(source):
    """Import an explicit stopped native data directory, never overwrite a volume."""
    if any(STATE.iterdir()):
        # Empty media directory is created in the image for named-volume ownership.
        entries = [p for p in STATE.iterdir() if not (p.name == 'media' and p.is_dir() and not any(p.iterdir()))]
        if entries:
            raise ValueError('El volumen ya contiene datos; no se sobrescribirá')
    source = Path(source).resolve()
    database = source / 'quibar.sqlite3'
    if not database.is_file():
        raise ValueError('La carpeta debe contener quibar.sqlite3 y, opcionalmente, media/ y map.mbtiles')
    # Build everything in staging first. A failed import leaves no partial live DB.
    with tempfile.TemporaryDirectory(dir=STATE, prefix='.import-') as directory:
        staging = Path(directory)
        snapshot(database, staging / 'quibar.sqlite3')
        media = source / 'media'
        if media.exists():
            if any(p.is_symlink() for p in media.rglob('*')) or media.is_symlink():
                raise ValueError('No se admiten enlaces simbólicos en los medios')
            shutil.copytree(media, staging / 'media')
        if (source / 'map.mbtiles').exists():
            shutil.copyfile(source / 'map.mbtiles', staging / 'map.mbtiles')
        if (source / 'routing').is_dir():
            if any(p.is_symlink() for p in (source / 'routing').rglob('*')):
                raise ValueError('No se admiten enlaces en datos viales')
            shutil.copytree(source / 'routing', staging / 'routing')
        # The original snapshot remains available even if a later migration fails.
        shutil.copyfile(staging / 'quibar.sqlite3', staging / 'pre-migration.sqlite3')
        with tarfile.open(staging / 'pre-migration.tar.gz', 'w:gz') as archive:
            for name in ('quibar.sqlite3', 'media', 'map.mbtiles', 'routing'):
                if (staging / name).exists():
                    archive.add(staging / name, arcname=name)
        (staging / 'pre-migration.tar.gz').chmod(0o600)
        if os.geteuid() == 0:
            for item in [staging, *staging.rglob('*')]:
                os.chown(item, 10001, 10001)
        for item in staging.iterdir():
            target = STATE / item.name
            if target.is_dir() and not any(target.iterdir()):
                target.rmdir()
            item.rename(target)
    if os.geteuid() == 0:
        # Migrations and any WAL/SHM files must use the application's identity.
        os.setgroups([10001])
        os.setgid(10001)
        os.setuid(10001)
    initialize()
    print('Datos importados; respaldo previo a migrar: /state/pre-migration.tar.gz')


def model():
    url = os.environ.get('OLLAMA_URL', 'http://ollama:11434')
    name = os.environ.get('QUIBAR_MODEL', 'qwen3:14b-q4_K_M')
    with httpx.Client(trust_env=False) as client:
        for attempt in range(30):
            try:
                client.get(f'{url}/api/tags', timeout=2).raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 29:
                    raise RuntimeError('Ollama no responde; Quíbar sigue en modo básico')
                time.sleep(2)
        if os.environ.get('QUIBAR_OLLAMA_MODE') != 'remote' and os.environ.get('QUIBAR_MODEL_PULL', '1') == '1':
            print(f'Descargando/verificando {name}. La aplicación sigue disponible.', flush=True)
            with client.stream('POST', f'{url}/api/pull', json={'name': name, 'stream': True}, timeout=1800) as response:
                response.raise_for_status()
                import json
                last_status = None
                for line in response.iter_lines():
                    message = json.loads(line)
                    if message.get('error'):
                        raise RuntimeError(message['error'])
                    if message.get('status') != last_status:
                        last_status = message.get('status')
                        print(last_status, flush=True)
        else:
            print(f'Usando modelo existente en servidor remoto: {name}; no se descargarán modelos.', flush=True)
    from .preload import main
    raise SystemExit(main())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['serve', 'develop', 'health', 'maintenance', 'model', 'backup', 'import'])
    parser.add_argument('source', nargs='?')
    args = parser.parse_args()
    if args.action in ('serve', 'develop'):
        initialize()
        # Uvicorn's reload supervisor does not remove a stale Unix socket.
        import socket
        with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as probe:
            try:
                probe.connect(SOCKET)
            except (FileNotFoundError, ConnectionRefusedError):
                Path(SOCKET).unlink(missing_ok=True)
            else:
                raise RuntimeError('Ya existe una API escuchando en este volumen de socket')
        import uvicorn
        # No TCP listener: only nginx, with access to this volume, supplies headers.
        uvicorn.run('backend.app:app', uds=SOCKET, proxy_headers=True, forwarded_allow_ips='*',
                    reload=args.action == 'develop', reload_dirs=['/app/backend'] if args.action == 'develop' else None)
    elif args.action == 'health':
        with httpx.Client(transport=httpx.HTTPTransport(uds=SOCKET)) as client:
            client.get('http://localhost/api/quibar/health', timeout=2).raise_for_status()
    elif args.action == 'maintenance':
        while True:
            subprocess.run(['python', '-m', 'backend.cli', 'prune'], check=True)
            time.sleep(86400)
    elif args.action == 'model':
        model()
    elif args.action == 'backup':
        backup(args.source)
    elif args.action == 'import':
        if not args.source:
            parser.error('Falta el directorio de origen')
        import_data(args.source)


if __name__ == '__main__':
    main()
