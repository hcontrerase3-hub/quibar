"""API administrativa local con moderación, multimedia y trazabilidad."""
import io
import os
import re
import secrets
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .db import ROOT, lookups, serialize, session
from .models import Auditoria, Comercio, Comuna, Fotografia, Metrica, Rubro, Sesion, Usuario, now
from .security import (COOKIE, DUMMY_HASH, VerificationError, administrator, check_network,
                       digest, hasher, identity, same_origin, throttle_login)

router = APIRouter(prefix="/api/quibar/admin")
Image.MAX_IMAGE_PIXELS = 20_000_000


def media_dir():
    path = Path(os.environ.get("QUIBAR_MEDIA_DIR", str(ROOT / "backend/media")))
    path.mkdir(parents=True, exist_ok=True)
    return path


def audit(db, user, request, action, row=None, detail=None):
    db.add(Auditoria(id_usuario=user["id"], id_comercio=row.id if row else None,
                     tipo_operacion=action, detalle_json=detail or {}, ip_origen=request.client.host))


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@router.post("/session")
def login(data: Login, request: Request, response: Response):
    check_network(request)
    same_origin(request)
    throttle_login(request)
    with session() as db:
        user = db.scalar(select(Usuario).where(Usuario.correo_institucional == data.email.strip().lower()))
        try:
            hasher.verify(user.password_hash if user else DUMMY_HASH, data.password)
        except VerificationError:
            raise HTTPException(401, "Correo o contraseña incorrectos")
        if not user or not user.activo:
            raise HTTPException(401, "Correo o contraseña incorrectos")
        if hasher.check_needs_rehash(user.password_hash):
            user.password_hash = hasher.hash(data.password)
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        db.execute(delete(Sesion).where(Sesion.vence < time.time()))
        db.add(Sesion(token_hash=digest(token), id_usuario=user.id, csrf=csrf, vence=time.time() + 8 * 3600))
        user.ultimo_acceso = now()
        audit(db, {"id": user.id}, request, "INICIAR_SESION")
        db.commit()
        secure = request.url.scheme == "https"
        response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True, secure=secure, samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return {"id": user.id, "name": user.nombre_completo, "email": user.correo_institucional, "role": user.rol, "csrf": csrf}


@router.get("/session")
def me(user=Depends(identity)):
    return user


@router.delete("/session")
def logout(request: Request, response: Response, user=Depends(identity)):
    with session() as db:
        db.execute(delete(Sesion).where(Sesion.token_hash == digest(request.cookies.get(COOKIE, ""))))
        audit(db, user, request, "CERRAR_SESION")
        db.commit()
    response.delete_cookie(COOKIE)
    return {"ok": True}


