from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import get_mongo_db, require_permiso
from schemas.mongo_tracking import GeocercaIn, GeocercaOut, GeocercaUpdate, GPSPingIn, GPSPingOut
from services.mongo import geocerca_service, tracking_service

router = APIRouter(tags=["tracking"])


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
