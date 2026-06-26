"""Endpoints de autenticación.

Con Keycloak como proveedor de identidad, el inicio de sesión (login, logout, refresh,
registro) ocurre íntegramente en Keycloak desde el frontend (OIDC Authorization Code +
PKCE). El backend solo VALIDA el access token recibido y expone el perfil del usuario
autenticado: aquí queda únicamente `GET /auth/me`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.database import get_db
from models.roles import Rol
from models.usuarios import Usuario
from schemas.usuarios import UsuarioResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UsuarioResponse)
async def me(current_user: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Perfil del usuario autenticado (provisionado/enlazado desde el token de Keycloak),
    incluyendo su rol y los permisos del rol (para el control de UI en el frontend)."""
    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.rol).selectinload(Rol.permisos))
        .where(Usuario.id == current_user.id)
    )
    return result.scalar_one()
