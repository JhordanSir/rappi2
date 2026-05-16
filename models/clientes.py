from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from core.database import Base

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    telefono = Column(String(20))
    atencion_nam = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    direcciones = relationship("ClienteDireccion", back_populates="cliente", cascade="all, delete-orphan")

class ClienteDireccion(Base):
    __tablename__ = "clientes_direcciones"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"))
    geom = Column(Geometry('POINT', srid=4326, spatial_index=False), nullable=False)
    direccion_texto = Column(Text, nullable=False)
    ciudad = Column(String(100))
    estado = Column(String(100))
    cp = Column(String(20))
    es_principal = Column(Boolean, default=False)

    cliente = relationship("Cliente", back_populates="direcciones")
