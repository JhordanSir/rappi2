from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_mongo_db, require_permiso
from core.database import get_db
from models.asignaciones import Asignacion
from models.conductores import Conductor
from models.ordenes import Orden
from models.vehiculos import Vehiculo
from schemas.asignaciones import AsignacionCreate, AsignacionResponse, AsignacionUpdate
from services.mongo import tracking_service, geocerca_service

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


@router.get("/", response_model=list[AsignacionResponse])
async def list_asignaciones(
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    conductor_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    stmt = select(Asignacion)
    if estado is not None:
        stmt = stmt.where(Asignacion.estado == estado)
    if conductor_id is not None:
        stmt = stmt.where(Asignacion.conductor_id == conductor_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(
    payload: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    orden = await db.get(Orden, payload.orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != "Pendiente":
        raise HTTPException(status_code=400, detail=f"Orden no esta Pendiente (estado actual: {orden.estado})")

    conductor = await db.get(Conductor, payload.conductor_id)
    if conductor is None or not conductor.activo:
        raise HTTPException(status_code=400, detail="Conductor invalido o inactivo")
    if conductor.disponibilidad != "Disponible":
        raise HTTPException(status_code=400, detail=f"Conductor no disponible (actual: {conductor.disponibilidad})")

    vehiculo = await db.get(Vehiculo, payload.vehiculo_placa)
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status_code=400, detail="Vehiculo invalido o inactivo")
    if vehiculo.estado != "Operativo":
        raise HTTPException(status_code=400, detail=f"Vehiculo no operativo (actual: {vehiculo.estado})")

    asignacion = Asignacion(**payload.model_dump(), estado="Asignada")
    db.add(asignacion)
    orden.estado = "En Proceso"
    conductor.disponibilidad = "Ocupado"
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.get("/{asignacion_id}", response_model=AsignacionResponse)
async def get_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return asignacion


@router.patch("/{asignacion_id}", response_model=AsignacionResponse)
async def update_asignacion(
    asignacion_id: int,
    payload: AsignacionUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(asignacion, k, v)
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.patch("/{asignacion_id}/iniciar", response_model=AsignacionResponse)
async def iniciar_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Asignada":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta Asignada (actual: {asignacion.estado})")
    orden = await db.get(Orden, asignacion.orden_id)
    asignacion.estado = "EnCurso"
    asignacion.fecha_inicio = datetime.now(timezone.utc)
    if orden is not None:
        orden.estado = "En Tránsito"
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.patch("/{asignacion_id}/finalizar", response_model=AsignacionResponse)
async def finalizar_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    orden = await db.get(Orden, asignacion.orden_id)
    conductor = await db.get(Conductor, asignacion.conductor_id)
    asignacion.estado = "Finalizada"
    asignacion.fecha_fin = datetime.now(timezone.utc)
    if orden is not None:
        orden.estado = "Entregado"
    if conductor is not None:
        conductor.disponibilidad = "Disponible"
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.delete("/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "delete")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado == "EnCurso":
        raise HTTPException(status_code=400, detail="No se puede borrar una asignacion en curso")
    await tracking_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await geocerca_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await db.delete(asignacion)
    await db.commit()
