from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class Conductor(Base):
    __tablename__ = "conductores"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), unique=True, nullable=False)
    vehiculo_placa = Column(
        String(15),
        ForeignKey("vehiculos.placa", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    nombre = Column(String(100), nullable=False)
    licencia = Column(String(30), unique=True, nullable=False)
    disponibilidad = Column(String(20), default="Disponible", nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    usuario = relationship("Usuario", back_populates="conductor")
    vehiculo = relationship("Vehiculo", back_populates="conductores")
    asignaciones = relationship("Asignacion", back_populates="conductor")
