from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from core.database import Base

class Orden(Base):
    __tablename__ = "ordenes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"))
    estado = Column(String(30), default="Pendiente")
    origen_geom = Column(Geometry('POINT', srid=4326), nullable=False)
    destino_geom = Column(Geometry('POINT', srid=4326), nullable=False)
    origen_texto = Column(Text, nullable=False)
    destino_texto = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=func.now())

    __table_args__ = (
        CheckConstraint("estado IN ('Pendiente', 'En Proceso', 'En Tránsito', 'Entregado', 'Cancelado')", name="estado_valido"),
    )

    cliente = relationship("Cliente")

class Asignacion(Base):
    __tablename__ = "asignaciones"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"))
    conductor_id = Column(Integer, ForeignKey("conductores.id", ondelete="RESTRICT"))
    vehiculo_id = Column(Integer, ForeignKey("vehiculos.id", ondelete="RESTRICT"))
    estado = Column(String(30), default="Asignado")
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_fin = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    orden = relationship("Orden")
    conductor = relationship("Conductor")
    vehiculo = relationship("Vehiculo")

class RutaPlanificada(Base):
    __tablename__ = "rutas_planificadas"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"))
    ruta_linea = Column(Geometry('LINESTRING', srid=4326), nullable=True)
    tolerancia_metros = Column(Integer, default=50)
    geocerca_poligono = Column(Geometry('POLYGON', srid=4326), nullable=True)
    distancia_km = Column(Numeric, nullable=True)
    # Using String for simplicity with INTERVAL representation if needed, or PostgreSQL INTERVAL
    # SQLAlchemy Native Interval:
    from sqlalchemy.dialects.postgresql import INTERVAL
    tiempo_estimado = Column(INTERVAL, nullable=True)
    created_at = Column(DateTime, default=func.now())

    orden = relationship("Orden")

class ParadaPlanificada(Base):
    __tablename__ = "paradas_planificadas"

    id = Column(Integer, primary_key=True, index=True)
    ruta_id = Column(Integer, ForeignKey("rutas_planificadas.id", ondelete="CASCADE"))
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"))
    geom = Column(Geometry('POINT', srid=4326), nullable=False)
    secuencia = Column(Integer, nullable=False)
    estado = Column(String(30), default="Pendiente")

    ruta = relationship("RutaPlanificada")
    orden = relationship("Orden")
