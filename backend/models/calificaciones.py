from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Calificacion(Base):
    """Calificación que el cliente da a la entrega/conductor de una orden entregada.
    Una calificación por orden (relación 1-1 con Orden)."""

    __tablename__ = "calificaciones"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("conductores.id", ondelete="SET NULL"), nullable=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    puntaje = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("puntaje BETWEEN 1 AND 5", name="calificacion_puntaje"),
    )

    orden = relationship("Orden", back_populates="calificacion")
