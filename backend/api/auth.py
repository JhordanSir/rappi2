import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
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
from schemas.auth import (
    GoogleLoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from schemas.common import MessageResponse
from schemas.usuarios import UsuarioResponse
from services.google_oauth import verify_google_id_token

router = APIRouter(prefix="/auth", tags=["auth"])


async def _get_rol_default(db: AsyncSession, nombre: str = "Cliente") -> Rol:
    result = await db.execute(select(Rol).where(Rol.nombre == nombre))
    rol = result.scalar_one_or_none()
    if rol is None:
        raise HTTPException(status_code=500, detail=f"Rol por defecto '{nombre}' no existe. Ejecuta seed_admin.")
    return rol


async def _crear_cliente_usuario(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    rol_id: int,
    nombre: Optional[str] = None,
    telefono: Optional[str] = None,
    cc_id: Optional[str] = None,
    password_hash: Optional[str] = None,
    auth_provider: str = "local",
    google_sub: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> Usuario:
    """Crea la ficha Cliente + el Usuario enlazado y los deja en la sesión (flush,
    sin commit: el llamador controla la transacción). Compartido por /register y /google."""
    cliente = Cliente(nombre=nombre or username, email=email, telefono=telefono, cc_id=cc_id)
    db.add(cliente)
    await db.flush()

    usuario = Usuario(
        username=username,
        email=email,
        password_hash=password_hash,
        rol_id=rol_id,
        cliente_id=cliente.id,
        auth_provider=auth_provider,
        google_sub=google_sub,
        avatar_url=avatar_url,
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def _generar_username(db: AsyncSession, email: str) -> str:
    """Deriva un username único (<=50) a partir del email para usuarios de Google."""
    base = re.sub(r"[^a-z0-9_.]", "", email.split("@")[0].lower())[:40] or "user"
    candidate = base
    i = 0
    while (
        await db.execute(select(Usuario.id).where(Usuario.username == candidate))
    ).scalar_one_or_none() is not None:
        i += 1
        candidate = f"{base}{i}"
    return candidate[:50]


async def _emitir_token_pair(db: AsyncSession, user: Usuario) -> TokenPair:
    """Genera access token + refresh token (persistido) para el usuario. No hace commit."""
    access_token, _ = create_access_token(user.id, user.rol_id, user.username)
    raw_refresh, hashed_refresh, expires_at = create_refresh_token()
    db.add(Token(usuario_id=user.id, token=hashed_refresh, fecha_expiracion=expires_at))
    return TokenPair(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


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

    usuario = await _crear_cliente_usuario(
        db,
        username=payload.username,
        email=payload.email,
        rol_id=rol.id,
        nombre=payload.nombre,
        telefono=payload.telefono,
        cc_id=payload.cc_id,
        password_hash=hash_password(payload.password),
    )
    await db.commit()

    result = await db.execute(
        select(Usuario).options(selectinload(Usuario.rol).selectinload(Rol.permisos)).where(Usuario.id == usuario.id)
    )
    return result.scalar_one()


@router.post("/login", response_model=TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).where(Usuario.username == form.username))
    user = result.scalar_one_or_none()
    # password_hash puede ser None en cuentas solo-Google: esas no pueden entrar por contraseña.
    if not user or not user.password_hash or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    token_pair = await _emitir_token_pair(db, user)
    await db.commit()
    return token_pair


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

    token_pair = await _emitir_token_pair(db, user)
    await db.commit()
    return token_pair


@router.post("/google", response_model=TokenPair)
async def google_login(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    if not settings.google_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Login con Google no disponible")

    try:
        # La verificación hace I/O de red (certs de Google) y es síncrona.
        idinfo = await run_in_threadpool(verify_google_id_token, payload.credential)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de Google inválido")

    if not idinfo.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El email de Google no está verificado")

    google_sub = idinfo["sub"]
    email = idinfo["email"]
    nombre = idinfo.get("name") or email.split("@")[0]
    avatar = idinfo.get("picture")

    # 1) Cuenta ya vinculada por google_sub.
    user = (await db.execute(select(Usuario).where(Usuario.google_sub == google_sub))).scalar_one_or_none()

    # 2) Vincular a una cuenta existente por email verificado.
    if user is None:
        user = (await db.execute(select(Usuario).where(Usuario.email == email))).scalar_one_or_none()
        if user is not None:
            user.google_sub = google_sub
            user.auth_provider = "google"
            if not user.avatar_url:
                user.avatar_url = avatar

    # 3) Crear cuenta nueva. El rol se decide por la allowlist GOOGLE_ROLE_MAP
    #    (operador): emails no listados nacen como "Cliente".
    if user is None:
        rol_nombre = settings.google_role_map.get(email.lower(), "Cliente")
        rol = await _get_rol_default(db, rol_nombre)
        username = await _generar_username(db, email)
        if rol_nombre == "Cliente":
            # Cliente (autoservicio): crea su ficha y enlaza cliente_id.
            user = await _crear_cliente_usuario(
                db,
                username=username,
                email=email,
                rol_id=rol.id,
                nombre=nombre,
                password_hash=None,
                auth_provider="google",
                google_sub=google_sub,
                avatar_url=avatar,
            )
        else:
            # Staff/Conductor: sin ficha de Cliente (cliente_id NULL) para que el
            # ruteo por rol lo lleve a su panel y no a la experiencia de Cliente.
            user = Usuario(
                username=username,
                email=email,
                password_hash=None,
                rol_id=rol.id,
                cliente_id=None,
                auth_provider="google",
                google_sub=google_sub,
                avatar_url=avatar,
            )
            db.add(user)
            await db.flush()

    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    token_pair = await _emitir_token_pair(db, user)
    await db.commit()
    return token_pair


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
