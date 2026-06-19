from sqlalchemy import Column, DateTime, Integer, JSON, Numeric, String, func

from core.database import Base


class TarifaConfig(Base):
    """Configuración de tarifa editable por el admin. Una sola fila vigente (id=1).

    El precio de un tramo recojo→entrega se calcula como:
        subtotal = tarifa_base + precio_km*km + precio_min*min + precio_kg*peso_cobrable
        peso_cobrable = max(peso_real, volumen_cm3 / factor_volumetrico)
        precio = max(minimo, subtotal * mult_servicio * (1 + recargos_horario))
    Los recargos de horario (nocturno / hora pico / fin de semana) se suman en porcentaje.
    """
    __tablename__ = "tarifa_config"

    id = Column(Integer, primary_key=True)
    moneda = Column(String(8), default="PEN", nullable=False)

    # Componentes base de la tarifa.
    tarifa_base = Column(Numeric(10, 2), default=5.00, nullable=False)
    precio_km = Column(Numeric(10, 2), default=1.20, nullable=False)
    precio_min = Column(Numeric(10, 2), default=0.30, nullable=False)
    precio_kg = Column(Numeric(10, 2), default=0.50, nullable=False)
    # Divisor del peso volumétrico (cm³ por kg). 5000 es el estándar de paquetería.
    factor_volumetrico = Column(Integer, default=5000, nullable=False)
    minimo = Column(Numeric(10, 2), default=6.00, nullable=False)

    # Multiplicadores por nivel de servicio.
    mult_estandar = Column(Numeric(5, 2), default=1.00, nullable=False)
    mult_express = Column(Numeric(5, 2), default=1.50, nullable=False)
    mult_urgente = Column(Numeric(5, 2), default=2.00, nullable=False)

    # Recargos por horario (porcentaje, p.ej. 0.20 = +20%).
    recargo_nocturno_pct = Column(Numeric(5, 2), default=0.20, nullable=False)
    nocturno_desde = Column(Integer, default=22, nullable=False)  # hora local (0-23)
    nocturno_hasta = Column(Integer, default=6, nullable=False)

    recargo_pico_pct = Column(Numeric(5, 2), default=0.15, nullable=False)
    # Ventanas de hora pico como lista de [inicio, fin] en horas locales.
    pico_ventanas = Column(JSON, default=lambda: [[7, 9], [18, 20]], nullable=False)

    recargo_finde_pct = Column(Numeric(5, 2), default=0.10, nullable=False)

    actualizado_en = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
