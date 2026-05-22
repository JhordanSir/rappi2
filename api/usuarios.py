from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import invalidar_cache_permisos, require_permiso
from core.database import get_db
from core.security import hash_password
from models.roles import Rol
from models.usuarios import Usuario
from schemas.usuarios import UsuarioCreate, UsuarioResponse, UsuarioUpdate

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/", response_model=list[UsuarioResponse])
async def list_usuarios(
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "read")),
):
    stmt = select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos))
    if activo is not None:
        stmt = stmt.where(Usuario.activo == activo)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    payload: UsuarioCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "write")),
):
    rol = await db.get(Rol, payload.rol_id)
    if rol is None:
        raise HTTPException(status_code=400, detail="rol_id invalido")
    usuario = Usuario(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol_id=payload.rol_id,
        cliente_id=payload.cliente_id,
    )
    db.add(usuario)
    try:
        await db.commit()
        await db.refresh(usuario)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Username, email o cliente_id ya en uso")
    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == usuario.id)
    )
    return result.scalar_one()


@router.get("/{usuario_id}", response_model=UsuarioResponse)
async def get_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "read")),
):
    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == usuario_id)
    )
    usuario = result.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioResponse)
async def update_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "write")),
):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    update = payload.model_dump(exclude_unset=True)
    if "password" in update:
        usuario.password_hash = hash_password(update.pop("password"))
    rol_anterior = usuario.rol_id
    for k, v in update.items():
        setattr(usuario, k, v)
    try:
        await db.commit()
        await db.refresh(usuario)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email ya en uso")
    if usuario.rol_id != rol_anterior:
        invalidar_cache_permisos(rol_anterior)
        invalidar_cache_permisos(usuario.rol_id)
    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == usuario.id)
    )
    return result.scalar_one()


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "delete")),
):
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    usuario.activo = False
    await db.commit()
