from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.config import settings
from core.database import get_db
from core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from models.clientes import Cliente
from models.roles import Rol
from models.usuarios import Token, Usuario
from schemas.auth import LogoutRequest, RefreshRequest, RegisterRequest, TokenPair
from schemas.common import MessageResponse
from schemas.usuarios import UsuarioResponse

router = APIRouter(prefix="/auth", tags=["auth"])


async def _get_rol_default(db: AsyncSession, nombre: str = "Cliente") -> Rol:
    result = await db.execute(select(Rol).where(Rol.nombre == nombre))
    rol = result.scalar_one_or_none()
    if rol is None:
        raise HTTPException(status_code=500, detail=f"Rol por defecto '{nombre}' no existe. Ejecuta seed_admin.")
    return rol


@router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Usuario).where((Usuario.username == payload.username) | (Usuario.email == payload.email))
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username o email ya registrado")

    # El registro publico siempre es rol "Cliente"; se ignora cualquier rol
    # enviado por el cliente para impedir auto-asignarse Admin/Despachador.
    rol = await _get_rol_default(db, "Cliente")

    cliente = Cliente(
        nombre=payload.nombre or payload.username,
        email=payload.email,
        telefono=payload.telefono,
        cc_id=payload.cc_id,
    )
    db.add(cliente)
    await db.flush()
    cliente_id = cliente.id

    usuario = Usuario(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        rol_id=rol.id,
        cliente_id=cliente_id,
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)

    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == usuario.id)
    )
    return result.scalar_one()


@router.post("/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    access_token, _ = create_access_token(user.id, user.rol_id, user.username)
    raw_refresh, hashed_refresh, expires_at = create_refresh_token()
    db.add(Token(usuario_id=user.id, token=hashed_refresh, fecha_expiracion=expires_at))
    await db.commit()

    return TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_token(payload.refresh_token)
    result = await db.execute(select(Token).where(Token.token == hashed))
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.revocado:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")
    expira = token_row.fecha_expiracion
    if expira.tzinfo is None:
        expira = expira.replace(tzinfo=timezone.utc)
    if expira < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")

    user_result = await db.execute(select(Usuario).where(Usuario.id == token_row.usuario_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invalido")

    token_row.revocado = True

    access_token, _ = create_access_token(user.id, user.rol_id, user.username)
    raw_refresh, hashed_refresh, expires_at = create_refresh_token()
    db.add(Token(usuario_id=user.id, token=hashed_refresh, fecha_expiracion=expires_at))
    await db.commit()

    return TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_token(payload.refresh_token)
    result = await db.execute(select(Token).where(Token.token == hashed))
    token_row = result.scalar_one_or_none()
    if token_row and not token_row.revocado:
        token_row.revocado = True
        await db.commit()
    return MessageResponse(message="Logout exitoso")


@router.get("/me", response_model=UsuarioResponse)
async def me(current_user: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == current_user.id)
    )
    return result.scalar_one()
