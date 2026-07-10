from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    # Nullable: los usuarios federados (Keycloak) no tienen contraseña local.
    password_hash = Column(Text, nullable=True)
    rol_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), unique=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_registro = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    # Identidad federada. keycloak_sub es el `sub` estable del usuario en Keycloak y la
    # clave de vinculación principal; auth_provider distingue el origen (keycloak/local).
    keycloak_sub = Column(String(255), unique=True, nullable=True, index=True)
    auth_provider = Column(String(20), default="local", nullable=False)
    avatar_url = Column(Text, nullable=True)

    rol = relationship("Rol", back_populates="usuarios", lazy="joined")
    cliente = relationship("Cliente", back_populates="usuario", uselist=False)
    conductor = relationship("Conductor", back_populates="usuario", uselist=False)
