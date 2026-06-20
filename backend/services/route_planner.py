"""Generación de rutas por calles (OSRM) reutilizable por la creación de órdenes
y por el endpoint manual /rutas/planificar."""
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from models.destinos import Destino
from models.ordenes import Orden
from models.rutas import Parada, RutaPlanificada
from services.mongo import geocerca_service
from services.osrm_service import osrm_service

logger = logging.getLogger(__name__)


async def _destinos_de(db: AsyncSession, orden_id: int) -> list[Destino]:
    return list(
        (await db.execute(select(Destino).where(Destino.orden_id == orden_id).order_by(Destino.secuencia)))
        .scalars().all()
    )


async def _crear_ruta_desde_stops(
    db: AsyncSession,
    primary_orden_id: int,
    stops: list[dict],
    orden_ids: list[int],
    mongo_db=None,
    generar_geocerca: bool = True,
    tolerancia_metros: int = 80,
) -> RutaPlanificada | None:
    """Crea una única RutaPlanificada multiparada a partir de `stops` (el primero es el
    origen/recojo principal, fijado como source). Optimiza la secuencia con OSRM y
    reemplaza cualquier ruta previa de las órdenes involucradas.

    stops: dicts con {orden_id, destino_id|None, direccion, distrito, lon, lat, estado}.
    """
    puntos = [(s["lon"], s["lat"]) for s in stops]
    if len(puntos) < 2:
        return None

    if len(puntos) >= 3:
        res = await osrm_service.optimize_trip(puntos, roundtrip=False)
        geometry, distancia_km, tiempo_seg = res["geometry"], res["distancia_km"], res["tiempo_segundos"]
        # El source (índice 0) debe quedar primero; conservamos ese orden óptimo.
        stops = [stops[i] for i in res["orden"]]
    else:
        res = await osrm_service.get_route_multi(puntos)
        geometry, distancia_km, tiempo_seg = res["geometry"], res["distancia_km"], res["tiempo_segundos"]

    # Reemplaza rutas previas de todas las órdenes involucradas (evita rutas huérfanas).
    previas = (
        await db.execute(select(RutaPlanificada).where(RutaPlanificada.orden_id.in_(orden_ids)))
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
        orden_id=primary_orden_id,
        distancia_km=round(distancia_km, 2),
        tiempo_estimado=timedelta(seconds=tiempo_seg),
        geometria=geometry,
    )
    for i, s in enumerate(stops):
        ruta.paradas.append(Parada(
            orden_id=s.get("orden_id"),
            destino_id=s.get("destino_id"),
            direccion=s["direccion"],
            distrito=s.get("distrito"),
            lat=s["lat"], lon=s["lon"],
            secuencia=i + 1,
            estado=s.get("estado", "Pendiente"),
        ))
    db.add(ruta)
    await db.commit()
    await db.refresh(ruta)

    if generar_geocerca and mongo_db is not None:
        try:
            poly = corredor_polygon(geometry["coordinates"], tolerancia_metros)
            await geocerca_service.crear_desde_geometry(
                mongo_db, ruta_id=ruta.id, orden_id=primary_orden_id,
                geometry={"type": "Polygon", "coordinates": [poly]},
                tolerance_m=tolerancia_metros, tipo="ruta_buffer",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo crear geocerca de corredor para ruta %s: %s", ruta.id, exc)
    return ruta


def _stops_de_orden(orden: Orden, destinos: list[Destino], incluir_recojo: bool = True) -> list[dict]:
    """Construye las paradas de una orden: su recojo + una entrega por destino."""
    stops: list[dict] = []
    if incluir_recojo and orden.lon_origen is not None and orden.lat_origen is not None:
        stops.append({
            "orden_id": orden.id, "destino_id": None,
            "direccion": orden.direccion_origen, "distrito": orden.distrito_origen,
            "lon": float(orden.lon_origen), "lat": float(orden.lat_origen),
            "estado": "Visitada",  # el recojo se considera cumplido al iniciar
        })
    for d in destinos:
        if d.lon is None or d.lat is None:
            continue
        stops.append({
            "orden_id": orden.id, "destino_id": d.id,
            "direccion": d.direccion, "distrito": d.distrito,
            "lon": float(d.lon), "lat": float(d.lat),
            "estado": "Visitada" if d.estado == "Entregado" else "Pendiente",
        })
    return stops


async def generar_ruta_orden(
    db: AsyncSession, orden: Orden, mongo_db=None,
    generar_geocerca: bool = True, tolerancia_metros: int = 80,
) -> RutaPlanificada | None:
    """Genera/replanifica la ruta de UNA orden sobre su origen + todos sus destinos."""
    destinos = await _destinos_de(db, orden.id)
    stops = _stops_de_orden(orden, destinos)
    return await _crear_ruta_desde_stops(
        db, orden.id, stops, [orden.id], mongo_db=mongo_db,
        generar_geocerca=generar_geocerca, tolerancia_metros=tolerancia_metros,
    )


async def generar_run(
    db: AsyncSession, primary_orden: Orden, ordenes: list[Orden], mongo_db=None,
    generar_geocerca: bool = True, tolerancia_metros: int = 80,
) -> RutaPlanificada | None:
    """Genera UNA ruta consolidada que agrupa varias órdenes (recojos + entregas)."""
    stops: list[dict] = []
    # La orden principal primero (su recojo es el source de la optimización).
    ordenadas = [primary_orden] + [o for o in ordenes if o.id != primary_orden.id]
    orden_ids = [o.id for o in ordenadas]
    for o in ordenadas:
        destinos = await _destinos_de(db, o.id)
        stops += _stops_de_orden(o, destinos)
    return await _crear_ruta_desde_stops(
        db, primary_orden.id, stops, orden_ids, mongo_db=mongo_db,
        generar_geocerca=generar_geocerca, tolerancia_metros=tolerancia_metros,
    )


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
    interrumpe la creación). Construye el recorrido sobre el origen + todos los destinos."""
    if not getattr(settings, "RUTA_AUTOGENERAR", True):
        return None
    if orden.lat_origen is None or orden.lon_origen is None:
        logger.info("Orden %s sin coordenadas de origen; se omite ruta automática.", orden.id)
        return None
    try:
        return await generar_ruta_orden(db, orden, mongo_db=mongo_db)
    except Exception as exc:
        logger.warning("Ruta automática falló para orden %s: %s", orden.id, exc)
        await db.rollback()
        return None
