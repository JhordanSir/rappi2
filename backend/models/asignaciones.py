from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Table
from sqlalchemy.orm import relationship

from core.database import Base

# Una asignación puede cubrir varias órdenes (la ruta del conductor agrupa varias
# entregas). orden_id sigue siendo la orden "principal" por compatibilidad.
asignacion_ordenes = Table(
    "asignacion_ordenes",
    Base.metadata,
    Column("asignacion_id", ForeignKey("asignaciones.id", ondelete="CASCADE"), primary_key=True),
    Column("orden_id", ForeignKey("ordenes.id", ondelete="CASCADE"), primary_key=True),
)


class Asignacion(Base):
    __tablename__ = "asignaciones"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id", ondelete="RESTRICT"), nullable=False, index=True)
    vehiculo_placa = Column(
        String(15),
        ForeignKey("vehiculos.placa", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    estado = Column(String(20), default="Asignada", nullable=False, index=True)
    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin = Column(DateTime(timezone=True), nullable=True)
    entrega_lat = Column(Numeric(9, 6), nullable=True)
    entrega_lon = Column(Numeric(9, 6), nullable=True)
    entrega_receptor = Column(String(120), nullable=True)

    orden = relationship("Orden", back_populates="asignaciones")
    # Todas las órdenes agrupadas en esta asignación (incluye la principal).
    ordenes = relationship("Orden", secondary=asignacion_ordenes, lazy="selectin")
    conductor = relationship("Conductor", back_populates="asignaciones")

    @property
    def orden_ids(self) -> list[int]:
        return [o.id for o in self.ordenes]
    vehiculo = relationship("Vehiculo", back_populates="asignaciones")
    incidencias = relationship("Incidencia", back_populates="asignacion", cascade="all, delete-orphan")
