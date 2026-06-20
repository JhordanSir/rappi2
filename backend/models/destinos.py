from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from core.database import Base


class Destino(Base):
    """Un punto de entrega de una orden. Una orden puede tener varios destinos
    (un remitente, varios destinatarios). Cada destino lleva su propio paquete y
    se tarifa como un tramo recojo→entrega; el total de la orden es la suma de tramos."""
    __tablename__ = "destinos"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    secuencia = Column(Integer, default=1, nullable=False)

    direccion = Column(String(200), nullable=False)
    distrito = Column(String(80), nullable=True)
    lat = Column(Numeric(9, 6), nullable=True)
    lon = Column(Numeric(9, 6), nullable=True)

    # Paquete de este destino (alimenta el precio del tramo).
    peso_kg = Column(Numeric(8, 2), nullable=True)
    largo_cm = Column(Numeric(7, 1), nullable=True)
    ancho_cm = Column(Numeric(7, 1), nullable=True)
    alto_cm = Column(Numeric(7, 1), nullable=True)

    nombre_destinatario = Column(String(120), nullable=True)
    subtotal = Column(Numeric(10, 2), nullable=True)  # precio del tramo
    nota = Column(String(200), nullable=True)  # observación de entrega o motivo de fallo

    # Estado de la entrega de este destino y datos de la prueba.
    estado = Column(String(20), default="Pendiente", nullable=False)
    entrega_lat = Column(Numeric(9, 6), nullable=True)
    entrega_lon = Column(Numeric(9, 6), nullable=True)
    entrega_receptor = Column(String(120), nullable=True)
    fecha_entrega = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("estado IN ('Pendiente','Entregado','Fallida')", name="destino_estado"),
    )

    orden = relationship("Orden", back_populates="destinos")
