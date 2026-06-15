from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from core.database import Base


class Asignacion(Base):
    __tablename__ = "asignaciones"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id", ondelete="RESTRICT"), nullable=False)
    vehiculo_placa = Column(
        String(15),
        ForeignKey("vehiculos.placa", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    estado = Column(String(20), default="Asignada", nullable=False)
    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin = Column(DateTime(timezone=True), nullable=True)
    entrega_lat = Column(Numeric(9, 6), nullable=True)
    entrega_lon = Column(Numeric(9, 6), nullable=True)
    entrega_receptor = Column(String(120), nullable=True)

    orden = relationship("Orden", back_populates="asignaciones")
    conductor = relationship("Conductor", back_populates="asignaciones")
    vehiculo = relationship("Vehiculo", back_populates="asignaciones")
    incidencias = relationship("Incidencia", back_populates="asignacion", cascade="all, delete-orphan")
