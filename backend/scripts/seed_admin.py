"""Siembra los roles base y sus permisos en PostgreSQL.

Con Keycloak como proveedor de identidad, los USUARIOS y la ASIGNACIÓN de roles viven
en Keycloak (no se crea aquí ningún usuario/contraseña). Esta tabla `roles` se conserva
como lookup para el FK `usuarios.rol_id` y `user.rol.nombre`, y la tabla `permisos` se
siembra desde `core.permisos.ROLE_PERMISOS` (única fuente de verdad) para que `/auth/me`
las devuelva y el frontend pueda mostrar/ocultar UI con `can()`.

La autorización efectiva del backend deriva del rol del token (core.permisos.tiene_permiso),
no de una lectura de esta tabla.

Es idempotente: solo agrega lo que falte (nunca borra), seguro en cada arranque.
"""
import asyncio

from sqlalchemy.future import select

from core.database import AsyncSessionLocal
from core.permisos import ROLE_PERMISOS
from models.roles import Permiso, Rol

ROLES = ["Admin", "Conductor", "Cliente"]


async def _ensure_permisos(db, rol: Rol, pares: list[tuple[str, str]]) -> None:
    """Agrega los permisos que falten para el rol (no borra los existentes)."""
    existentes = {
        (p.recurso, p.accion)
        for p in (await db.execute(select(Permiso).where(Permiso.rol_id == rol.id))).scalars().all()
    }
    nuevos = [par for par in pares if par not in existentes]
    for recurso, accion in nuevos:
        db.add(Permiso(rol_id=rol.id, recurso=recurso, accion=accion))
    if nuevos:
        await db.commit()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for nombre in ROLES:
            existente = (await db.execute(select(Rol).where(Rol.nombre == nombre))).scalar_one_or_none()
            if existente is None:
                db.add(Rol(nombre=nombre))
        await db.commit()

        roles = {r.nombre: r for r in (await db.execute(select(Rol))).scalars().all()}

        # Permisos por rol desde la fuente de verdad compartida (core.permisos).
        for nombre, pares in ROLE_PERMISOS.items():
            if nombre in roles:
                await _ensure_permisos(db, roles[nombre], pares)

        print("Seed completado: roles base (Admin/Conductor/Cliente) y sus permisos.")


if __name__ == "__main__":
    asyncio.run(main())
