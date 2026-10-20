"""Recursos públicos: mapas locales, fotos aprobadas y métricas sin datos personales."""
from contextlib import closing
import os
import html
import math
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from .admin import media_dir
from .db import ROOT, session
from .models import Comercio, Fotografia, Metrica
from .security import identity

router = APIRouter()


def tile_path():
    return Path(os.environ.get("QUIBAR_TILES_PATH", str(ROOT / "data/map.mbtiles"))).resolve()


@router.get("/api/quibar/map")
def map_info():
    path = tile_path()
    if not path.is_file():
        return {"available": False}
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
            metadata = dict(db.execute("SELECT name,value FROM metadata"))
        fmt = metadata.get("format", "png")
        if fmt not in ("png", "jpg", "jpeg", "webp"):
            raise ValueError("Solo teselas raster")
        bounds = [float(v) for v in metadata.get("bounds", "-72.5,-38.2,-71.2,-37.3").split(",")]
        if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
            raise ValueError("Límites inválidos")
        minimum, maximum = int(metadata.get("minzoom", 0)), int(metadata.get("maxzoom", 16))
        if not 0 <= minimum <= maximum <= 19:
            raise ValueError("Niveles de zoom inválidos")
        return {"available": True, "minZoom": minimum,
                "maxZoom": maximum, "bounds": bounds,
                "attribution": html.escape(metadata.get("attribution", "© OpenStreetMap contributors · ODbL")[:500])}
    except (sqlite3.Error, ValueError):
        raise HTTPException(503, "El paquete de mapas no es un MBTiles raster válido")


@router.get("/tiles/{z}/{x}/{y}")
def tile(z: int, x: int, y: int):
    path = tile_path()
    if not 0 <= z <= 19 or not (0 <= x < 2 ** z and 0 <= y < 2 ** z) or not path.is_file():
        raise HTTPException(404)
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
            data = db.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                              (z, x, (2 ** z - 1) - y)).fetchone()
            fmt = dict(db.execute("SELECT name,value FROM metadata")).get("format", "png")
    except sqlite3.Error:
        raise HTTPException(503, "Mapa no disponible")
    if not data:
        raise HTTPException(404)
    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(fmt)
    if not media:
        raise HTTPException(404)
    return Response(bytes(data[0]), media_type=media, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/media/{filename}")
def photograph(filename: str, request: Request):
    with session() as db:
        photo = db.scalar(select(Fotografia).where(Fotografia.ruta_archivo == filename))
        row = db.get(Comercio, photo.id_comercio) if photo else None
        if not row:
            raise HTTPException(404)
        if row.estado_moderacion != "Aprobado" or not row.rubro.activo:
            try:
                identity(request)
            except HTTPException:
                raise HTTPException(404)
        path = media_dir() / photo.ruta_archivo
        if not path.is_file():
            raise HTTPException(404)
        # Revalidate moderation on every request; suspended photos must not remain cached.
        return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "no-store"})


class EventData(BaseModel):
    event: Literal["FILTRO", "CLICK_FICHA", "QR_MOSTRADO"]
    business_id: str | None = Field(default=None, max_length=80)


@router.post("/api/quibar/metrics", status_code=202)
def record_metric(data: EventData):
    with session() as db:
        row = db.scalar(select(Comercio).where(Comercio.public_id == data.business_id,
                        Comercio.estado_moderacion == "Aprobado")) if data.business_id else None
        if data.business_id and not row:
            raise HTTPException(404, "Ficha no disponible")
        db.add(Metrica(id_comercio=row.id if row else None, tipo_evento=data.event))
        db.commit()
    return {"ok": True}
