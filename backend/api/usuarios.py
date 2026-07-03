from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import invalidar_cache_permisos, require_permiso
from core.database import get_db
from core.pagination import paginate
from core.security import hash_password
from models.clientes import Cliente
from models.conductores import Conductor
from models.roles import Rol
from models.usuarios import Usuario
from schemas.usuarios import UsuarioCreate, UsuarioResponse, UsuarioUpdate
from services import keycloak_admin
from services.provisioning import sincronizar_por_rol

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/", response_model=list[UsuarioResponse])
async def list_usuarios(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    activo: bool | None = None,
    q: str | None = Query(None, description="Busca por username o email"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "read")),
):
    stmt = select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos))
    if activo is not None:
        stmt = stmt.where(Usuario.activo == activo)
    if q:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(Usuario.username.ilike(patron), Usuario.email.ilike(patron)))
    stmt = stmt.order_by(Usuario.id)
    # Body = lista simple; el total (sin paginar) viaja en el header X-Total-Count.
    return await paginate(db, stmt, response, skip, limit)


@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    payload: UsuarioCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("usuarios", "write")),
):
    rol = await db.get(Rol, payload.rol_id)
    if rol is None:
        raise HTTPException(status_code=400, detail="rol_id invalido")
    # Si ya existe alguien con ese correo, guiar al admin: si está INACTIVO no se puede
    # recrear (el correo es único) → debe reactivarlo; si está activo, es duplicado real.
    previo = (
        await db.execute(select(Usuario).where(Usuario.email == payload.email))
    ).scalar_one_or_none()
    if previo is not None:
        if not previo.activo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ya existe un usuario inactivo con el correo {payload.email} "
                    f"(«{previo.username}»). Reactívalo desde la lista de usuarios."
                ),
            )
        raise HTTPException(status_code=400, detail="El correo ya está en uso")
    # Keycloak es el proveedor de identidad ÚNICO: el usuario se crea PRIMERO allá
    # (con contraseña y rol); si falla, no se crea nada local (sin cuentas huérfanas
    # que no puedan iniciar sesión). El registro local es solo el espejo.
    sub = await keycloak_admin.crear_usuario(
        payload.username, payload.email, payload.password, rol.nombre
    )
    usuario = Usuario(
        username=payload.username,
        email=payload.email,
        password_hash=None,  # la credencial vive en Keycloak
        rol_id=payload.rol_id,
        cliente_id=payload.cliente_id,
        auth_provider="keycloak",
        keycloak_sub=sub,
    )
    db.add(usuario)
    try:
        await db.flush()  # asigna usuario.id (necesario para la ficha especializada)
        # Crea/enlaza la ficha Cliente o Conductor segun el rol (P1, P4).
        await sincronizar_por_rol(db, usuario, rol.nombre)
        await db.commit()
        await db.refresh(usuario)
    except IntegrityError:
        await db.rollback()
        # Deshacer la creación en Keycloak para no dejar la cuenta a medias.
        await keycloak_admin.eliminar(sub)
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
    password_nuevo = update.pop("password", None)
    rol_anterior = usuario.rol_id
    activo_anterior = usuario.activo
    for k, v in update.items():
        setattr(usuario, k, v)
    rol_cambio = usuario.rol_id != rol_anterior
    # Reactivación (Inactivo -> Activo; solo un admin llega aquí): revivir la ficha
    # Cliente/Conductor que el soft-delete desactivó en cascada. Si no, el usuario vuelve
    # activo pero su ficha queda inactiva y no puede operar.
    reactivado = usuario.activo and not activo_anterior
    rol_nuevo = None
    if rol_cambio:
        rol_nuevo = await db.get(Rol, usuario.rol_id)
        if rol_nuevo is None:
            await db.rollback()
            raise HTTPException(status_code=400, detail="rol_id invalido")
    # Propagar a Keycloak ANTES del commit local: si Keycloak falla (503), nada queda
    # a medias. Usuarios legacy sin `keycloak_sub` (previos a la federación): solo se
    # tocan localmente y su contraseña se sigue guardando como hash local.
    if usuario.keycloak_sub:
        if "email" in update:
            await keycloak_admin.actualizar(usuario.keycloak_sub, email=update["email"])
        if "activo" in update:
            await keycloak_admin.actualizar(usuario.keycloak_sub, enabled=update["activo"])
        if password_nuevo:
            await keycloak_admin.reset_password(usuario.keycloak_sub, password_nuevo)
        if rol_cambio:
            await keycloak_admin.asignar_rol(usuario.keycloak_sub, rol_nuevo.nombre)
    elif password_nuevo:
        usuario.password_hash = hash_password(password_nuevo)
    try:
        await db.flush()
        # Al cambiar de rol, migrar/crear la ficha especializada (P3); al reactivar,
        # revivir la ficha del rol actual (espejo de la cascada de baja del delete, P6).
        if rol_cambio:
            await sincronizar_por_rol(db, usuario, rol_nuevo.nombre)
        elif reactivado:
            rol_actual = await db.get(Rol, usuario.rol_id)
            await sincronizar_por_rol(db, usuario, rol_actual.nombre)
        await db.commit()
        await db.refresh(usuario)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email o licencia ya en uso")
    if rol_cambio:
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
    # También se deshabilita en Keycloak (antes del commit local): sin esto la cuenta
    # seguiría pudiendo iniciar sesión aunque el espejo local esté inactivo.
    if usuario.keycloak_sub:
        await keycloak_admin.actualizar(usuario.keycloak_sub, enabled=False)
    usuario.activo = False
    # Cascada (P6): desactivar las fichas especializadas vinculadas.
    conductor = (
        await db.execute(select(Conductor).where(Conductor.usuario_id == usuario.id))
    ).scalar_one_or_none()
    if conductor is not None:
        conductor.activo = False
        conductor.disponibilidad = "Inactivo"
    if usuario.cliente_id is not None:
        cliente = await db.get(Cliente, usuario.cliente_id)
        if cliente is not None:
            cliente.activo = False
    await db.commit()
