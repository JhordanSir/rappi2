from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.orm import relationship

from core.database import Base


class RutaPlanificada(Base):
    __tablename__ = "rutas_planificadas"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    distancia_km = Column(Numeric(8, 2), nullable=True)
    tiempo_estimado = Column(INTERVAL, nullable=True)
    # Geometría real por calles (GeoJSON LineString) para dibujar la ruta sin depender del navegador
    geometria = Column(JSON, nullable=True)

    orden = relationship("Orden", back_populates="rutas")
    paradas = relationship("Parada", back_populates="ruta", cascade="all, delete-orphan", order_by="Parada.secuencia")


class Parada(Base):
    __tablename__ = "paradas"

    id = Column(Integer, primary_key=True, index=True)
    ruta_id = Column(Integer, ForeignKey("rutas_planificadas.id", ondelete="CASCADE"), nullable=False, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="SET NULL"), nullable=True)
    # Una parada de entrega apunta al destino que representa (las de recojo no).
    destino_id = Column(Integer, ForeignKey("destinos.id", ondelete="SET NULL"), nullable=True)
    direccion = Column(String(200), nullable=False)
    distrito = Column(String(80), nullable=True)
    lat = Column(Numeric(9, 6), nullable=True)
    lon = Column(Numeric(9, 6), nullable=True)
    secuencia = Column(Integer, nullable=False)
    fecha_paso = Column(DateTime(timezone=True), nullable=True)
    estado = Column(String(20), default="Pendiente", nullable=False)

    __table_args__ = (
        UniqueConstraint("ruta_id", "secuencia", name="uq_paradas_ruta_secuencia"),
    )

    ruta = relationship("RutaPlanificada", back_populates="paradas")
