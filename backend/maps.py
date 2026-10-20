"""Instalación atómica de paquetes cartográficos raster MBTiles."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile

from .db import db_path
from .public import tile_path


def inspect_map(path: Path):
    if not path.is_file():
        raise ValueError("No se encontró el archivo MBTiles")
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
            if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("El paquete tiene errores de integridad")
            metadata = dict(source.execute("SELECT name,value FROM metadata"))
            if metadata.get("format") not in ("png", "jpg", "jpeg", "webp"):
                raise ValueError("Se requiere un paquete raster PNG, JPEG o WebP")
            count, minimum, maximum = source.execute("SELECT count(*),min(zoom_level),max(zoom_level) FROM tiles").fetchone()
            if not count or minimum < 0 or maximum > 19:
                raise ValueError("El paquete no tiene teselas válidas entre zoom 0 y 19")
            return {"tiles": count, "min_zoom": minimum, "max_zoom": maximum, "format": metadata["format"],
                    "attribution": metadata.get("attribution", "© OpenStreetMap contributors · ODbL")}
    except sqlite3.Error as error:
        raise ValueError("El archivo no tiene la estructura MBTiles esperada") from error


def install_map(source: Path, replace=False):
    info = inspect_map(source)
    target = tile_path()
    if target == db_path() or source.resolve() == target:
        raise ValueError("El paquete debe ser distinto del destino y de la base del catálogo")
    if target.exists() and not replace:
        raise ValueError("Ya existe un mapa. Usa --replace para sustituirlo")
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".map-", suffix=".mbtiles", dir=target.parent)
    os.close(handle)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as source_db:
            with closing(sqlite3.connect(temporary)) as dest:
                source_db.backup(dest)
        inspect_map(Path(temporary))
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return info
