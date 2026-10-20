"""SQLite WAL, migraciones Alembic y serialización pública del catálogo."""
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock

from dotenv import load_dotenv
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from .models import Comercio, Comuna, Rubro

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
_lock = RLock()
_initialized: set[str] = set()


def db_path() -> Path:
    return Path(os.environ.get("QUIBAR_DB_PATH", str(ROOT / "backend/quibar.sqlite3"))).resolve()


@lru_cache(maxsize=32)
def _engine(path: str):
    result = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 15}, poolclass=NullPool)

    @event.listens_for(result, "connect")
    def pragmas(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=15000")
    return result


def engine():
    return _engine(str(db_path()))


def initialize() -> None:
    path = db_path()
    with _lock:
        if str(path) in _initialized and path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        config = Config(str(ROOT / "alembic.ini"))
        # The migration imports legacy rows transactionally and keeps the old table intact.
        with engine().begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        _initialized.add(str(path))


def session():
    initialize()
    return Session(engine())


def serialize(row: Comercio, private=False) -> dict:
    result = {
        "id": row.public_id, "name": row.nombre_fantasia, "category": row.rubro.nombre,
        "commune": row.comuna.nombre, "area": row.direccion_texto, "summary": row.resumen,
        "description": row.descripcion, "offerings": row.ofertas, "hours": row.horario_atencion,
        "keywords": row.keywords, "visual": row.visual, "status": row.estado_moderacion,
        "demo": row.demo, "latitude": row.latitud, "longitude": row.longitud,
        "whatsapp": row.telefono_whatsapp, "featured": row.destacado,
        "photos": [{"id": f.id, "url": f"/media/{f.ruta_archivo}", "alt": f.texto_alt,
                    "cover": f.es_portada, "order": f.orden} for f in row.fotos],
    }
    if private:
        result.update(legal_name=row.razon_social, tax_id=row.rut_contribuyente,
                      updated_at=row.fecha_actualizacion.isoformat())
    return result


def approved() -> list[dict]:
    with session() as db:
        return [serialize(row) for row in db.scalars(select(Comercio).join(Rubro).where(
            Comercio.estado_moderacion == "Aprobado", Rubro.activo.is_(True)
        ).order_by(Comercio.destacado.desc(), Comercio.nombre_fantasia)).unique()]


def lookups(db):
    return {"communes": [r.nombre for r in db.scalars(select(Comuna).order_by(Comuna.nombre))],
            "categories": [r.nombre for r in db.scalars(select(Rubro).where(Rubro.activo.is_(True)).order_by(Rubro.nombre))]}
