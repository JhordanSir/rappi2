from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    rol_id = Column(Integer, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), unique=True, nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_registro = Column(DateTime, default=func.now(), nullable=False)

    rol = relationship("Rol", back_populates="usuarios", lazy="joined")
    cliente = relationship("Cliente", back_populates="usuario", uselist=False)
    tokens = relationship("Token", back_populates="usuario", cascade="all, delete-orphan")
    conductor = relationship("Conductor", back_populates="usuario", uselist=False)


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(Text, unique=True, nullable=False, index=True)
    fecha_expiracion = Column(DateTime, nullable=False)
    revocado = Column(Boolean, default=False, nullable=False)

    usuario = relationship("Usuario", back_populates="tokens")
