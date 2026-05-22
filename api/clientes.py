from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import require_permiso
from core.database import get_db
from models.clientes import Cliente, ClienteDireccion
from schemas.clientes import (
    ClienteCreate,
    ClienteDireccionCreate,
    ClienteDireccionResponse,
    ClienteDireccionUpdate,
    ClienteResponse,
    ClienteUpdate,
)

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.get("/", response_model=list[ClienteResponse])
async def list_clientes(
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = True,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("clientes", "read")),
):
    stmt = select(Cliente).options(selectinload(Cliente.direcciones))
    if activo is not None:
        stmt = stmt.where(Cliente.activo == activo)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
async def create_cliente(
    payload: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("clientes", "write")),
):
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
    _: object = Depends(require_permiso("clientes", "read")),
):
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
    _: object = Depends(require_permiso("clientes", "write")),
):
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
    _: object = Depends(require_permiso("clientes", "delete")),
):
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    cliente.activo = False
    await db.commit()


@router.post("/{cliente_id}/direcciones", response_model=ClienteDireccionResponse, status_code=status.HTTP_201_CREATED)
async def add_direccion(
    cliente_id: int,
    payload: ClienteDireccionCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("clientes", "write")),
):
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    if payload.es_principal:
        existentes = await db.execute(
            select(ClienteDireccion).where(ClienteDireccion.cliente_id == cliente_id, ClienteDireccion.es_principal == True)
        )
        for dir_existente in existentes.scalars().all():
            dir_existente.es_principal = False
    direccion = ClienteDireccion(cliente_id=cliente_id, **payload.model_dump())
    db.add(direccion)
    await db.commit()
    await db.refresh(direccion)
    return direccion


@router.get("/{cliente_id}/direcciones", response_model=list[ClienteDireccionResponse])
async def list_direcciones(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("clientes", "read")),
):
    result = await db.execute(select(ClienteDireccion).where(ClienteDireccion.cliente_id == cliente_id))
    return result.scalars().all()


@router.patch("/{cliente_id}/direcciones/{direccion_id}", response_model=ClienteDireccionResponse)
async def update_direccion(
    cliente_id: int,
    direccion_id: int,
    payload: ClienteDireccionUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("clientes", "write")),
):
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
    _: object = Depends(require_permiso("clientes", "write")),
):
    direccion = await db.get(ClienteDireccion, direccion_id)
    if direccion is None or direccion.cliente_id != cliente_id:
        raise HTTPException(status_code=404, detail="Direccion no encontrada")
    await db.delete(direccion)
    await db.commit()
