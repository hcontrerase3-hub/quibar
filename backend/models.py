"""Modelo relacional del catálogo y administración local de Quíbar."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Comuna(Base):
    __tablename__ = "comuna"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    provincia: Mapped[str] = mapped_column(default="Biobío")
    region: Mapped[str] = mapped_column(default="Región del Biobío")


class Rubro(Base):
    __tablename__ = "rubro"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    icono: Mapped[str] = mapped_column(default="shop")
    descripcion: Mapped[str] = mapped_column(default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Comercio(Base):
    __tablename__ = "comercio"
    __table_args__ = (CheckConstraint("estado_moderacion IN ('Pendiente','Aprobado','Suspendido')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True)
    id_comuna: Mapped[int] = mapped_column(ForeignKey("comuna.id"))
    id_rubro: Mapped[int] = mapped_column(ForeignKey("rubro.id"))
    nombre_fantasia: Mapped[str] = mapped_column(String(150))
    razon_social: Mapped[str] = mapped_column(default="")
    rut_contribuyente: Mapped[str] = mapped_column(default="")
    resumen: Mapped[str] = mapped_column(Text)
    descripcion: Mapped[str] = mapped_column(Text)
    direccion_texto: Mapped[str] = mapped_column(String(255))
    latitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitud: Mapped[float | None] = mapped_column(Float, nullable=True)
    telefono_whatsapp: Mapped[str] = mapped_column(default="")
    horario_atencion: Mapped[str] = mapped_column(String(255))
    estado_moderacion: Mapped[str] = mapped_column(default="Pendiente", index=True)
    destacado: Mapped[bool] = mapped_column(Boolean, default=False)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    sector: Mapped[str] = mapped_column(String(50), default="")
    location_source: Mapped[str] = mapped_column(Text, default="")
    location_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    ofertas: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[str] = mapped_column(Text, default="")
    visual: Mapped[str] = mapped_column(default="shop")
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    comuna: Mapped[Comuna] = relationship(lazy="joined")
    rubro: Mapped[Rubro] = relationship(lazy="joined")
    fotos: Mapped[list["Fotografia"]] = relationship(cascade="all, delete-orphan", order_by="Fotografia.orden", lazy="selectin")


class PuntoInteres(Base):
    __tablename__ = "punto_interes"
    __table_args__ = (CheckConstraint("status IN ('Pendiente','Aprobado','Suspendido')"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(50))
    commune: Mapped[str] = mapped_column(String(50))
    sector: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    access: Mapped[str] = mapped_column(Text)
    hours: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(Text)
    access_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="Pendiente")


class Totem(Base):
    __tablename__ = "totem"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), default="Tótem Quíbar")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class Fotografia(Base):
    __tablename__ = "fotografia_comercio"
    id: Mapped[int] = mapped_column(primary_key=True)
    id_comercio: Mapped[int] = mapped_column(ForeignKey("comercio.id", ondelete="CASCADE"))
    ruta_archivo: Mapped[str] = mapped_column(unique=True)
    orden: Mapped[int] = mapped_column(default=1)
    es_portada: Mapped[bool] = mapped_column(default=False)
    texto_alt: Mapped[str] = mapped_column(default="")


class Usuario(Base):
    __tablename__ = "usuario_admin"
    __table_args__ = (CheckConstraint("rol IN ('Administrador','Operador Territorial')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(100))
    correo_institucional: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(default="Operador Territorial")
    activo: Mapped[bool] = mapped_column(default=True)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Sesion(Base):
    __tablename__ = "sesion_admin"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_admin.id", ondelete="CASCADE"))
    csrf: Mapped[str] = mapped_column(String(64))
    vence: Mapped[float] = mapped_column(Float)


class Auditoria(Base):
    __tablename__ = "registro_auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario_admin.id"))
    id_comercio: Mapped[int | None] = mapped_column(ForeignKey("comercio.id"), nullable=True)
    tipo_operacion: Mapped[str] = mapped_column(String(50))
    detalle_json: Mapped[dict] = mapped_column(JSON)
    ip_origen: Mapped[str] = mapped_column(String(45))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Metrica(Base):
    __tablename__ = "metrica_evento"
    id: Mapped[int] = mapped_column(primary_key=True)
    id_comercio: Mapped[int | None] = mapped_column(ForeignKey("comercio.id"), nullable=True)
    tipo_evento: Mapped[str] = mapped_column(String(50), index=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
