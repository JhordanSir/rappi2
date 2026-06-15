from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_mongo_db, require_permiso
from core.database import get_db
from models.asignaciones import Asignacion
from models.conductores import Conductor
from models.ordenes import Orden
from models.rutas import RutaPlanificada
from schemas.mongo_tracking import GeocercaIn, GeocercaOut, GeocercaUpdate, GPSPingIn, GPSPingOut
from schemas.seguimiento import (
    AsignacionSeguimiento,
    OrdenSeguimientoResponse,
    ParadaSeguimiento,
    PosicionActual,
    PuntoGeo,
    RutaSeguimiento,
)
from services.mongo import geocerca_service, tracking_service

router = APIRouter(tags=["tracking"])


def _to_float(value) -> Optional[float]:
    return float(value) if value is not None else None


@router.post("/tracking/ping", response_model=GPSPingOut, status_code=status.HTTP_201_CREATED)
async def post_ping(
    payload: GPSPingIn,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "write")),
):
    doc = await tracking_service.crear_ping(mongo_db, payload)
    return doc


@router.get("/tracking/asignacion/{asignacion_id}", response_model=list[GPSPingOut])
async def get_tracking_asignacion(
    asignacion_id: int,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limit: int = Query(500, le=2000),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    return await tracking_service.listar_por_asignacion(mongo_db, asignacion_id, desde, hasta, limit)


@router.get("/tracking/asignacion/{asignacion_id}/ultimo", response_model=GPSPingOut)
async def get_ultimo_ping(
    asignacion_id: int,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    doc = await tracking_service.ultimo_ping(mongo_db, asignacion_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Sin pings para esta asignacion")
    return doc


@router.get("/tracking/asignacion/{asignacion_id}/estadisticas")
async def estadisticas_asignacion(
    asignacion_id: int,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Distancia total recorrida, duracion y velocidad promedio segun pings GPS."""
    return await tracking_service.estadisticas_asignacion(mongo_db, asignacion_id)


@router.get("/tracking/conductores-cerca")
async def conductores_cerca_de_punto(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    radio_m: int = Query(2000, ge=10, le=50000),
    ventana_min: int = Query(5, ge=1, le=60),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Conductores con ping reciente dentro del radio. Usa $geoNear sobre gps_tracking."""
    return await tracking_service.conductores_cerca(mongo_db, lon, lat, radio_m, ventana_min)


@router.get("/tracking/orden/{orden_id}", response_model=OrdenSeguimientoResponse)
async def seguimiento_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Vista agregada para la pantalla de trackeo: orden, asignacion activa, ultima
    posicion GPS, ruta, progreso de paradas y geocercas activas."""
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Asignacion activa: preferir la EnCurso, si no la mas reciente.
    result = await db.execute(
        select(Asignacion).where(Asignacion.orden_id == orden_id).order_by(Asignacion.id.desc())
    )
    asignaciones = result.scalars().all()
    asignacion = next(
        (a for a in asignaciones if a.estado == "EnCurso"),
        asignaciones[0] if asignaciones else None,
    )

    asignacion_out = None
    posicion = None
    estadisticas = None
    if asignacion is not None:
        conductor = await db.get(Conductor, asignacion.conductor_id)
        asignacion_out = AsignacionSeguimiento(
            id=asignacion.id,
            estado=asignacion.estado,
            conductor_id=asignacion.conductor_id,
            conductor_nombre=conductor.nombre if conductor else None,
            vehiculo_placa=asignacion.vehiculo_placa,
            fecha_inicio=asignacion.fecha_inicio,
            fecha_fin=asignacion.fecha_fin,
        )
        ultimo = await tracking_service.ultimo_ping(mongo_db, asignacion.id)
        if ultimo is not None:
            coords = ultimo["location"]["coordinates"]
            posicion = PosicionActual(
                lon=coords[0],
                lat=coords[1],
                speed_kmh=ultimo.get("speed_kmh"),
                heading=ultimo.get("heading"),
                timestamp=ultimo["timestamp"],
            )
        estadisticas = await tracking_service.estadisticas_asignacion(mongo_db, asignacion.id)

    # Ruta mas reciente de la orden + sus paradas + geocercas activas.
    result = await db.execute(
        select(RutaPlanificada)
        .options(selectinload(RutaPlanificada.paradas))
        .where(RutaPlanificada.orden_id == orden_id)
        .order_by(RutaPlanificada.id.desc())
    )
    ruta = result.scalars().first()
    ruta_out = None
    paradas_out: list[ParadaSeguimiento] = []
    geocercas: list = []
    if ruta is not None:
        ruta_out = RutaSeguimiento(
            id=ruta.id,
            distancia_km=_to_float(ruta.distancia_km),
            tiempo_estimado_segundos=ruta.tiempo_estimado.total_seconds() if ruta.tiempo_estimado is not None else None,
            geometria=ruta.geometria,
        )
        paradas_out = [
            ParadaSeguimiento(
                id=p.id,
                secuencia=p.secuencia,
                direccion=p.direccion,
                lat=_to_float(p.lat),
                lon=_to_float(p.lon),
                estado=p.estado,
                fecha_paso=p.fecha_paso,
            )
            for p in ruta.paradas
        ]
        geocercas = await geocerca_service.listar(mongo_db, ruta_id=ruta.id, activa=True)

    return OrdenSeguimientoResponse(
        orden_id=orden.id,
        estado=orden.estado,
        cliente_id=orden.cliente_id,
        origen=PuntoGeo(
            direccion=orden.direccion_origen,
            distrito=orden.distrito_origen,
            lat=_to_float(orden.lat_origen),
            lon=_to_float(orden.lon_origen),
        ),
        destino=PuntoGeo(
            direccion=orden.direccion_destino,
            distrito=orden.distrito_destino,
            lat=_to_float(orden.lat_destino),
            lon=_to_float(orden.lon_destino),
        ),
        asignacion=asignacion_out,
        posicion_actual=posicion,
        ruta=ruta_out,
        paradas=paradas_out,
        geocercas=geocercas,
        estadisticas=estadisticas,
    )


@router.post("/geocercas", response_model=GeocercaOut, status_code=status.HTTP_201_CREATED)
async def create_geocerca(
    payload: GeocercaIn,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "write")),
):
    return await geocerca_service.crear(mongo_db, payload)


@router.get("/geocercas", response_model=list[GeocercaOut])
async def list_geocercas(
    ruta_id: Optional[int] = None,
    activa: Optional[bool] = None,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    return await geocerca_service.listar(mongo_db, ruta_id, activa)


@router.get("/geocercas/contiene", response_model=list[GeocercaOut])
async def geocercas_contienen_punto(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    return await geocerca_service.contiene_punto(mongo_db, lon, lat)


@router.get("/geocercas/{geocerca_id}", response_model=GeocercaOut)
async def get_geocerca(
    geocerca_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    doc = await geocerca_service.obtener(mongo_db, geocerca_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    return doc


@router.patch("/geocercas/{geocerca_id}", response_model=GeocercaOut)
async def update_geocerca(
    geocerca_id: str,
    payload: GeocercaUpdate,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "write")),
):
    doc = await geocerca_service.actualizar(mongo_db, geocerca_id, payload.model_dump(exclude_unset=True))
    if doc is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    return doc


@router.delete("/geocercas/{geocerca_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desactivar_geocerca(
    geocerca_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "delete")),
):
    ok = await geocerca_service.desactivar(mongo_db, geocerca_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
