from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from models.vehiculos import Vehiculo
from schemas.vehiculos import VehiculoCreate, VehiculoResponse, VehiculoUpdate

router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])


@router.get("/", response_model=list[VehiculoResponse])
async def list_vehiculos(
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    estado: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "read")),
):
    stmt = select(Vehiculo)
    if activo is not None:
        stmt = stmt.where(Vehiculo.activo == activo)
    if estado is not None:
        stmt = stmt.where(Vehiculo.estado == estado)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=VehiculoResponse, status_code=status.HTTP_201_CREATED)
async def create_vehiculo(
    payload: VehiculoCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "write")),
):
    vehiculo = Vehiculo(**payload.model_dump())
    db.add(vehiculo)
    try:
        await db.commit()
        await db.refresh(vehiculo)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Placa ya registrada")
    return vehiculo


@router.get("/{placa}", response_model=VehiculoResponse)
async def get_vehiculo(
    placa: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "read")),
):
    vehiculo = await db.get(Vehiculo, placa)
    if vehiculo is None:
        raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
    return vehiculo


@router.patch("/{placa}", response_model=VehiculoResponse)
async def update_vehiculo(
    placa: str,
    payload: VehiculoUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "write")),
):
    vehiculo = await db.get(Vehiculo, placa)
    if vehiculo is None:
        raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(vehiculo, k, v)
    await db.commit()
    await db.refresh(vehiculo)
    return vehiculo


@router.delete("/{placa}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehiculo(
    placa: str,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "delete")),
):
    vehiculo = await db.get(Vehiculo, placa)
    if vehiculo is None:
        raise HTTPException(status_code=404, detail="Vehiculo no encontrado")
    vehiculo.activo = False
    vehiculo.estado = "Inactivo"
    await db.commit()
