from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_mongo_db, require_permiso
from core.database import get_db
from models.ordenes import Orden
from models.rutas import Parada, RutaPlanificada
from schemas.rutas import (
    ParadaCreate,
    ParadaResponse,
    ParadaUpdate,
    ParadaVisitarRequest,
    PlanificarRutaRequest,
    RutaCreate,
    RutaResponse,
    RutaUpdate,
)
from services.geocoding import resolver_coords
from services.mongo import geocerca_service
from services.route_planner import generar_ruta_para_orden

router = APIRouter(prefix="/rutas", tags=["rutas"])


@router.get("/", response_model=list[RutaResponse])
async def list_rutas(
    orden_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "read")),
):
    stmt = select(RutaPlanificada).options(selectinload(RutaPlanificada.paradas))
    if orden_id is not None:
        stmt = stmt.where(RutaPlanificada.orden_id == orden_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=RutaResponse, status_code=status.HTTP_201_CREATED)
async def create_ruta(
    payload: RutaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    orden = await db.get(Orden, payload.orden_id)
    if orden is None:
        raise HTTPException(status_code=400, detail="orden_id invalido")
    ruta = RutaPlanificada(
        orden_id=payload.orden_id,
        distancia_km=payload.distancia_km,
        tiempo_estimado=payload.tiempo_estimado,
    )
    for parada_in in payload.paradas:
        ruta.paradas.append(Parada(**parada_in.model_dump()))
    db.add(ruta)
    await db.commit()
    result = await db.execute(
        select(RutaPlanificada).options(selectinload(RutaPlanificada.paradas)).where(RutaPlanificada.id == ruta.id)
    )
    return result.scalar_one()


@router.post("/planificar", response_model=RutaResponse, status_code=status.HTTP_201_CREATED)
async def planificar_ruta(
    payload: PlanificarRutaRequest,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    orden = await db.get(Orden, payload.orden_id)
    if orden is None:
        raise HTTPException(status_code=400, detail="orden_id invalido")

    def _coord(payload_val, orden_val):
        if payload_val is not None:
            return payload_val
        return float(orden_val) if orden_val is not None else None

    origen_lon = _coord(payload.origen_lon, orden.lon_origen)
    origen_lat = _coord(payload.origen_lat, orden.lat_origen)
    destino_lon = _coord(payload.destino_lon, orden.lon_destino)
    destino_lat = _coord(payload.destino_lat, orden.lat_destino)

    if None in (origen_lon, origen_lat, destino_lon, destino_lat):
        raise HTTPException(
            status_code=400,
            detail="Faltan coordenadas: envialas en el request o registra lat/lon de origen y destino en la orden",
        )

    try:
        ruta = await generar_ruta_para_orden(
            db, orden,
            origen_lon, origen_lat, destino_lon, destino_lat,
            mongo_db=mongo_db,
            generar_geocerca=payload.generar_geocerca,
            tolerancia_metros=payload.tolerancia_metros,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error generando ruta: {exc}")

    result = await db.execute(
        select(RutaPlanificada).options(selectinload(RutaPlanificada.paradas)).where(RutaPlanificada.id == ruta.id)
    )
    return result.scalar_one()


@router.get("/{ruta_id}", response_model=RutaResponse)
async def get_ruta(
    ruta_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "read")),
):
    result = await db.execute(
        select(RutaPlanificada).options(selectinload(RutaPlanificada.paradas)).where(RutaPlanificada.id == ruta_id)
    )
    ruta = result.scalar_one_or_none()
    if ruta is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return ruta


@router.patch("/{ruta_id}", response_model=RutaResponse)
async def update_ruta(
    ruta_id: int,
    payload: RutaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    ruta = await db.get(RutaPlanificada, ruta_id)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(ruta, k, v)
    await db.commit()
    result = await db.execute(
        select(RutaPlanificada).options(selectinload(RutaPlanificada.paradas)).where(RutaPlanificada.id == ruta.id)
    )
    return result.scalar_one()


@router.delete("/{ruta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ruta(
    ruta_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("rutas", "delete")),
):
    ruta = await db.get(RutaPlanificada, ruta_id)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    await geocerca_service.eliminar_por_ruta(mongo_db, ruta_id)
    await db.delete(ruta)
    await db.commit()


@router.get("/{ruta_id}/paradas", response_model=list[ParadaResponse])
async def list_paradas(
    ruta_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "read")),
):
    ruta = await db.get(RutaPlanificada, ruta_id)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    result = await db.execute(
        select(Parada).where(Parada.ruta_id == ruta_id).order_by(Parada.secuencia)
    )
    return result.scalars().all()


@router.get("/{ruta_id}/paradas/{parada_id}", response_model=ParadaResponse)
async def get_parada(
    ruta_id: int,
    parada_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "read")),
):
    parada = await db.get(Parada, parada_id)
    if parada is None or parada.ruta_id != ruta_id:
        raise HTTPException(status_code=404, detail="Parada no encontrada")
    return parada


@router.post("/{ruta_id}/paradas", response_model=ParadaResponse, status_code=status.HTTP_201_CREATED)
async def add_parada(
    ruta_id: int,
    payload: ParadaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    ruta = await db.get(RutaPlanificada, ruta_id)
    if ruta is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    data = payload.model_dump()
    data["lat"], data["lon"] = await resolver_coords(data.get("direccion"), data.get("lat"), data.get("lon"))
    parada = Parada(ruta_id=ruta_id, **data)
    db.add(parada)
    await db.commit()
    await db.refresh(parada)
    return parada


@router.patch("/{ruta_id}/paradas/{parada_id}", response_model=ParadaResponse)
async def update_parada(
    ruta_id: int,
    parada_id: int,
    payload: ParadaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    parada = await db.get(Parada, parada_id)
    if parada is None or parada.ruta_id != ruta_id:
        raise HTTPException(status_code=404, detail="Parada no encontrada")
    update = payload.model_dump(exclude_unset=True)
    if "direccion" in update and update.get("lat") is None and update.get("lon") is None:
        update["lat"], update["lon"] = await resolver_coords(update["direccion"], None, None)
    for k, v in update.items():
        setattr(parada, k, v)
    await db.commit()
    await db.refresh(parada)
    return parada


@router.patch("/{ruta_id}/paradas/{parada_id}/visitar", response_model=ParadaResponse)
async def visitar_parada(
    ruta_id: int,
    parada_id: int,
    payload: ParadaVisitarRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    """Marca una parada como visitada, con la fecha y las coordenadas reales del momento."""
    parada = await db.get(Parada, parada_id)
    if parada is None or parada.ruta_id != ruta_id:
        raise HTTPException(status_code=404, detail="Parada no encontrada")
    parada.estado = "Visitada"
    parada.fecha_paso = datetime.now(timezone.utc)
    if payload.lat is not None:
        parada.lat = payload.lat
    if payload.lon is not None:
        parada.lon = payload.lon
    await db.commit()
    await db.refresh(parada)
    return parada


@router.delete("/{ruta_id}/paradas/{parada_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parada(
    ruta_id: int,
    parada_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("rutas", "write")),
):
    parada = await db.get(Parada, parada_id)
    if parada is None or parada.ruta_id != ruta_id:
        raise HTTPException(status_code=404, detail="Parada no encontrada")
    await db.delete(parada)
    await db.commit()
