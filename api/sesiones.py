"""Gestion de sesiones (refresh tokens) como sub-recurso del usuario.

Reemplaza al antiguo api/tokens.py para que la administracion de sesiones
viva semanticamente bajo /usuarios/{id}/sesiones en vez de un CRUD aislado.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_current_user, require_permiso
from core.database import get_db
from models.usuarios import Token, Usuario
from schemas.auth import TokenInfo

router = APIRouter(prefix="/usuarios", tags=["sesiones"])


def _puede_ver_sesiones_de(actor: Usuario, usuario_id: int) -> bool:
    return actor.id == usuario_id


@router.get("/me/sesiones", response_model=list[TokenInfo])
async def listar_mis_sesiones(
    activos_solo: bool = True,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sesiones del usuario autenticado (no requiere permiso administrativo)."""
    stmt = select(Token).where(Token.usuario_id == current_user.id)
    if activos_solo:
        stmt = stmt.where(Token.revocado == False, Token.fecha_expiracion > datetime.now(timezone.utc))
    stmt = stmt.order_by(Token.fecha_expiracion.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{usuario_id}/sesiones", response_model=list[TokenInfo])
async def listar_sesiones_de_usuario(
    usuario_id: int,
    activos_solo: bool = True,
    skip: int = 0,
    limit: int = Query(50, le=200),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sesiones de un usuario concreto. El propio usuario puede consultarlas;
    si es otro, requiere permiso administrativo sesiones:read.
    """
    if not _puede_ver_sesiones_de(current_user, usuario_id):
        await require_permiso("sesiones", "read")(user=current_user, db=db)

    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    stmt = select(Token).where(Token.usuario_id == usuario_id)
    if activos_solo:
        stmt = stmt.where(Token.revocado == False, Token.fecha_expiracion > datetime.now(timezone.utc))
    stmt = stmt.order_by(Token.fecha_expiracion.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/{usuario_id}/sesiones/{sesion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revocar_sesion(
    usuario_id: int,
    sesion_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoca una sesion concreta. Permitido al dueno o a admins con sesiones:delete."""
    if not _puede_ver_sesiones_de(current_user, usuario_id):
        await require_permiso("sesiones", "delete")(user=current_user, db=db)

    token = await db.get(Token, sesion_id)
    if token is None or token.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    if not token.revocado:
        token.revocado = True
        await db.commit()


@router.delete("/{usuario_id}/sesiones", status_code=status.HTTP_200_OK)
async def revocar_todas_las_sesiones(
    usuario_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forzar logout total de un usuario (cierra todas sus sesiones activas)."""
    if not _puede_ver_sesiones_de(current_user, usuario_id):
        await require_permiso("sesiones", "delete")(user=current_user, db=db)

    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    activos = (
        await db.execute(
            select(Token).where(
                Token.usuario_id == usuario_id,
                Token.revocado == False,
            )
        )
    ).scalars().all()
    for t in activos:
        t.revocado = True
    await db.commit()
    return {"revocados": len(activos), "usuario_id": usuario_id}
