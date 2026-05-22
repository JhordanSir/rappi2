from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_current_user, require_permiso
from core.database import get_db
from models.usuarios import Token, Usuario
from schemas.auth import TokenInfo

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("/", response_model=list[TokenInfo])
async def list_tokens(
    usuario_id: int | None = None,
    revocado: bool | None = None,
    activos: bool | None = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("tokens", "read")),
):
    """Lista refresh tokens (sesiones). `activos=true` filtra los no revocados y no expirados."""
    stmt = select(Token)
    if usuario_id is not None:
        stmt = stmt.where(Token.usuario_id == usuario_id)
    if revocado is not None:
        stmt = stmt.where(Token.revocado == revocado)
    if activos:
        stmt = stmt.where(Token.revocado == False, Token.fecha_expiracion > datetime.now(timezone.utc))
    stmt = stmt.order_by(Token.fecha_expiracion.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/mias", response_model=list[TokenInfo])
async def list_mis_tokens(
    activos_solo: bool = True,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sesiones del usuario autenticado (sin necesitar permiso tokens:read)."""
    stmt = select(Token).where(Token.usuario_id == current_user.id)
    if activos_solo:
        stmt = stmt.where(Token.revocado == False, Token.fecha_expiracion > datetime.now(timezone.utc))
    stmt = stmt.order_by(Token.fecha_expiracion.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revocar_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("tokens", "delete")),
):
    token = await db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    token.revocado = True
    await db.commit()


@router.delete("/usuario/{usuario_id}", status_code=status.HTTP_200_OK)
async def revocar_todos_de_usuario(
    usuario_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("tokens", "delete")),
):
    """Forzar logout de un usuario: revoca todos sus refresh tokens activos."""
    usuario = await db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    result = await db.execute(
        select(func.count())
        .select_from(Token)
        .where(Token.usuario_id == usuario_id, Token.revocado == False)
    )
    count = result.scalar() or 0
    stmt = (
        select(Token).where(Token.usuario_id == usuario_id, Token.revocado == False)
    )
    rows = (await db.execute(stmt)).scalars().all()
    for t in rows:
        t.revocado = True
    await db.commit()
    return {"revocados": count, "usuario_id": usuario_id}
