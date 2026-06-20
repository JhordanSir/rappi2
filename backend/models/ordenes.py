from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from core.database import Base


class Orden(Base):
    __tablename__ = "ordenes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    estado = Column(String(20), default="Pendiente", nullable=False, index=True)
    direccion_origen = Column(String(200), nullable=False)
    distrito_origen = Column(String(80), nullable=True)
    lat_origen = Column(Numeric(9, 6), nullable=True)
    lon_origen = Column(Numeric(9, 6), nullable=True)
    direccion_destino = Column(String(200), nullable=False)
    distrito_destino = Column(String(80), nullable=True)
    lat_destino = Column(Numeric(9, 6), nullable=True)
    lon_destino = Column(Numeric(9, 6), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    total = Column(Numeric(10, 2), nullable=True)  # calculado por el servidor (no por el cliente)

    # Datos del paquete (alimentan el cálculo de precio).
    peso_kg = Column(Numeric(8, 2), nullable=True)
    largo_cm = Column(Numeric(7, 1), nullable=True)
    ancho_cm = Column(Numeric(7, 1), nullable=True)
    alto_cm = Column(Numeric(7, 1), nullable=True)

    # Nivel de servicio (estandar/express/urgente) y programación (null = inmediato).
    nivel_servicio = Column(String(20), default="estandar", nullable=False)
    programado_para = Column(DateTime(timezone=True), nullable=True)

    # Ajuste manual de precio aplicado por staff (descuento negativo / recargo positivo).
    ajuste_monto = Column(Numeric(10, 2), nullable=True)
    ajuste_motivo = Column(String(200), nullable=True)
    ajuste_por = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('Pendiente de Pago','Pendiente','En Proceso','En Tránsito','Entregado','Cancelado')",
            name="orden_estado",
        ),
        CheckConstraint(
            "nivel_servicio IN ('estandar','express','urgente')",
            name="orden_nivel_servicio",
        ),
    )

    cliente = relationship("Cliente", back_populates="ordenes")
    pagos = relationship("Pago", back_populates="orden", cascade="all, delete-orphan")
    facturas = relationship("Factura", back_populates="orden", cascade="all, delete-orphan")
    asignaciones = relationship("Asignacion", back_populates="orden", cascade="all, delete-orphan")
    destinos = relationship("Destino", back_populates="orden", cascade="all, delete-orphan", order_by="Destino.secuencia")
    rutas = relationship("RutaPlanificada", back_populates="orden", cascade="all, delete-orphan")
    calificacion = relationship("Calificacion", back_populates="orden", uselist=False, cascade="all, delete-orphan")


class Pago(Base):
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha_pago = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    estado = Column(String(20), default="Pendiente", nullable=False)
    referencia_banco = Column(String(80), nullable=True)
    # Datos de la pasarela (MercadoPago Checkout Pro). proveedor=None => pago manual/staff.
    metodo = Column(String(40), nullable=True)
    proveedor = Column(String(40), nullable=True)
    preference_id = Column(String(120), nullable=True)
    external_id = Column(String(120), nullable=True)

    # Los reportes filtran casi siempre por estado='Pagado' + rango de fecha_pago;
    # un índice compuesto cubre ese patrón y el ordenamiento por fecha del listado.
    __table_args__ = (
        Index("ix_pagos_estado_fecha_pago", "estado", "fecha_pago"),
    )

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
