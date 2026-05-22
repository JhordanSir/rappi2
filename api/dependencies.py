import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.mongo import get_mongo_db as _get_mongo_db
from core.security import decode_access_token
from models.usuarios import Usuario
from models.roles import Rol, Permiso

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

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
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol)).where(Usuario.id == user_id)
    )
    user = result.scalar_one_or_none()
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Sin permiso para {recurso}:{accion}")
    return _checker


async def get_mongo_db() -> AsyncIOMotorDatabase:
    return await _get_mongo_db()
