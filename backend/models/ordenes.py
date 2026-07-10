from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from core.database import Base
from models.destinos import Destino


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

    # El paquete (peso/dimensiones) vive por destino (models/destinos.py), NO aquí: el peso/volumen
    # de la orden se derivan de los destinos (ver peso_total_kg / volumen_total_cm3 abajo).

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

    # --- Agregados FÍSICOS del paquete: se calculan sobre los destinos (fuente de verdad),
    # nunca se persisten (evita la desincronización del modelo redundante anterior). El lado
    # Python requiere `destinos` cargado (usar selectinload); el lado .expression permite
    # filtrar/ordenar por peso en SQL sin instanciar. ---
    # Nota: los valores pueden venir como Decimal (cargados de la BD) o como float (recién
    # asignados desde un payload Pydantic, con expire_on_commit=False). Se normaliza cada uno
    # a Decimal con Decimal(str(...)) para no mezclar tipos al sumar (igual que pricing_service).
    @hybrid_property
    def peso_total_kg(self) -> Decimal:
        return sum(
            (Decimal(str(d.peso_kg)) for d in self.destinos if d.peso_kg is not None),
            Decimal("0"),
        )

    @peso_total_kg.expression
    def peso_total_kg(cls):
        return (
            select(func.coalesce(func.sum(Destino.peso_kg), 0))
            .where(Destino.orden_id == cls.id)
            .scalar_subquery()
        )

    @hybrid_property
    def volumen_total_cm3(self) -> Decimal:
        total = Decimal("0")
        for d in self.destinos:
            if d.largo_cm is not None and d.ancho_cm is not None and d.alto_cm is not None:
                total += Decimal(str(d.largo_cm)) * Decimal(str(d.ancho_cm)) * Decimal(str(d.alto_cm))
        return total


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
