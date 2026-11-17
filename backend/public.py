"""Recursos públicos: mapas locales, fotos aprobadas y métricas sin datos personales."""
from contextlib import closing
import os
import html
import math
import sqlite3
import time
from pathlib import Path
from typing import Literal

import httpx
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


@router.get("/media/logos/{filename}")
def business_logo(filename: str, request: Request):
    with session() as db:
        row = db.scalar(select(Comercio).where(Comercio.logo_archivo == filename))
        if not row:
            raise HTTPException(404)
        if row.estado_moderacion != "Aprobado" or not row.rubro.activo:
            try:
                identity(request)
            except HTTPException:
                raise HTTPException(404)
        path = media_dir() / row.logo_archivo
        if not path.is_file():
            raise HTTPException(404)
        # Revalidate moderation on every request; suspended logos must not remain cached.
        return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "no-store"})


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


_WEATHER_TTL_SECONDS = 600
_WEATHER_DEFAULT_LAT = -37.7106
_WEATHER_DEFAULT_LON = -71.8155
_WEATHER_DEFAULT_LABEL = "Los Nogales, Santa Bárbara"
_weather_cache: dict[tuple[float, float], tuple[float, dict[str, object]]] = {}

_WMO_CONDITIONS = {
    0: "Despejado",
    1: "Parcialmente nublado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla",
    51: "Llovizna",
    53: "Llovizna",
    55: "Llovizna",
    56: "Llovizna",
    57: "Llovizna",
    61: "Lluvia",
    63: "Lluvia",
    65: "Lluvia",
    66: "Lluvia",
    67: "Lluvia",
    71: "Nieve",
    73: "Nieve",
    75: "Nieve",
    77: "Nieve",
    80: "Lluvia",
    81: "Lluvia",
    82: "Lluvia",
    85: "Nieve",
    86: "Nieve",
    95: "Tormenta",
    96: "Tormenta",
    99: "Tormenta",
}


def weather_coordinates() -> tuple[float, float, str]:
    """Devuelve latitud, longitud y etiqueta para consultar el clima en Open-Meteo."""
    from .territory import station

    label = os.environ.get("QUIBAR_WEATHER_LABEL", _WEATHER_DEFAULT_LABEL).strip() or _WEATHER_DEFAULT_LABEL
    env_lat = os.environ.get("QUIBAR_WEATHER_LATITUDE")
    env_lon = os.environ.get("QUIBAR_WEATHER_LONGITUDE")
    if env_lat and env_lon:
        try:
            return float(env_lat), float(env_lon), label
        except ValueError:
            pass
    totem = station()
    if totem["configured"] and totem["latitude"] is not None and totem["longitude"] is not None:
        return round(float(totem["latitude"]), 4), round(float(totem["longitude"]), 4), label
    return _WEATHER_DEFAULT_LAT, _WEATHER_DEFAULT_LON, label


@router.get("/api/quibar/weather")
async def current_weather():
    """Consulta el clima actual en Open-Meteo para el Centro de Visitantes con caché breve."""
    latitude, longitude, label = weather_coordinates()
    cache_key = (latitude, longitude)
    now = time.monotonic()
    cached = _weather_cache.get(cache_key)
    if cached and now - cached[0] < _WEATHER_TTL_SECONDS:
        return cached[1]
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code",
        "timezone": "America/Santiago",
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        current = payload.get("current") if isinstance(payload, dict) else None
        if not isinstance(current, dict) or current.get("temperature_2m") is None:
            return {"available": False}
        code = current.get("weather_code")
        condition = _WMO_CONDITIONS.get(int(code), "Clima actual") if code is not None else "Clima actual"
        humidity = current.get("relative_humidity_2m")
        result: dict[str, object] = {
            "available": True,
            "city": label,
            "temperature": str(current["temperature_2m"]),
            "condition": condition,
            "humidity": str(round(float(humidity))) if humidity is not None else "",
            "updated_at": str(current.get("time") or ""),
        }
        _weather_cache[cache_key] = (now, result)
        return result
    except (httpx.HTTPError, ValueError, TypeError):
        return {"available": False}
