"""Sesiones locales opacas, Argon2id y límite de red para administración."""
import hashlib
import ipaddress
import os
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select

from .db import session
from .models import Sesion, Usuario

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))
COOKIE = "quibar_session"
_attempts = defaultdict(deque)
_attempt_lock = Lock()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def check_network(request: Request):
    host = request.client.host if request.client else ""
    try:
        ip = ipaddress.ip_address(host)
        ranges = os.environ.get("QUIBAR_ADMIN_NETWORKS", "127.0.0.0/8,::1/128,100.64.0.0/10")
        if any(ip in ipaddress.ip_network(net.strip()) for net in ranges.split(",")):
            return
    except ValueError:
        pass
    raise HTTPException(403, "Administración disponible solo en este equipo o por la red privada.")


def same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Origen no permitido")


def throttle_login(request: Request):
    key = request.client.host
    with _attempt_lock:
        # Bound memory even if requests arrive through many tailnet peers.
        if len(_attempts) > 1000:
            _attempts.clear()
        attempts = _attempts[key]
        now = time.time()
        while attempts and attempts[0] < now - 600:
            attempts.popleft()
        if len(attempts) >= 5:
            raise HTTPException(429, "Demasiados intentos. Espera diez minutos.")
        attempts.append(now)


def identity(request: Request):
    check_network(request)
    token = request.cookies.get(COOKIE, "")
    with session() as db:
        row = db.get(Sesion, digest(token)) if token else None
        user = db.get(Usuario, row.id_usuario) if row and row.vence > time.time() else None
        if not user or not user.activo:
            raise HTTPException(401, "Inicia sesión para continuar")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            same_origin(request)
            if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row.csrf):
                raise HTTPException(403, "Sesión no válida para esta operación")
        return {"id": user.id, "name": user.nombre_completo, "email": user.correo_institucional,
                "role": user.rol, "csrf": row.csrf}


def administrator(user=Depends(identity)):
    if user["role"] != "Administrador":
        raise HTTPException(403, "Se requiere el rol Administrador")
    return user


def create_user(email, name, password, role="Administrador"):
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    with session() as db:
        if db.scalar(select(Usuario).where(Usuario.correo_institucional == email.strip().lower())):
            raise ValueError("El usuario ya existe")
        user = Usuario(correo_institucional=email.strip().lower(), nombre_completo=name,
                       password_hash=hasher.hash(password), rol=role)
        db.add(user)
        db.commit()
