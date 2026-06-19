from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import UserScope, get_scope, orden_en_alcance, require_permiso
from core.database import get_db
from core.realtime import canal_conductor, publish
from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.ordenes import Orden
from schemas.calificaciones import CalificacionCreate, CalificacionResponse, ConductorRating

router = APIRouter(tags=["calificaciones"])


@router.post(
    "/ordenes/{orden_id}/calificacion",
    response_model=CalificacionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def calificar_orden(
    orden_id: int,
    payload: CalificacionCreate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("calificaciones", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != "Entregado":
        raise HTTPException(status_code=400, detail="Solo se puede calificar una orden entregada")
    ya = (await db.execute(select(Calificacion).where(Calificacion.orden_id == orden_id))).scalar_one_or_none()
    if ya is not None:
        raise HTTPException(status_code=400, detail="Esta orden ya fue calificada")

    # Conductor a calificar: el de la asignación finalizada (o la más reciente).
    asignaciones = (
        await db.execute(select(Asignacion).where(Asignacion.orden_id == orden_id).order_by(Asignacion.id.desc()))
    ).scalars().all()
    asignacion = next((a for a in asignaciones if a.estado == "Finalizada"), asignaciones[0] if asignaciones else None)
    conductor_id = asignacion.conductor_id if asignacion is not None else None

    cal = Calificacion(
        orden_id=orden_id,
        conductor_id=conductor_id,
        cliente_id=orden.cliente_id,
        puntaje=payload.puntaje,
        comentario=payload.comentario,
    )
    db.add(cal)
    await db.commit()
    await db.refresh(cal)
    if conductor_id is not None:
        await publish(canal_conductor(conductor_id), {"tipo": "calificacion", "orden_id": orden_id, "puntaje": cal.puntaje})
    return cal


@router.get("/ordenes/{orden_id}/calificacion", response_model=CalificacionResponse)
async def get_calificacion(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("calificaciones", "read")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    cal = (await db.execute(select(Calificacion).where(Calificacion.orden_id == orden_id))).scalar_one_or_none()
    if cal is None:
        raise HTTPException(status_code=404, detail="La orden aún no tiene calificación")
    return cal


@router.get("/conductores/{conductor_id}/calificaciones", response_model=ConductorRating)
async def rating_conductor(
    conductor_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("calificaciones", "read")),
):
    promedio, total = (
        await db.execute(
            select(func.avg(Calificacion.puntaje), func.count(Calificacion.id)).where(
                Calificacion.conductor_id == conductor_id
            )
        )
    ).one()
    return ConductorRating(
        conductor_id=conductor_id,
        promedio=round(float(promedio), 2) if promedio is not None else None,
        total=total or 0,
    )
