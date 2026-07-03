import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose.exceptions import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import get_db
from core.mongo import get_mongo_db as _get_mongo_db
from models.asignaciones import Asignacion
from models.conductores import Conductor
from models.ordenes import Orden
from models.roles import Permiso
from models.usuarios import Usuario
from services.keycloak import validate_token
from services.provisioning import ensure_usuario_from_claims

# Esquema OAuth2 (Authorization Code) apuntando a Keycloak: habilita el botón
# "Authorize" de /docs y documenta de dónde sale el token. El backend solo VALIDA
# el Bearer recibido (no participa en el intercambio).
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.keycloak_authorization_url,
    tokenUrl=settings.keycloak_token_url,
    auto_error=True,
)

# Roles de usuario FINAL (con filtro de fila: solo ven lo suyo). Cualquier otro rol
# —Admin o personalizados como Despachador/Auditor— es staff: visibilidad total de
# filas, y la matriz de permisos finos (require_permiso) acota qué puede HACER.
ROLES_USUARIO_FINAL = {"Cliente", "Conductor"}


def es_staff_rol(rol_nombre: Optional[str]) -> bool:
    """True si el rol es interno/staff (todo lo que no sea Cliente o Conductor)."""
    return rol_nombre is not None and rol_nombre not in ROLES_USUARIO_FINAL

# El ROL del usuario lo asigna Keycloak (viene en el token y lo refleja usuario.rol_id),
# pero el conjunto de permisos finos de cada rol vive en la BD local (tabla `permisos`) y
# es editable desde "Roles & Permisos". Cache por rol con TTL corto para no consultar en
# cada request; se invalida al editar permisos (ver api/roles.py).
_PERMISO_CACHE: dict[int, tuple[float, list[tuple[str, str]]]] = {}
_PERMISO_TTL_SECONDS = 60


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = await validate_token(token)
    except JWTError:
        raise credentials_exception

    # Provisiona/enlaza el espejo local del usuario de Keycloak.
    try:
        user = await ensure_usuario_from_claims(db, claims)
        await db.commit()
    except IntegrityError:
        # Carrera entre dos primeros requests del mismo usuario: re-leer el existente.
        await db.rollback()
        user = (
            await db.execute(select(Usuario).where(Usuario.keycloak_sub == claims.get("sub")))
        ).scalar_one_or_none()
        if user is None:
            raise credentials_exception

    # Recargar con el rol (lazy=joined no basta para un objeto recién creado/modificado).
    user = (
        await db.execute(
            select(Usuario).options(selectinload(Usuario.rol)).where(Usuario.id == user.id)
        )
    ).scalar_one_or_none()
    if user is None or not user.activo:
        raise credentials_exception
    return user


async def _cargar_permisos(db: AsyncSession, rol_id: int) -> list[tuple[str, str]]:
    now = time.monotonic()
    cached = _PERMISO_CACHE.get(rol_id)
    if cached and (now - cached[0]) < _PERMISO_TTL_SECONDS:
        return cached[1]
    result = await db.execute(select(Permiso).where(Permiso.rol_id == rol_id))
    permisos = [(p.recurso, p.accion) for p in result.scalars().all()]
    _PERMISO_CACHE[rol_id] = (now, permisos)
    return permisos


def invalidar_cache_permisos(rol_id: Optional[int] = None) -> None:
    if rol_id is None:
        _PERMISO_CACHE.clear()
    else:
        _PERMISO_CACHE.pop(rol_id, None)


def require_permiso(recurso: str, accion: str):
    async def _checker(
        user: Usuario = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Usuario:
        permisos = await _cargar_permisos(db, user.rol_id)
        for r, a in permisos:
            if (r == "*" or r == recurso) and (a == "*" or a == accion):
                return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sin permiso para {recurso}:{accion}",
        )
    return _checker


async def get_mongo_db() -> AsyncIOMotorDatabase:
    return await _get_mongo_db()


@dataclass
class UserScope:
    """Alcance de fila del usuario autenticado. Los endpoints lo usan para
    restringir cada quien a SUS datos. El staff (Admin/Despachador) ve todo."""

    user: Usuario
    is_staff: bool
    cliente_id: Optional[int]
    conductor_id: Optional[int]

    def ve_todo(self) -> bool:
        return self.is_staff


async def get_scope(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserScope:
    rol_nombre = user.rol.nombre if user.rol is not None else None
    is_staff = es_staff_rol(rol_nombre)
    cliente_id = user.cliente_id
    conductor_id: Optional[int] = None
    # Solo resolvemos el conductor cuando no es staff ni cliente (una query indexada).
    if not is_staff and cliente_id is None:
        conductor_id = (
            await db.execute(select(Conductor.id).where(Conductor.usuario_id == user.id))
        ).scalar_one_or_none()
    return UserScope(user=user, is_staff=is_staff, cliente_id=cliente_id, conductor_id=conductor_id)


async def orden_en_alcance(db: AsyncSession, scope: UserScope, orden: Orden) -> bool:
    """True si el usuario puede ver/operar esta orden segun su alcance de fila:
    staff todo, cliente solo las suyas, conductor solo las que tiene asignadas."""
    if scope.ve_todo():
        return True
    if scope.cliente_id is not None:
        return orden.cliente_id == scope.cliente_id
    if scope.conductor_id is not None:
        asignada = (
            await db.execute(
                select(Asignacion.id)
                .where(Asignacion.orden_id == orden.id, Asignacion.conductor_id == scope.conductor_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        return asignada is not None
    return False
