"""Cálculo de precio del envío (server-side). El cliente nunca fija el precio.

Una orden/tramo recojo→entrega se tarifa como:
    peso_cobrable = max(peso_real, volumen_cm3 / factor_volumetrico)
    subtotal = tarifa_base + precio_km*km + precio_min*min + precio_kg*peso_cobrable
    precio   = max(minimo, subtotal * mult_servicio * (1 + recargo_horario))
El recargo_horario suma los porcentajes aplicables (nocturno + hora pico + fin de semana)
según el momento del envío (programado o el actual).
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from models.tarifa import TarifaConfig
from services.osrm_service import osrm_service

# Arequipa/Perú no observa horario de verano: offset fijo. Sirve para evaluar los
# recargos por horario sobre la hora local del envío.
ZONA_LOCAL = ZoneInfo("America/Lima")

_MULT_POR_NIVEL = {
    "estandar": "mult_estandar",
    "express": "mult_express",
    "urgente": "mult_urgente",
}


async def obtener_tarifa(db: AsyncSession) -> TarifaConfig:
    """Devuelve la fila de tarifa vigente (id=1), creándola con defaults si falta."""
    tarifa = await db.get(TarifaConfig, 1)
    if tarifa is None:
        tarifa = TarifaConfig(id=1)
        db.add(tarifa)
        await db.commit()
        await db.refresh(tarifa)
    return tarifa


def _q2(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def peso_cobrable(
    tarifa: TarifaConfig,
    peso_kg: Optional[float],
    largo_cm: Optional[float],
    ancho_cm: Optional[float],
    alto_cm: Optional[float],
) -> Decimal:
    real = Decimal(str(peso_kg or 0))
    if largo_cm and ancho_cm and alto_cm and tarifa.factor_volumetrico:
        volumen = Decimal(str(largo_cm)) * Decimal(str(ancho_cm)) * Decimal(str(alto_cm))
        volumetrico = volumen / Decimal(tarifa.factor_volumetrico)
        return max(real, volumetrico)
    return real


def recargo_horario(tarifa: TarifaConfig, cuando: datetime) -> Decimal:
    """Fracción de recargo (p.ej. 0.30 = +30%) según hora local y día."""
    if cuando.tzinfo is None:
        cuando = cuando.replace(tzinfo=timezone.utc)
    local = cuando.astimezone(ZONA_LOCAL)
    hora = local.hour
    recargo = Decimal("0")

    # Nocturno: la ventana puede cruzar la medianoche (p.ej. 22→6).
    desde, hasta = tarifa.nocturno_desde, tarifa.nocturno_hasta
    es_nocturno = (desde <= hora or hora < hasta) if desde > hasta else (desde <= hora < hasta)
    if es_nocturno:
        recargo += Decimal(str(tarifa.recargo_nocturno_pct))

    # Hora pico: cualquiera de las ventanas configuradas.
    for ventana in (tarifa.pico_ventanas or []):
        if len(ventana) == 2 and ventana[0] <= hora < ventana[1]:
            recargo += Decimal(str(tarifa.recargo_pico_pct))
            break

    # Fin de semana (sábado=5, domingo=6).
    if local.weekday() >= 5:
        recargo += Decimal(str(tarifa.recargo_finde_pct))

    return recargo


def precio_tramo(
    tarifa: TarifaConfig,
    distancia_km: float,
    tiempo_min: float,
    peso_kg: Optional[float] = None,
    largo_cm: Optional[float] = None,
    ancho_cm: Optional[float] = None,
    alto_cm: Optional[float] = None,
    nivel_servicio: str = "estandar",
    cuando: Optional[datetime] = None,
) -> dict:
    """Calcula el precio de un tramo y devuelve el desglose."""
    cuando = cuando or datetime.now(timezone.utc)
    cobrable = peso_cobrable(tarifa, peso_kg, largo_cm, ancho_cm, alto_cm)

    base = Decimal(str(tarifa.tarifa_base))
    por_dist = Decimal(str(tarifa.precio_km)) * Decimal(str(distancia_km))
    por_tiempo = Decimal(str(tarifa.precio_min)) * Decimal(str(tiempo_min))
    por_peso = Decimal(str(tarifa.precio_kg)) * cobrable
    subtotal = base + por_dist + por_tiempo + por_peso

    mult_attr = _MULT_POR_NIVEL.get(nivel_servicio, "mult_estandar")
    mult = Decimal(str(getattr(tarifa, mult_attr)))
    recargo = recargo_horario(tarifa, cuando)

    bruto = subtotal * mult * (Decimal("1") + recargo)
    total = max(Decimal(str(tarifa.minimo)), bruto)

    return {
        "distancia_km": round(float(distancia_km), 2),
        "tiempo_min": round(float(tiempo_min), 1),
        "peso_cobrable_kg": float(_q2(cobrable)),
        "subtotal": float(_q2(subtotal)),
        "multiplicador_servicio": float(mult),
        "recargo_horario_pct": float(recargo),
        "total": float(_q2(total)),
        "moneda": tarifa.moneda,
    }


async def cotizar_tramo(
    db: AsyncSession,
    origen_lon: float,
    origen_lat: float,
    destino_lon: float,
    destino_lat: float,
    peso_kg: Optional[float] = None,
    largo_cm: Optional[float] = None,
    ancho_cm: Optional[float] = None,
    alto_cm: Optional[float] = None,
    nivel_servicio: str = "estandar",
    cuando: Optional[datetime] = None,
) -> dict:
    """Cotiza un tramo consultando la distancia/tiempo reales por calles (OSRM)."""
    tarifa = await obtener_tarifa(db)
    ruta = await osrm_service.get_route(origen_lon, origen_lat, destino_lon, destino_lat)
    return precio_tramo(
        tarifa,
        distancia_km=ruta["distancia_km"],
        tiempo_min=ruta["tiempo_segundos"] / 60.0,
        peso_kg=peso_kg,
        largo_cm=largo_cm,
        ancho_cm=ancho_cm,
        alto_cm=alto_cm,
        nivel_servicio=nivel_servicio,
        cuando=cuando,
    )
