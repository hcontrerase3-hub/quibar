"""Lugares públicos y administración del circuito Santa Bárbara–Huequecura–Ralco."""
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from .admin import audit
from .db import approved, session
from .models import Comuna, PuntoInteres, Totem
from .security import administrator, identity

SECTORS = ['Santa Bárbara', 'Huequecura', 'Ralco']
# View/validation envelope, never a fabricated location for a business or kiosk.
BOUNDS = [-72.2, -38.05, -71.35, -37.55]
Sector = Literal['Santa Bárbara', 'Huequecura', 'Ralco']
Category = Literal['Mirador', 'Naturaleza', 'Patrimonio', 'Plaza', 'Actividad', 'Cultura']
router = APIRouter()


def within(latitude, longitude):
    return BOUNDS[0] <= longitude <= BOUNDS[2] and BOUNDS[1] <= latitude <= BOUNDS[3]


def interest_dict(row):
    return {key: getattr(row, key) for key in ('id', 'name', 'category', 'commune', 'sector', 'description',
            'latitude', 'longitude', 'access', 'hours', 'source', 'access_verified', 'status', 'demo')}


def public_places():
    places = []
    for row in approved():
        if row['commune'] == 'Quilaco' or (row.get('sector') not in SECTORS and row['commune'] != 'Santa Bárbara'):
            continue
        located = bool(row.get('location_verified') and row.get('location_source') and
                       row['latitude'] is not None and row['longitude'] is not None and
                       within(row['latitude'], row['longitude']))
        places.append({**row, 'kind': 'business', 'key': f"business:{row['id']}",
                       'located': located, 'latitude': row['latitude'] if located else None,
                       'longitude': row['longitude'] if located else None})
    with session() as db:
        for row in db.scalars(select(PuntoInteres).where(PuntoInteres.status == 'Aprobado',
                                                       PuntoInteres.access_verified.is_(True))):
            if row.sector not in SECTORS or not within(row.latitude, row.longitude):
                continue
            places.append({**interest_dict(row), 'kind': 'interest', 'key': f'interest:{row.id}',
                           'summary': row.description[:200], 'located': True,
                           'photos': [], 'offerings': [], 'area': row.access})
    return sorted(places, key=lambda p: (p['sector'], p['name']))


def station():
    with session() as db:
        row = db.get(Totem, 1)
        configured = bool(row and row.verified and row.latitude is not None and row.longitude is not None)
        return {'name': row.name if row else 'Tótem Quíbar', 'configured': configured,
                'latitude': row.latitude if configured else None, 'longitude': row.longitude if configured else None}


@router.get('/api/quibar/places')
def places():
    return {'places': public_places(), 'sectors': SECTORS, 'bounds': BOUNDS, 'station': station()}


class InterestData(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=150)
    category: Category
    commune: str = Field(min_length=2, max_length=50)
    sector: Sector
    description: str = Field(min_length=5, max_length=4000)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    access: str = Field(min_length=5, max_length=1000)
    hours: str = Field(default='', max_length=255)
    source: str = Field(min_length=5, max_length=1000)
    access_verified: bool = False
    status: Literal['Pendiente', 'Aprobado', 'Suspendido'] = 'Pendiente'
    demo: bool = False

    @model_validator(mode='after')
    def valid_location(self):
        if not within(self.latitude, self.longitude):
            raise ValueError('La ubicación debe estar dentro del circuito Santa Bárbara–Huequecura–Ralco')
        if self.status == 'Aprobado' and not self.access_verified:
            raise ValueError('Verifica el acceso antes de aprobar el lugar')
        return self


@router.get('/api/quibar/admin/interests')
def interests(user=Depends(identity)):
    with session() as db:
        return [interest_dict(row) for row in db.scalars(select(PuntoInteres).order_by(PuntoInteres.name))]


def save_interest(data, request, user, identifier=None):
    if data.status == 'Aprobado' and user['role'] != 'Administrador':
        raise HTTPException(403, 'Solo un administrador puede aprobar lugares')
    with session() as db:
        if not db.scalar(select(Comuna).where(Comuna.nombre == data.commune)):
            raise HTTPException(422, 'Comuna no válida')
        row = db.get(PuntoInteres, identifier) if identifier else PuntoInteres(id=uuid.uuid4().hex)
        if row is None:
            raise HTTPException(404, 'Lugar no encontrado')
        before = interest_dict(row) if identifier else None
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        db.add(row)
        db.flush()
        after = interest_dict(row)
        audit(db, user, request, 'EDITAR_LUGAR' if identifier else 'CREAR_LUGAR',
              detail={'kind': 'interest', 'id': row.id, 'before': before, 'after': after})
        db.commit()
        return after


@router.post('/api/quibar/admin/interests', status_code=201)
def create_interest(data: InterestData, request: Request, user=Depends(identity)):
    return save_interest(data, request, user)


@router.put('/api/quibar/admin/interests/{identifier}')
def update_interest(identifier: str, data: InterestData, request: Request, user=Depends(identity)):
    return save_interest(data, request, user, identifier)


class StationData(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    source: str = Field(min_length=5, max_length=1000)
    verified: bool

    @model_validator(mode='after')
    def in_circuit(self):
        if not within(self.latitude, self.longitude):
            raise ValueError('Configura un tótem dentro del circuito')
        return self


@router.get('/api/quibar/admin/station')
def read_station(user=Depends(identity)):
    with session() as db:
        row = db.get(Totem, 1)
        return {key: getattr(row, key) for key in StationData.model_fields}


@router.put('/api/quibar/admin/station')
def update_station(data: StationData, request: Request, user=Depends(administrator)):
    with session() as db:
        row = db.get(Totem, 1)
        before = {key: getattr(row, key) for key in StationData.model_fields}
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, request, 'CONFIGURAR_TOTEM', detail={'before': before, 'after': data.model_dump()})
        db.commit()
    return data.model_dump()
