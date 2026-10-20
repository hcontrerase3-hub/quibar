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
    admin = sub.add_parser("create-admin", help="Crear administrador sin credenciales por defecto")
    admin.add_argument("email")
    admin.add_argument("--name", required=True)
    reset = sub.add_parser("reset-password", help="Restablecer una contraseña y revocar sesiones")
    reset.add_argument("email")
    backup = sub.add_parser("backup", help="Respaldo SQLite consistente, incluyendo WAL")
    backup.add_argument("destination", type=Path)
    sub.add_parser("prune", help="Eliminar métricas de más de 90 días y sesiones vencidas")
    args = parser.parse_args()
    initialize()
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
        if args.destination.exists() or args.destination.resolve() == db_path():
            parser.error("El destino debe ser un archivo nuevo")
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(f"file:{db_path()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(args.destination)) as target, target:
                source.backup(target)
        args.destination.chmod(0o600)
    elif args.command == "prune":
        import time
        with session() as db:
            db.execute(delete(Metrica).where(Metrica.fecha_hora < now() - timedelta(days=90)))
            db.execute(delete(Sesion).where(Sesion.vence < time.time()))
            db.commit()
    print("Operación completada")


if __name__ == "__main__":
    main()
