from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user, require_permiso
from core.database import get_db
from models.conductores import Conductor
from models.usuarios import Usuario
from models.vehiculos import Vehiculo
from schemas.conductores import (
    AsignarVehiculoRequest,
    ConductorCreate,
    ConductorResponse,
    ConductorUpdate,
)

router = APIRouter(prefix="/conductores", tags=["conductores"])


@router.get("/", response_model=list[ConductorResponse])
async def list_conductores(
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    disponibilidad: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "read")),
):
    stmt = select(Conductor).options(selectinload(Conductor.vehiculo))
    if activo is not None:
        stmt = stmt.where(Conductor.activo == activo)
    if disponibilidad is not None:
        stmt = stmt.where(Conductor.disponibilidad == disponibilidad)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ConductorResponse, status_code=status.HTTP_201_CREATED)
async def create_conductor(
    payload: ConductorCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "write")),
):
    usuario = await db.get(Usuario, payload.usuario_id)
    if usuario is None:
        raise HTTPException(status_code=400, detail="usuario_id invalido")
    if payload.vehiculo_placa:
        vehiculo = await db.get(Vehiculo, payload.vehiculo_placa)
        if vehiculo is None:
            raise HTTPException(status_code=400, detail="vehiculo_placa invalido")
    conductor = Conductor(**payload.model_dump())
    db.add(conductor)
    try:
        await db.commit()
        await db.refresh(conductor)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="usuario_id o licencia ya en uso")
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo)).where(Conductor.id == conductor.id)
    )
    return result.scalar_one()


@router.get("/me", response_model=ConductorResponse)
async def get_mi_conductor(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
    _: object = Depends(require_permiso("conductores", "read")),
):
    """Perfil del conductor autenticado (lo usa la app del conductor para arrancar)."""
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo)).where(Conductor.usuario_id == current_user.id)
    )
    conductor = result.scalar_one_or_none()
    if conductor is None:
        raise HTTPException(status_code=404, detail="No tienes un perfil de conductor")
    return conductor


@router.get("/{conductor_id}", response_model=ConductorResponse)
async def get_conductor(
    conductor_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "read")),
):
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo)).where(Conductor.id == conductor_id)
    )
    conductor = result.scalar_one_or_none()
    if conductor is None:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    return conductor


@router.patch("/{conductor_id}", response_model=ConductorResponse)
async def update_conductor(
    conductor_id: int,
    payload: ConductorUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "write")),
):
    conductor = await db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    update = payload.model_dump(exclude_unset=True)
    if update.get("vehiculo_placa"):
        vehiculo = await db.get(Vehiculo, update["vehiculo_placa"])
        if vehiculo is None:
            raise HTTPException(status_code=400, detail="vehiculo_placa invalido")
    for k, v in update.items():
        setattr(conductor, k, v)
    await db.commit()
    await db.refresh(conductor)
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo)).where(Conductor.id == conductor.id)
    )
    return result.scalar_one()


@router.patch("/{conductor_id}/vehiculo", response_model=ConductorResponse)
async def asignar_vehiculo(
    conductor_id: int,
    payload: AsignarVehiculoRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "write")),
):
    conductor = await db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    if payload.vehiculo_placa is not None:
        vehiculo = await db.get(Vehiculo, payload.vehiculo_placa)
        if vehiculo is None or not vehiculo.activo:
            raise HTTPException(status_code=400, detail="Vehiculo invalido o inactivo")
        if vehiculo.estado != "Operativo":
            raise HTTPException(status_code=400, detail="Vehiculo no esta operativo")
    conductor.vehiculo_placa = payload.vehiculo_placa
    await db.commit()
    await db.refresh(conductor)
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo)).where(Conductor.id == conductor.id)
    )
    return result.scalar_one()


@router.delete("/{conductor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conductor(
    conductor_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "delete")),
):
    conductor = await db.get(Conductor, conductor_id)
    if conductor is None:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    conductor.activo = False
    conductor.disponibilidad = "Inactivo"
    # Cascada (P6): desactivar el usuario vinculado para que no pueda iniciar sesion.
    usuario = await db.get(Usuario, conductor.usuario_id)
    if usuario is not None:
        usuario.activo = False
    await db.commit()
