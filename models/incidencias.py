from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Incidencia(Base):
    __tablename__ = "incidencias"

    id = Column(Integer, primary_key=True, index=True)
    asignacion_id = Column(Integer, ForeignKey("asignaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    fecha = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    severidad = Column(Integer, nullable=False)
    notas = Column(Text, nullable=True)
    evidencia_url = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("severidad BETWEEN 1 AND 5", name="severidad_rango"),
    )

    asignacion = relationship("Asignacion", back_populates="incidencias")
