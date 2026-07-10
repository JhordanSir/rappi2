from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Incidencia(Base):
    __tablename__ = "incidencias"

    id = Column(Integer, primary_key=True, index=True)
    asignacion_id = Column(Integer, ForeignKey("asignaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    fecha = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    # La severidad la deriva el sistema (por tipo) o la ajusta el admin; el chofer no la fija.
    severidad = Column(Integer, nullable=False)
    # Quién originó la incidencia: reporte del chofer, automática (desvío/retraso) o el admin.
    origen = Column(String(20), default="chofer", nullable=False)
    notas = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("severidad BETWEEN 1 AND 5", name="severidad_rango"),
        CheckConstraint("origen IN ('chofer','automatica','admin')", name="incidencia_origen"),
    )

    asignacion = relationship("Asignacion", back_populates="incidencias")
