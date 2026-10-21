"""Operaciones locales: python -m backend.cli --help."""
from contextlib import closing
import argparse
import getpass
import sqlite3
from pathlib import Path

from sqlalchemy import delete, select

from .db import db_path, initialize, session
from .models import Metrica, Sesion, Usuario, now
from .security import create_user, hasher
from datetime import timedelta


def main():
    parser = argparse.ArgumentParser(description="Administración local de Quíbar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Aplicar migraciones y cargar catálogo inicial")
    sub.add_parser("setup-admin", help="Crear el primer administrador si no existe")
    admin = sub.add_parser("create-admin", help="Crear administrador sin credenciales por defecto")
    admin.add_argument("email")
    admin.add_argument("--name", required=True)
    reset = sub.add_parser("reset-password", help="Restablecer una contraseña y revocar sesiones")
    reset.add_argument("email")
    backup = sub.add_parser("backup", help="Respaldo SQLite consistente, incluyendo WAL")
    backup.add_argument("destination", type=Path)
    maps = sub.add_parser("import-map", help="Instalar un mapa MBTiles raster verificado")
    maps.add_argument("source", type=Path)
    maps.add_argument("--replace", action="store_true")
    roads = sub.add_parser("import-roads", help="Preparar datos viales OSM PBF para Valhalla")
    roads.add_argument("source", type=Path)
    roads.add_argument("--replace", action="store_true")
    sub.add_parser("prune", help="Eliminar métricas de más de 90 días y sesiones vencidas")
    args = parser.parse_args()
    if args.command not in ("backup", "import-roads"):
        initialize()
    if args.command == "setup-admin":
        with session() as db:
            if db.scalar(select(Usuario).where(Usuario.rol == "Administrador", Usuario.activo.is_(True))):
                print("Ya existe un administrador activo. Abre /admin para iniciar sesión.")
                return
        args.email = input("Correo del primer administrador: ").strip()
        args.name = input("Nombre completo: ").strip()
        if not args.email or "@" not in args.email or not args.name:
            parser.error("Indica un correo y nombre válidos")
        args.command = "create-admin"
    if args.command in ("create-admin", "reset-password"):
        password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
        if password != getpass.getpass("Repite la contraseña: "):
            parser.error("Las contraseñas no coinciden")
        try:
            if args.command == "create-admin":
                create_user(args.email, args.name, password)
            else:
                if len(password) < 12:
                    raise ValueError("La contraseña debe tener al menos 12 caracteres")
                with session() as db:
                    user = db.scalar(select(Usuario).where(Usuario.correo_institucional == args.email.strip().lower()))
                    if not user:
                        raise ValueError("Usuario no encontrado")
                    user.password_hash = hasher.hash(password)
                    db.execute(delete(Sesion).where(Sesion.id_usuario == user.id))
                    db.commit()
        except ValueError as error:
            parser.error(str(error))
    elif args.command == "backup":
        if not db_path().is_file():
            parser.error("No existe la base que se quiere respaldar")
        if args.destination.exists() or args.destination.resolve() == db_path():
            parser.error("El destino debe ser un archivo nuevo")
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(args.destination)) as target, target:
                source.backup(target)
        args.destination.chmod(0o600)
    elif args.command == "import-map":
        from .maps import install_map
        try:
            print(install_map(args.source, args.replace))
        except ValueError as error:
            parser.error(str(error))
    elif args.command == "import-roads":
        from .roads import install_roads
        try:
            print(install_roads(args.source, args.replace))
        except ValueError as error:
            parser.error(str(error))
    elif args.command == "prune":
        import time
        with session() as db:
            db.execute(delete(Metrica).where(Metrica.fecha_hora < now() - timedelta(days=90)))
            db.execute(delete(Sesion).where(Sesion.vence < time.time()))
            db.commit()
    print("Operación completada")


if __name__ == "__main__":
    main()
