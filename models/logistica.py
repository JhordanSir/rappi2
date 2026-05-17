from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base

class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String(20), unique=True, index=True, nullable=False)
    tipo = Column(String(50), nullable=False)
    capacidad_kg = Column(Numeric, nullable=False)
    estado = Column(String(30), default="Operativo")
    fecha_mantenimiento = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True)
    nombre = Column(String(100), nullable=False)
    licencia = Column(String(50), unique=True, nullable=False)
    disponibilidad = Column(String(30), default="Disponible")
    is_active = Column(Boolean, default=True)

    usuario = relationship("Usuario")
