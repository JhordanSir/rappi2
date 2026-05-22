from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from core.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    telefono = Column(String(20), nullable=True)
    cc_id = Column(String(30), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_registro = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    direcciones = relationship("ClienteDireccion", back_populates="cliente", cascade="all, delete-orphan")
    ordenes = relationship("Orden", back_populates="cliente", cascade="all, delete-orphan")
    usuario = relationship("Usuario", back_populates="cliente", uselist=False)


class ClienteDireccion(Base):
    __tablename__ = "clientes_direcciones"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    direccion = Column(String(200), nullable=False)
    distrito = Column(String(80), nullable=True)
    ciudad = Column(String(80), nullable=True)
    estado = Column(String(80), nullable=True)
    pais = Column(String(80), nullable=True)
    es_principal = Column(Boolean, default=False, nullable=False)

    cliente = relationship("Cliente", back_populates="direcciones")