class BusinessData(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=50)
    commune: str = Field(min_length=2, max_length=50)
    area: str = Field(min_length=2, max_length=255)
    summary: str = Field(min_length=5, max_length=400)
    description: str = Field(min_length=5, max_length=4000)
    offerings: list[str] = Field(min_length=1, max_length=20)
    hours: str = Field(min_length=2, max_length=255)
    keywords: str = Field(default="", max_length=1000)
    visual: Literal["stay", "food", "craft", "outdoors", "coffee", "shop", "camp", "textile"] = "shop"
    status: Literal["Pendiente", "Aprobado", "Suspendido"] = "Pendiente"
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    whatsapp: str = Field(default="", max_length=20, pattern=r"^(\+[1-9]\d{7,14})?$")
    legal_name: str = Field(default="", max_length=150)
    tax_id: str = Field(default="", max_length=12)
    featured: bool = False
    demo: bool = True

    @model_validator(mode="after")
    def complete(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Completa ambas coordenadas")
        if any(not value.strip() or len(value) > 150 for value in self.offerings):
            raise ValueError("Los servicios deben contener entre 1 y 150 caracteres")
        if not self.demo and self.status == "Aprobado" and (self.latitude is None or not self.whatsapp):
            raise ValueError("Para aprobar una ficha real se requieren coordenadas y contacto verificados")
        return self


def find_business(db, public_id):
    row = db.scalar(select(Comercio).where(Comercio.public_id == public_id))
    if not row:
        raise HTTPException(404, "Ficha no encontrada")
    return row


def apply_data(db, row, data, user):
    if data.status == "Aprobado" and user["role"] != "Administrador":
        raise HTTPException(403, "Solo un administrador puede aprobar fichas")
    commune = db.scalar(select(Comuna).where(Comuna.nombre == data.commune))
    category = db.scalar(select(Rubro).where(Rubro.nombre == data.category, Rubro.activo.is_(True)))
    if not commune or not category:
        raise HTTPException(422, "Comuna o rubro no válido")
    row.id_comuna, row.id_rubro = commune.id, category.id
    row.comuna, row.rubro = commune, category
    mapping = {"name": "nombre_fantasia", "area": "direccion_texto", "summary": "resumen",
               "description": "descripcion", "offerings": "ofertas", "hours": "horario_atencion",
               "status": "estado_moderacion", "latitude": "latitud", "longitude": "longitud",
               "whatsapp": "telefono_whatsapp", "legal_name": "razon_social", "tax_id": "rut_contribuyente",
               "featured": "destacado"}
    for key, value in data.model_dump().items():
        if key not in ("category", "commune"):
            setattr(row, mapping.get(key, key), value.strip() if isinstance(value, str) else value)


@router.get("/lookups")
def get_lookups(user=Depends(identity)):
    with session() as db:
        return lookups(db)


@router.get("/businesses")
def list_businesses(user=Depends(identity)):
    with session() as db:
        return [serialize(r, True) for r in db.scalars(select(Comercio).order_by(Comercio.nombre_fantasia)).unique()]


@router.post("/businesses", status_code=201)
def create_business(data: BusinessData, request: Request, user=Depends(identity)):
    with session() as db:
        row = Comercio(public_id=uuid.uuid4().hex)
        apply_data(db, row, data, user)
        db.add(row)
        db.flush()
        audit(db, user, request, "CREAR", row, {"after": serialize(row, True)})
        db.commit()
        return serialize(row, True)


@router.put("/businesses/{public_id}")
def update_business(public_id: str, data: BusinessData, request: Request, user=Depends(identity)):
    with session() as db:
        row = find_business(db, public_id)
        before = serialize(row, True)
        apply_data(db, row, data, user)
        db.flush()
        audit(db, user, request, "EDITAR", row, {"before": before, "after": serialize(row, True)})
        db.commit()
        return serialize(row, True)


@router.post("/businesses/{public_id}/photos", status_code=201)
def upload_photo(public_id: str, request: Request, file: UploadFile, user=Depends(identity)):
    with session() as db:
        row = find_business(db, public_id)
        if user["role"] != "Administrador":
            row.estado_moderacion = "Pendiente"
        if len(row.fotos) >= 8:
            raise HTTPException(422, "Máximo ocho fotografías por ficha")
        content = file.file.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(413, "La imagen supera los 8 MB")
        filename = f"{uuid.uuid4().hex}.webp"
        target = media_dir() / filename
        try:
            image = Image.open(io.BytesIO(content))
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1600, 1600))
            image.save(target, "WEBP", quality=85)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise HTTPException(422, "La imagen no es válida")
        try:
            row.fotos.append(Fotografia(ruta_archivo=filename, orden=len(row.fotos) + 1,
                                        es_portada=not row.fotos, texto_alt=row.nombre_fantasia))
            audit(db, user, request, "AGREGAR_FOTO", row, {"file": filename})
            db.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return serialize(row, True)


class PhotoData(BaseModel):
    alt: str = Field(max_length=150)
    cover: bool = False
    order: int = Field(ge=0, le=100)


