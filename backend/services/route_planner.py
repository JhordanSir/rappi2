"""Generación de rutas por calles (OSRM) reutilizable por la creación de órdenes
y por el endpoint manual /rutas/planificar."""
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from models.ordenes import Orden
from models.rutas import Parada, RutaPlanificada
from services.mongo import geocerca_service
from services.osrm_service import osrm_service

logger = logging.getLogger(__name__)


def corredor_polygon(coords, tol_m: int):
    """Polígono (bounding box con margen) que envuelve el recorrido para usarlo como
    geocerca de corredor. coords = lista de [lon, lat]."""
    pad = max(tol_m / 111000.0, 0.0035)
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    minlon, maxlon = min(lons) - pad, max(lons) + pad
    minlat, maxlat = min(lats) - pad, max(lats) + pad
    return [[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]


async def generar_ruta_para_orden(
    db: AsyncSession,
    orden: Orden,
    origen_lon: float,
    origen_lat: float,
    destino_lon: float,
    destino_lat: float,
    mongo_db=None,
    generar_geocerca: bool = True,
    tolerancia_metros: int = 80,
) -> RutaPlanificada:
    """Crea una RutaPlanificada con paradas (origen/destino) y, opcionalmente, una
    geocerca de corredor. La distancia/tiempo provienen de OSRM. Puede lanzar si
    OSRM falla (antes de tocar la BD)."""
    data = await osrm_service.get_route(origen_lon, origen_lat, destino_lon, destino_lat)

    # Replanificar reemplaza la ruta previa de la orden en vez de acumular rutas
    # huérfanas: el seguimiento siempre apunta a una única ruta vigente.
    previas = (
        await db.execute(select(RutaPlanificada).where(RutaPlanificada.orden_id == orden.id))
    ).scalars().all()
    for previa in previas:
        if mongo_db is not None:
            try:
                await geocerca_service.eliminar_por_ruta(mongo_db, previa.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo eliminar geocerca de ruta previa %s: %s", previa.id, exc)
        await db.delete(previa)
    if previas:
        await db.flush()

    ruta = RutaPlanificada(
        orden_id=orden.id,
        distancia_km=round(data["distancia_km"], 2),
        tiempo_estimado=timedelta(seconds=data["tiempo_segundos"]),
        geometria=data["geometry"],  # GeoJSON LineString por calles
    )
    ruta.paradas.append(Parada(orden_id=orden.id, direccion=orden.direccion_origen, distrito=orden.distrito_origen, lat=origen_lat, lon=origen_lon, secuencia=1, estado="Pendiente"))
    ruta.paradas.append(Parada(orden_id=orden.id, direccion=orden.direccion_destino, distrito=orden.distrito_destino, lat=destino_lat, lon=destino_lon, secuencia=2, estado="Pendiente"))
    db.add(ruta)
    await db.commit()
    await db.refresh(ruta)

    if generar_geocerca and mongo_db is not None:
        try:
            poly = corredor_polygon(data["geometry"]["coordinates"], tolerancia_metros)
            await geocerca_service.crear_desde_geometry(
                mongo_db, ruta_id=ruta.id, orden_id=orden.id,
                geometry={"type": "Polygon", "coordinates": [poly]},
                tolerance_m=tolerancia_metros, tipo="ruta_buffer",
            )
        except Exception as exc:
            logger.warning("No se pudo crear geocerca de corredor para ruta %s: %s", ruta.id, exc)

    return ruta


async def aplicar_secuencia(
    db: AsyncSession,
    ruta: RutaPlanificada,
    paradas_ordenadas: list[Parada],
    mongo_db=None,
    tolerancia_metros: int = 80,
) -> RutaPlanificada:
    """Reasigna la secuencia de las paradas en el orden dado, recalcula la geometría
    por calles a lo largo de ellas y regenera la geocerca de corredor."""
    puntos = [
        (float(p.lon), float(p.lat))
        for p in paradas_ordenadas
        if p.lon is not None and p.lat is not None
    ]
    if len(puntos) >= 2:
        data = await osrm_service.get_route_multi(puntos)
        ruta.geometria = data["geometry"]
        ruta.distancia_km = round(data["distancia_km"], 2)
        ruta.tiempo_estimado = timedelta(seconds=data["tiempo_segundos"])

    # La secuencia es única por ruta: primero la liberamos a negativos para evitar
    # choques con la constraint, luego asignamos 1..N en el nuevo orden.
    for i, p in enumerate(paradas_ordenadas):
        p.secuencia = -(i + 1)
    await db.flush()
    for i, p in enumerate(paradas_ordenadas):
        p.secuencia = i + 1
    await db.commit()
    await db.refresh(ruta)

    if mongo_db is not None and ruta.geometria:
        try:
            await geocerca_service.eliminar_por_ruta(mongo_db, ruta.id)
            poly = corredor_polygon(ruta.geometria["coordinates"], tolerancia_metros)
            await geocerca_service.crear_desde_geometry(
                mongo_db, ruta_id=ruta.id, orden_id=ruta.orden_id,
                geometry={"type": "Polygon", "coordinates": [poly]},
                tolerance_m=tolerancia_metros, tipo="ruta_buffer",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo regenerar geocerca de corredor para ruta %s: %s", ruta.id, exc)
    return ruta


async def optimizar_ruta(db: AsyncSession, ruta: RutaPlanificada, mongo_db=None) -> RutaPlanificada:
    """Optimiza el orden de visita de las paradas (OSRM trip), fijando la primera
    (el recojo) como origen, y aplica la nueva secuencia."""
    paradas = sorted(ruta.paradas, key=lambda p: p.secuencia)
    visitables = [p for p in paradas if p.lon is not None and p.lat is not None]
    if len(visitables) < 3:
        # Con origen + 1 destino no hay nada que optimizar; solo recalcula geometría.
        return await aplicar_secuencia(db, ruta, paradas, mongo_db=mongo_db)
    puntos = [(float(p.lon), float(p.lat)) for p in visitables]
    resultado = await osrm_service.optimize_trip(puntos, roundtrip=False)
    nuevo_orden = [visitables[i] for i in resultado["orden"]]
    return await aplicar_secuencia(db, ruta, nuevo_orden, mongo_db=mongo_db)


async def autogenerar_ruta(db: AsyncSession, orden: Orden, mongo_db=None) -> Optional[RutaPlanificada]:
    """Genera la ruta automáticamente al crear una orden (best-effort: nunca
    interrumpe la creación). Requiere que la orden tenga coordenadas."""
    if not getattr(settings, "RUTA_AUTOGENERAR", True):
        return None
    if None in (orden.lat_origen, orden.lon_origen, orden.lat_destino, orden.lon_destino):
        logger.info("Orden %s sin coordenadas; se omite ruta automática.", orden.id)
        return None
    try:
        return await generar_ruta_para_orden(
            db, orden,
            float(orden.lon_origen), float(orden.lat_origen),
            float(orden.lon_destino), float(orden.lat_destino),
            mongo_db=mongo_db,
        )
    except Exception as exc:
        logger.warning("Ruta automática falló para orden %s: %s", orden.id, exc)
        await db.rollback()
        return None
