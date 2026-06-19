"""Crea roles base, permisos comodin para Admin, los permisos base de cada rol
(Despachador / Conductor / Cliente) y el usuario admin/admin123.

Es idempotente: solo agrega lo que falte (nunca borra permisos), por lo que es
seguro ejecutarlo en cada arranque de produccion."""
import asyncio

from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from core.database import AsyncSessionLocal
from core.security import hash_password
from models.roles import Permiso, Rol
from models.usuarios import Usuario

ROLES = ["Admin", "Despachador", "Conductor", "Cliente"]

# Permisos base por rol (recurso, accion). La propiedad de fila (ownership) se
# impone aparte en los endpoints: el cliente solo opera SUS datos, el conductor
# solo SUS asignaciones. Estos permisos solo habilitan la capacidad.
BASE_PERMISOS: dict[str, list[tuple[str, str]]] = {
    "Despachador": (
        [
            (r, a)
            for r in [
                "ordenes", "asignaciones", "rutas", "tracking", "clientes",
                "conductores", "vehiculos", "incidencias", "geocercas",
            ]
            for a in ["read", "write"]
        ]
        + [
            ("reportes", "read"), ("pagos", "read"), ("facturas", "read"),
            ("entregas", "read"), ("calificaciones", "read"), ("notificaciones", "read"),
        ]
    ),
    "Conductor": [
        ("tracking", "read"), ("tracking", "write"),
        ("ordenes", "read"),
        ("asignaciones", "read"), ("asignaciones", "write"),
        ("rutas", "read"), ("rutas", "write"),
        ("incidencias", "read"), ("incidencias", "write"),
        ("entregas", "read"), ("entregas", "write"),
        ("conductores", "read"),
        ("calificaciones", "read"),
        ("notificaciones", "read"),
    ],
    "Cliente": [
        ("ordenes", "read"), ("ordenes", "write"),
        ("tracking", "read"),
        ("pagos", "read"), ("pagos", "write"),
        ("clientes", "read"), ("clientes", "write"),
        ("incidencias", "read"), ("incidencias", "write"),
        ("calificaciones", "read"), ("calificaciones", "write"),
        ("facturas", "read"),
        ("notificaciones", "read"),
    ],
}


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

        # Admin: permiso comodin *:*
        admin_rol = roles["Admin"]
        await _ensure_permisos(db, admin_rol, [("*", "*")])

        # Permisos base del resto de roles
        for nombre, pares in BASE_PERMISOS.items():
            if nombre in roles:
                await _ensure_permisos(db, roles[nombre], pares)

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

        print("Seed completado: roles, permisos base por rol y usuario admin/admin123")


if __name__ == "__main__":
    asyncio.run(main())
