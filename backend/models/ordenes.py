from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Orden(Base):
    __tablename__ = "ordenes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    estado = Column(String(20), default="Pendiente", nullable=False)
    direccion_origen = Column(String(200), nullable=False)
    distrito_origen = Column(String(80), nullable=True)
    lat_origen = Column(Numeric(9, 6), nullable=True)
    lon_origen = Column(Numeric(9, 6), nullable=True)
    direccion_destino = Column(String(200), nullable=False)
    distrito_destino = Column(String(80), nullable=True)
    lat_destino = Column(Numeric(9, 6), nullable=True)
    lon_destino = Column(Numeric(9, 6), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    total = Column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('Pendiente','En Proceso','En Tránsito','Entregado','Cancelado')",
            name="orden_estado",
        ),
    )

    cliente = relationship("Cliente", back_populates="ordenes")
    pagos = relationship("Pago", back_populates="orden", cascade="all, delete-orphan")
    facturas = relationship("Factura", back_populates="orden", cascade="all, delete-orphan")
    asignaciones = relationship("Asignacion", back_populates="orden", cascade="all, delete-orphan")
    rutas = relationship("RutaPlanificada", back_populates="orden", cascade="all, delete-orphan")


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha_pago = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    estado = Column(String(20), default="Pendiente", nullable=False)
    referencia_banco = Column(String(80), nullable=True)

    orden = relationship("Orden", back_populates="pagos")


class Factura(Base):
    __tablename__ = "facturas"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    ruc = Column(String(20), nullable=True)
    monto = Column(Numeric(10, 2), nullable=False)
    url = Column(Text, nullable=True)

    orden = relationship("Orden", back_populates="facturas")
