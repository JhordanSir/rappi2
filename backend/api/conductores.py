from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user, require_permiso
from core.database import get_db
from core.pagination import ordenar, paginate
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
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    disponibilidad: str | None = None,
    q: str | None = Query(None, description="Busca por nombre o licencia"),
    orden_por: str | None = Query(None, description="Campo de ordenamiento (cabecera)"),
    direccion: str | None = Query(None, alias="dir", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("conductores", "read")),
):
    stmt = select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario))
    if activo is not None:
        stmt = stmt.where(Conductor.activo == activo)
    if disponibilidad is not None:
        stmt = stmt.where(Conductor.disponibilidad == disponibilidad)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(Conductor.nombre.ilike(patron), Conductor.licencia.ilike(patron)))
    stmt = ordenar(
        stmt, orden_por, direccion,
        {"id": Conductor.id, "nombre": Conductor.nombre, "licencia": Conductor.licencia,
         "disponibilidad": Conductor.disponibilidad, "vehiculo_placa": Conductor.vehiculo_placa,
         "activo": Conductor.activo},
        por_defecto=Conductor.id,
    )
    # Body = lista simple; el total (sin paginar) viaja en el header X-Total-Count.
    return await paginate(db, stmt, response, skip, limit)


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
        select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario)).where(Conductor.id == conductor.id)
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
        select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario)).where(Conductor.usuario_id == current_user.id)
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
        select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario)).where(Conductor.id == conductor_id)
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
    # Reactivación coherente: el delete desactiva en cascada conductor→usuario; reactivar
    # el conductor con el usuario aún inactivo dejaría una ficha operable sin login.
    # Política: solo un admin reactiva usuarios (primero el usuario, luego la ficha).
    if update.get("activo") and not conductor.activo:
        usuario = await db.get(Usuario, conductor.usuario_id)
        if usuario is not None and not usuario.activo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"El usuario «{usuario.username}» vinculado está inactivo. "
                    "Reactívalo primero desde Usuarios y luego reactiva al conductor."
                ),
            )
        # Al volver a estar activo, vuelve al pool de despacho.
        update.setdefault("disponibilidad", "Disponible")
    for k, v in update.items():
        setattr(conductor, k, v)
    await db.commit()
    await db.refresh(conductor)
    result = await db.execute(
        select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario)).where(Conductor.id == conductor.id)
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
        select(Conductor).options(selectinload(Conductor.vehiculo), selectinload(Conductor.usuario)).where(Conductor.id == conductor.id)
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
