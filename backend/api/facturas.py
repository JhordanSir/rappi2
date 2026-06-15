from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from models.ordenes import Factura, Orden
from schemas.facturas import FacturaCreate, FacturaResponse, FacturaUpdate

router = APIRouter(tags=["facturas"])


@router.get("/facturas", response_model=list[FacturaResponse])
async def list_facturas(
    skip: int = 0,
    limit: int = Query(50, le=200),
    ruc: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    stmt = select(Factura)
    if ruc is not None:
        stmt = stmt.where(Factura.ruc == ruc)
    if desde is not None:
        stmt = stmt.where(Factura.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(Factura.fecha <= hasta)
    stmt = stmt.order_by(Factura.fecha.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/facturas/{factura_id}", response_model=FacturaResponse)
async def update_factura(
    factura_id: int,
    payload: FacturaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "write")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(factura, k, v)
    await db.commit()
    await db.refresh(factura)
    return factura


@router.post("/ordenes/{orden_id}/facturas", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def create_factura(
    orden_id: int,
    payload: FacturaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    factura = Factura(orden_id=orden_id, **payload.model_dump())
    db.add(factura)
    await db.commit()
    await db.refresh(factura)
    return factura


@router.get("/ordenes/{orden_id}/facturas", response_model=list[FacturaResponse])
async def list_facturas_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    result = await db.execute(select(Factura).where(Factura.orden_id == orden_id).order_by(Factura.fecha.desc()))
    return result.scalars().all()


@router.get("/facturas/{factura_id}", response_model=FacturaResponse)
async def get_factura(
    factura_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return factura


@router.delete("/facturas/{factura_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_factura(
    factura_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "delete")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    await db.delete(factura)
    await db.commit()
