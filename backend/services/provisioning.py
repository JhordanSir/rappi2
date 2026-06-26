"""Aprovisionamiento de fichas especializadas (Cliente/Conductor) según el rol.

Mantiene coherente la regla del proyecto: "todo cliente o conductor debe ser un
usuario registrado", y su recíproca práctica: un usuario con rol Cliente debe tener
su ficha `Cliente` enlazada (para poder crear/pagar pedidos) y uno con rol Conductor
su registro en `conductores` (para poder ser asignado).

Lo usan la CRUD de usuarios (api/usuarios.py) al crear/cambiar de rol, y el backfill.
Ninguna función hace commit: el llamador controla la transacción (se usa flush para
obtener ids).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.clientes import Cliente
from models.conductores import Conductor
from models.usuarios import Usuario


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
