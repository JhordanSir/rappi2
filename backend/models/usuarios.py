from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    # Nullable: los usuarios solo-Google no tienen contraseña local.
    password_hash = Column(Text, nullable=True)
    rol_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), unique=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_registro = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    # Identidad de Google (OAuth). google_sub es el id estable del usuario en Google
    # y la clave de vinculación principal; auth_provider distingue local/google.
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    auth_provider = Column(String(20), default="local", nullable=False)
    avatar_url = Column(Text, nullable=True)

    rol = relationship("Rol", back_populates="usuarios", lazy="joined")
    cliente = relationship("Cliente", back_populates="usuario", uselist=False)
    tokens = relationship("Token", back_populates="usuario", cascade="all, delete-orphan")
    conductor = relationship("Conductor", back_populates="usuario", uselist=False)


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(Text, unique=True, nullable=False, index=True)
    fecha_expiracion = Column(DateTime(timezone=True), nullable=False)
    revocado = Column(Boolean, default=False, nullable=False)

    usuario = relationship("Usuario", back_populates="tokens")
