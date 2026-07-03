from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import invalidar_cache_permisos, require_permiso
from core.database import get_db
from models.roles import Permiso, Rol
from services import keycloak_admin
from schemas.roles import (
    PermisoCreate,
    PermisoResponse,
    PermisosBulkSet,
    RolCreate,
    RolResponse,
    RolUpdate,
)

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=list[RolResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "read")),
):
    result = await db.execute(select(Rol).options(selectinload(Rol.permisos)))
    return result.scalars().all()


@router.get("/permisos/all", response_model=list[PermisoResponse], tags=["permisos"])
async def list_all_permisos(
    rol_id: int | None = None,
    recurso: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "read")),
):
    stmt = select(Permiso)
    if rol_id is not None:
        stmt = stmt.where(Permiso.rol_id == rol_id)
    if recurso is not None:
        stmt = stmt.where(Permiso.recurso == recurso)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/permisos/{permiso_id}", response_model=PermisoResponse, tags=["permisos"])
async def get_permiso(
    permiso_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "read")),
):
    permiso = await db.get(Permiso, permiso_id)
    if permiso is None:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    return permiso


@router.post("/", response_model=RolResponse, status_code=status.HTTP_201_CREATED)
async def create_rol(
    payload: RolCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "write")),
):
    # El rol debe existir TAMBIÉN como realm-role en Keycloak: el rol del usuario viaja
    # en el token, así que un rol solo-local sería invisible al autenticar. Se crea
    # primero allá (si falla → 503 y no queda un rol local inutilizable).
    await keycloak_admin.asegurar_rol_realm(payload.nombre)
    rol = Rol(nombre=payload.nombre)
    db.add(rol)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Nombre de rol ya existe")
    result = await db.execute(
        select(Rol).options(selectinload(Rol.permisos)).where(Rol.id == rol.id)
    )
    return result.scalar_one()


@router.get("/{rol_id}", response_model=RolResponse)
async def get_rol(
    rol_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "read")),
):
    result = await db.execute(select(Rol).options(selectinload(Rol.permisos)).where(Rol.id == rol_id))
    rol = result.scalar_one_or_none()
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    return rol


@router.patch("/{rol_id}", response_model=RolResponse)
async def update_rol(
    rol_id: int,
    payload: RolUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "write")),
):
    rol = await db.get(Rol, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    update = payload.model_dump(exclude_unset=True)
    nombre_anterior = rol.nombre
    renombrado = bool(update.get("nombre")) and update["nombre"] != nombre_anterior
    # Renombrar = migrar el realm-role en Keycloak (crear nuevo, reasignar miembros,
    # borrar viejo) ANTES del commit local: si Keycloak falla, nada queda a medias.
    if renombrado:
        await keycloak_admin.renombrar_rol_realm(nombre_anterior, update["nombre"])
    for k, v in update.items():
        setattr(rol, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Nombre de rol ya existe")
    invalidar_cache_permisos(rol_id)
    result = await db.execute(
        select(Rol).options(selectinload(Rol.permisos)).where(Rol.id == rol_id)
    )
    return result.scalar_one()


@router.delete("/{rol_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rol(
    rol_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "delete")),
):
    rol = await db.get(Rol, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    nombre = rol.nombre
    await db.delete(rol)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar el rol: tiene usuarios asociados. Reasigna esos usuarios a otro rol antes de borrarlo.",
        )
    # Retirar también el realm-role de Keycloak (best-effort: el rol local ya no existe).
    await keycloak_admin.eliminar_rol_realm(nombre)
    invalidar_cache_permisos(rol_id)


@router.post("/{rol_id}/permisos", response_model=PermisoResponse, status_code=status.HTTP_201_CREATED)
async def add_permiso(
    rol_id: int,
    payload: PermisoCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "write")),
):
    rol = await db.get(Rol, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    permiso = Permiso(rol_id=rol_id, recurso=payload.recurso, accion=payload.accion)
    db.add(permiso)
    try:
        await db.commit()
        await db.refresh(permiso)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Permiso ya existe para este rol")
    invalidar_cache_permisos(rol_id)
    return permiso


@router.put("/{rol_id}/permisos", response_model=RolResponse)
async def set_permisos(
    rol_id: int,
    payload: PermisosBulkSet,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "write")),
):
    """Reemplaza el conjunto completo de permisos del rol en UNA operación (multiselección).

    Calcula el diff contra los permisos existentes: agrega los nuevos y elimina los que ya
    no estén en la lista. Idempotente (los duplicados del payload se colapsan). Devuelve el
    rol con sus permisos ya actualizados.
    """
    rol = await db.get(Rol, rol_id)
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado")

    deseados = {(p.recurso.strip(), p.accion.strip()) for p in payload.permisos}
    existentes_rows = (
        await db.execute(select(Permiso).where(Permiso.rol_id == rol_id))
    ).scalars().all()
    existentes = {(p.recurso, p.accion): p for p in existentes_rows}

    # Quitar los que ya no están seleccionados.
    for par, row in existentes.items():
        if par not in deseados:
            await db.delete(row)
    # Agregar los nuevos.
    for recurso, accion in deseados - set(existentes.keys()):
        db.add(Permiso(rol_id=rol_id, recurso=recurso, accion=accion))

    await db.commit()
    invalidar_cache_permisos(rol_id)
    result = await db.execute(
        select(Rol).options(selectinload(Rol.permisos)).where(Rol.id == rol_id)
    )
    return result.scalar_one()


@router.delete("/{rol_id}/permisos/{permiso_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_permiso(
    rol_id: int,
    permiso_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("roles", "write")),
):
    permiso = await db.get(Permiso, permiso_id)
    if permiso is None or permiso.rol_id != rol_id:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    await db.delete(permiso)
    await db.commit()
    invalidar_cache_permisos(rol_id)