@router.put("/businesses/{public_id}/photos/{photo_id}")
def update_photo(public_id: str, photo_id: int, data: PhotoData, request: Request, user=Depends(identity)):
    with session() as db:
        row = find_business(db, public_id)
        photo = next((p for p in row.fotos if p.id == photo_id), None)
        if not photo:
            raise HTTPException(404, "Fotografía no encontrada")
        if user["role"] != "Administrador":
            row.estado_moderacion = "Pendiente"
        if data.cover:
            for p in row.fotos:
                p.es_portada = False
        photo.es_portada, photo.texto_alt, photo.orden = data.cover, data.alt, data.order
        audit(db, user, request, "EDITAR_FOTO", row, data.model_dump())
        db.commit()
        return serialize(row, True)


@router.delete("/businesses/{public_id}/photos/{photo_id}")
def delete_photo(public_id: str, photo_id: int, request: Request, user=Depends(identity)):
    with session() as db:
        row = find_business(db, public_id)
        photo = next((p for p in row.fotos if p.id == photo_id), None)
        if not photo:
            raise HTTPException(404, "Fotografía no encontrada")
        if user["role"] != "Administrador":
            row.estado_moderacion = "Pendiente"
        filename = photo.ruta_archivo
        row.fotos.remove(photo)
        if row.fotos and not any(p.es_portada for p in row.fotos):
            row.fotos[0].es_portada = True
        audit(db, user, request, "ELIMINAR_FOTO", row, {"file": filename})
        db.commit()
        (media_dir() / filename).unlink(missing_ok=True)
        return serialize(row, True)


@router.get("/audit")
def audit_log(user=Depends(administrator)):
    with session() as db:
        return [{"id": a.id, "user_id": a.id_usuario, "action": a.tipo_operacion, "business_id": a.id_comercio,
                 "detail": a.detalle_json, "at": a.fecha_hora.isoformat()} for a in db.scalars(
                     select(Auditoria).order_by(Auditoria.id.desc()).limit(200))]


@router.get("/metrics")
def metrics(user=Depends(identity)):
    with session() as db:
        rows = db.execute(select(Metrica.tipo_evento, func.count(), func.avg(Metrica.latencia_ms)).where(
            Metrica.fecha_hora >= now() - timedelta(days=90)).group_by(Metrica.tipo_evento)).all()
        return [{"event": event, "count": count, "average_ms": round(latency) if latency is not None else None}
                for event, count, latency in rows]


class UserData(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=100, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: Literal["Administrador", "Operador Territorial"]
    active: bool = True
    password: str = Field(default="", max_length=256)


@router.get("/users")
def users(user=Depends(administrator)):
    with session() as db:
        return [{"id": u.id, "name": u.nombre_completo, "email": u.correo_institucional,
                 "role": u.rol, "active": u.activo} for u in db.scalars(select(Usuario))]


@router.post("/users", status_code=201)
@router.put("/users/{user_id}")
def save_user(data: UserData, request: Request, user_id: int | None = None, user=Depends(administrator)):
    with session() as db:
        row = db.get(Usuario, user_id) if user_id else Usuario()
        if not row:
            raise HTTPException(404, "Usuario no encontrado")
        if row.id == user["id"] and (not data.active or data.role != "Administrador"):
            raise HTTPException(422, "No puedes quitar tus propios permisos")
        if (not user_id or data.password) and len(data.password) < 12:
            raise HTTPException(422, "La contraseña debe tener al menos 12 caracteres")
        row.nombre_completo, row.correo_institucional = data.name, data.email.strip().lower()
        row.rol, row.activo = data.role, data.active
        if data.password:
            row.password_hash = hasher.hash(data.password)
        db.add(row)
        if user_id:
            db.execute(delete(Sesion).where(Sesion.id_usuario == user_id))
        audit(db, user, request, "GUARDAR_USUARIO", detail={"email": row.correo_institucional, "role": row.rol, "active": row.activo})
        try:
            db.commit()
        except IntegrityError:
            raise HTTPException(409, "El correo ya está registrado")
        return {"ok": True}
