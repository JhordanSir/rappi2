from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from models.ordenes import Orden, Pago
from schemas.pagos import PagoCreate, PagoResponse, PagoUpdate

router = APIRouter(tags=["pagos"])


@router.get("/pagos", response_model=list[PagoResponse])
async def list_pagos(
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "read")),
):
    stmt = select(Pago)
    if estado is not None:
        stmt = stmt.where(Pago.estado == estado)
    if desde is not None:
        stmt = stmt.where(Pago.fecha_pago >= desde)
    if hasta is not None:
        stmt = stmt.where(Pago.fecha_pago <= hasta)
    stmt = stmt.order_by(Pago.fecha_pago.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/ordenes/{orden_id}/pagos", response_model=PagoResponse, status_code=status.HTTP_201_CREATED)
async def create_pago(
    orden_id: int,
    payload: PagoCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    pago = Pago(orden_id=orden_id, **payload.model_dump())
    db.add(pago)
    await db.commit()
    await db.refresh(pago)
    return pago


@router.get("/ordenes/{orden_id}/pagos", response_model=list[PagoResponse])
async def list_pagos_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "read")),
):
    result = await db.execute(select(Pago).where(Pago.orden_id == orden_id).order_by(Pago.fecha_pago.desc()))
    return result.scalars().all()


@router.get("/pagos/{pago_id}", response_model=PagoResponse)
async def get_pago(
    pago_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "read")),
):
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago


@router.patch("/pagos/{pago_id}", response_model=PagoResponse)
async def update_pago(
    pago_id: int,
    payload: PagoUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "write")),
):
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(pago, k, v)
    await db.commit()
    await db.refresh(pago)
    return pago


@router.delete("/pagos/{pago_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pago(
    pago_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("pagos", "delete")),
):
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    await db.delete(pago)
    await db.commit()
