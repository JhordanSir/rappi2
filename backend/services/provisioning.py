"""Aprovisionamiento de fichas especializadas (Cliente/Conductor) según el rol.

Mantiene coherente la regla del proyecto: "todo cliente o conductor debe ser un
usuario registrado", y su recíproca práctica: un usuario con rol Cliente debe tener
su ficha `Cliente` enlazada (para poder crear/pagar pedidos) y uno con rol Conductor
su registro en `conductores` (para poder ser asignado).

Lo usan la CRUD de usuarios (api/usuarios.py) al crear/cambiar de rol, el backfill y el
provisioning desde Keycloak (api/dependencies.py al validar un token).
Ninguna función hace commit: el llamador controla la transacción (se usa flush para
obtener ids).
"""
import re
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.clientes import Cliente
from models.conductores import Conductor
from models.roles import Rol
from models.usuarios import Usuario
from services.keycloak import rol_principal


async def ensure_cliente(db: AsyncSession, usuario: Usuario) -> Cliente:
    """Garantiza que el usuario tenga una ficha Cliente activa y enlazada."""
    if usuario.cliente_id is not None:
        cliente = await db.get(Cliente, usuario.cliente_id)
        if cliente is not None:
            if not cliente.activo:
                cliente.activo = True
            return cliente

    # Reusar una ficha existente con el mismo email antes de crear una nueva.
    cliente = (
        await db.execute(select(Cliente).where(Cliente.email == usuario.email))
    ).scalar_one_or_none()
    if cliente is None:
        cliente = Cliente(nombre=usuario.username, email=usuario.email)
        db.add(cliente)
        await db.flush()
    elif not cliente.activo:
        cliente.activo = True

    usuario.cliente_id = cliente.id
    return cliente


async def ensure_conductor(db: AsyncSession, usuario: Usuario) -> Conductor:
    """Garantiza que el usuario tenga un registro Conductor activo (stub si no existe)."""
    conductor = (
        await db.execute(select(Conductor).where(Conductor.usuario_id == usuario.id))
    ).scalar_one_or_none()
    if conductor is None:
        # Licencia placeholder única (el admin la completa luego en Conductores).
        conductor = Conductor(
            usuario_id=usuario.id,
            nombre=usuario.username,
            licencia=f"PEND-{usuario.id}",
            disponibilidad="Disponible",
            activo=True,
        )
        db.add(conductor)
        await db.flush()
    else:
        if not conductor.activo:
            conductor.activo = True
            conductor.disponibilidad = "Disponible"
    return conductor


async def _desactivar_conductor(db: AsyncSession, usuario: Usuario) -> None:
    conductor = (
        await db.execute(select(Conductor).where(Conductor.usuario_id == usuario.id))
    ).scalar_one_or_none()
    if conductor is not None and conductor.activo:
        conductor.activo = False
        conductor.disponibilidad = "Inactivo"


async def sincronizar_por_rol(db: AsyncSession, usuario: Usuario, rol_nombre: str | None) -> None:
    """Ajusta las fichas especializadas para que coincidan con el rol del usuario.

    Cambiar de rol NO borra la entidad anterior: se desactiva (preserva historial).
    """
    if rol_nombre == "Cliente":
        await ensure_cliente(db, usuario)
        await _desactivar_conductor(db, usuario)
    elif rol_nombre == "Conductor":
        await ensure_conductor(db, usuario)
        usuario.cliente_id = None  # desenlaza la ficha Cliente (queda sin usuario)
    else:
        # Staff (Admin): sin ficha de cliente ni conductor activo.
        usuario.cliente_id = None
        await _desactivar_conductor(db, usuario)


async def _rol_por_nombre(db: AsyncSession, nombre: str) -> Rol | None:
    rol = (await db.execute(select(Rol).where(Rol.nombre == nombre))).scalar_one_or_none()
    if rol is None and nombre != "Cliente":
        rol = (await db.execute(select(Rol).where(Rol.nombre == "Cliente"))).scalar_one_or_none()
    return rol


async def _username_unico(db: AsyncSession, base: str) -> str:
    """Deriva un username único (<=50) saneando `base`."""
    base = re.sub(r"[^a-z0-9_.]", "", (base or "").lower())[:40] or "user"
    candidate = base
    i = 0
    while (
        await db.execute(select(Usuario.id).where(Usuario.username == candidate))
    ).scalar_one_or_none() is not None:
        i += 1
        candidate = f"{base}{i}"
    return candidate[:50]


async def ensure_usuario_from_claims(db: AsyncSession, claims: Dict[str, Any]) -> Usuario:
    """Crea/enlaza el `Usuario` local que corresponde a un token de Keycloak.

    Estrategia de resolución: (1) por `keycloak_sub`; (2) por `email` (enlaza una cuenta
    pre-existente, p. ej. staff dado de alta por un admin); (3) crea una cuenta nueva. El
    rol viene del token (`realm_access.roles`) y, según el rol, se asegura la ficha
    Cliente/Conductor. No hace commit: lo hace el llamador.
    """
    sub = claims.get("sub")
    email = (claims.get("email") or "").strip().lower() or None
    nombre = claims.get("name")
    avatar = claims.get("picture")
    # El catálogo de roles de la BD hace válidos también los roles PERSONALIZADOS
    # (Despachador, Auditor…): sin esto, rol_principal degradaba a 'Cliente' a todo
    # usuario cuyo realm-role no fuera Admin/Conductor/Cliente.
    validos = set((await db.execute(select(Rol.nombre))).scalars().all())
    rol_nombre = rol_principal(claims, validos)

    rol = await _rol_por_nombre(db, rol_nombre)
    if rol is None:
        raise RuntimeError(
            f"Rol '{rol_nombre}' no existe en la BD. Ejecuta scripts.seed_admin."
        )

    # 1) por keycloak_sub
    user = (
        await db.execute(select(Usuario).where(Usuario.keycloak_sub == sub))
    ).scalar_one_or_none()

    # 2) por email (cuenta pre-existente sin Keycloak aún)
    if user is None and email:
        user = (
            await db.execute(select(Usuario).where(Usuario.email == email))
        ).scalar_one_or_none()
        if user is not None:
            user.keycloak_sub = sub
            user.auth_provider = "keycloak"

    # 3) crear
    es_nuevo = user is None
    if es_nuevo:
        base = claims.get("preferred_username") or (email.split("@")[0] if email else None) or nombre
        username = await _username_unico(db, base)
        user = Usuario(
            username=username,
            email=email or f"{username}@keycloak.local",
            password_hash=None,
            rol_id=rol.id,
            auth_provider="keycloak",
            keycloak_sub=sub,
            avatar_url=avatar,
        )
        db.add(user)
        await db.flush()

    rol_cambio = user.rol_id != rol.id
    if rol_cambio:
        user.rol_id = rol.id
    if avatar and not user.avatar_url:
        user.avatar_url = avatar

    # Solo sincronizamos fichas al crear o al cambiar de rol (evita trabajo por request).
    if es_nuevo or rol_cambio:
        await sincronizar_por_rol(db, user, rol_nombre)

    return user
