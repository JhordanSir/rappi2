from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import UserScope, get_scope, require_permiso
from core.database import get_db
from core.pagination import paginate
from models.clientes import Cliente, ClienteDireccion
from models.usuarios import Usuario
from schemas.clientes import (
    ClienteCreate,
    ClienteDireccionCreate,
    ClienteDireccionResponse,
    ClienteDireccionUpdate,
    ClienteResponse,
    ClienteUpdate,
)
from services.geocoding import resolver_coords

router = APIRouter(prefix="/clientes", tags=["clientes"])


def _puede_ver(scope: UserScope, cliente_id: int) -> bool:
    """El cliente solo puede acceder a su propia ficha; el staff a cualquiera."""
    return scope.ve_todo() or (scope.cliente_id is not None and scope.cliente_id == cliente_id)


def _solo_staff(scope: UserScope) -> None:
    if not scope.ve_todo():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción reservada al personal interno")


@router.get("/", response_model=list[ClienteResponse])
async def list_clientes(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    q: str | None = Query(None, description="Busca por nombre, email, teléfono o documento"),
    desde: datetime | None = Query(None, description="fecha_registro >= desde"),
    hasta: datetime | None = Query(None, description="fecha_registro <= hasta"),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "read")),
):
    stmt = select(Cliente).options(selectinload(Cliente.direcciones))
    if not scope.ve_todo():
        # Un cliente solo se ve a sí mismo en el listado.
        if scope.cliente_id is None:
            response.headers["X-Total-Count"] = "0"
            return []
        stmt = stmt.where(Cliente.id == scope.cliente_id)
    if activo is not None:
        stmt = stmt.where(Cliente.activo == activo)
    if desde is not None:
        stmt = stmt.where(Cliente.fecha_registro >= desde)
    if hasta is not None:
        stmt = stmt.where(Cliente.fecha_registro <= hasta)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Cliente.nombre.ilike(patron),
            Cliente.email.ilike(patron),
            Cliente.telefono.ilike(patron),
            Cliente.cc_id.ilike(patron),
        ))
    stmt = stmt.order_by(Cliente.id)
    # Body = lista simple; el total (sin paginar) viaja en el header X-Total-Count.
    return await paginate(db, stmt, response, skip, limit)


@router.post("/", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
async def create_cliente(
    payload: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "write")),
):
    _solo_staff(scope)
    cliente = Cliente(**payload.model_dump())
    db.add(cliente)
    try:
        await db.commit()
        await db.refresh(cliente)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email ya registrado")
    result = await db.execute(
        select(Cliente).options(selectinload(Cliente.direcciones)).where(Cliente.id == cliente.id)
    )
    return result.scalar_one()


@router.get("/{cliente_id}", response_model=ClienteResponse)
async def get_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "read")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    result = await db.execute(
        select(Cliente).options(selectinload(Cliente.direcciones)).where(Cliente.id == cliente_id)
    )
    cliente = result.scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@router.patch("/{cliente_id}", response_model=ClienteResponse)
async def update_cliente(
    cliente_id: int,
    payload: ClienteUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "write")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cliente, k, v)
    try:
        await db.commit()
        await db.refresh(cliente)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email ya en uso")
    result = await db.execute(
        select(Cliente).options(selectinload(Cliente.direcciones)).where(Cliente.id == cliente.id)
    )
    return result.scalar_one()


@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "delete")),
):
    _solo_staff(scope)
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente.activo = False
    # Cascada (P6): desactivar el usuario vinculado, si existe.
    usuario = (
        await db.execute(select(Usuario).where(Usuario.cliente_id == cliente.id))
    ).scalar_one_or_none()
    if usuario is not None:
        usuario.activo = False
    await db.commit()


@router.post("/{cliente_id}/direcciones", response_model=ClienteDireccionResponse, status_code=status.HTTP_201_CREATED)
async def add_direccion(
    cliente_id: int,
    payload: ClienteDireccionCreate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "write")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if payload.es_principal:
        existentes = await db.execute(
            select(ClienteDireccion).where(ClienteDireccion.cliente_id == cliente_id, ClienteDireccion.es_principal == True)
        )
        for dir_existente in existentes.scalars().all():
            dir_existente.es_principal = False
    data = payload.model_dump()
    data["lat"], data["lon"] = await resolver_coords(data.get("direccion"), data.get("lat"), data.get("lon"))
    direccion = ClienteDireccion(cliente_id=cliente_id, **data)
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)
    return direccion


@router.get("/{cliente_id}/direcciones", response_model=list[ClienteDireccionResponse])
async def list_direcciones(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "read")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    result = await db.execute(select(ClienteDireccion).where(ClienteDireccion.cliente_id == cliente_id))
    return result.scalars().all()


@router.patch("/{cliente_id}/direcciones/{direccion_id}", response_model=ClienteDireccionResponse)
async def update_direccion(
    cliente_id: int,
    direccion_id: int,
    payload: ClienteDireccionUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "write")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    direccion = await db.get(ClienteDireccion, direccion_id)
    if direccion is None or direccion.cliente_id != cliente_id:
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    update = payload.model_dump(exclude_unset=True)
    if update.get("es_principal"):
        existentes = await db.execute(
            select(ClienteDireccion).where(
                ClienteDireccion.cliente_id == cliente_id,
                ClienteDireccion.es_principal == True,
                ClienteDireccion.id != direccion_id,
            )
        )
        for d in existentes.scalars().all():
            d.es_principal = False
    if "direccion" in update and update.get("lat") is None and update.get("lon") is None:
        update["lat"], update["lon"] = await resolver_coords(update["direccion"], None, None)
    for k, v in update.items():
        setattr(direccion, k, v)
    await db.commit()
    await db.refresh(direccion)
    return direccion


@router.delete("/{cliente_id}/direcciones/{direccion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_direccion(
    cliente_id: int,
    direccion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("clientes", "write")),
):
    if not _puede_ver(scope, cliente_id):
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    direccion = await db.get(ClienteDireccion, direccion_id)
    if direccion is None or direccion.cliente_id != cliente_id:
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    await db.delete(direccion)
    await db.commit()
