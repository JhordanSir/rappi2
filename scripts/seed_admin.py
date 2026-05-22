"""Crea roles base, permisos comodin para Admin y usuario admin/admin123."""
import asyncio

from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from core.database import AsyncSessionLocal
from core.security import hash_password
from models.roles import Permiso, Rol
from models.usuarios import Usuario

ROLES = ["Admin", "Despachador", "Conductor", "Cliente"]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for nombre in ROLES:
            existente = (await db.execute(select(Rol).where(Rol.nombre == nombre))).scalar_one_or_none()
            if existente is None:
                db.add(Rol(nombre=nombre))
        await db.commit()

        admin_rol = (await db.execute(select(Rol).where(Rol.nombre == "Admin"))).scalar_one()
        existe_wildcard = (
            await db.execute(
                select(Permiso).where(Permiso.rol_id == admin_rol.id, Permiso.recurso == "*", Permiso.accion == "*")
            )
        ).scalar_one_or_none()
        if existe_wildcard is None:
            db.add(Permiso(rol_id=admin_rol.id, recurso="*", accion="*"))
            await db.commit()

        admin_user = (await db.execute(select(Usuario).where(Usuario.username == "admin"))).scalar_one_or_none()
        if admin_user is None:
            db.add(
                Usuario(
                    username="admin",
                    email="admin@rappi2.com",
                    password_hash=hash_password("admin123"),
                    rol_id=admin_rol.id,
                )
            )
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()

        print("Seed completado: roles, permiso *:* para Admin, usuario admin/admin123")


if __name__ == "__main__":
    asyncio.run(main())
