from sqlalchemy import Boolean, Column, DateTime, Numeric, String
from sqlalchemy.orm import relationship

from core.database import Base


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    placa = Column(String(15), primary_key=True, index=True)
    tipo = Column(String(40), nullable=False)
    capacidad_kg = Column(Numeric(8, 2), nullable=False)
    # Dimensiones útiles de carga (cm) para validar cubicaje: ¿cabe el paquete físicamente?
    largo_cm = Column(Numeric(7, 1), nullable=True)
    ancho_cm = Column(Numeric(7, 1), nullable=True)
    alto_cm = Column(Numeric(7, 1), nullable=True)
    estado = Column(String(20), default="Operativo", nullable=False)
    fecha_mantenimiento = Column(DateTime(timezone=True), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)

    conductores = relationship("Conductor", back_populates="vehiculo")
    asignaciones = relationship("Asignacion", back_populates="vehiculo")
