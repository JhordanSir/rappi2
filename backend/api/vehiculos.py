from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from core.pagination import ordenar, paginate
from models.vehiculos import Vehiculo
from schemas.vehiculos import VehiculoCreate, VehiculoResponse, VehiculoUpdate

router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])


@router.get("/", response_model=list[VehiculoResponse])
async def list_vehiculos(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    estado: str | None = None,
    tipo: str | None = Query(None, description="Tipo de vehículo (parcial: 'moto', 'camioneta'…)"),
    capacidad_min: float | None = Query(None, ge=0, description="Capacidad mínima en kg"),
    q: str | None = Query(None, description="Busca por placa o tipo"),
    orden_por: str | None = Query(None, description="Campo de ordenamiento (cabecera)"),
    direccion: str | None = Query(None, alias="dir", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("vehiculos", "read")),
):
    stmt = select(Vehiculo)
    if activo is not None:
        stmt = stmt.where(Vehiculo.activo == activo)
    if estado is not None:
        stmt = stmt.where(Vehiculo.estado == estado)
    if tipo:
        stmt = stmt.where(Vehiculo.tipo.ilike(f"%{tipo.strip()}%"))
    if capacidad_min is not None:
        stmt = stmt.where(Vehiculo.capacidad_kg >= capacidad_min)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(Vehiculo.placa.ilike(patron), Vehiculo.tipo.ilike(patron)))
    stmt = ordenar(
        stmt, orden_por, direccion,
        {"placa": Vehiculo.placa, "tipo": Vehiculo.tipo, "capacidad_kg": Vehiculo.capacidad_kg,
         "estado": Vehiculo.estado, "activo": Vehiculo.activo},
        por_defecto=Vehiculo.placa,
    )
    # Body = lista simple; el total (sin paginar) viaja en el header X-Total-Count.
    return await paginate(db, stmt, response, skip, limit)


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
