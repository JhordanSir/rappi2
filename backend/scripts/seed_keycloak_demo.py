"""Asegura en Keycloak TODOS los usuarios demo del seed local (password `demo123`).

Idempotente: para cada usuario local `*@demo.rappi2.com` (creados por scripts.seed_demo)
garantiza su cuenta en Keycloak con el mismo username/email, rol correcto, habilitada y
con contraseña demo123. Si el username ya existía con OTRO email (p. ej. el
`conductor1@rappi2.com` de realms antiguos), se alinea el email al del seed para que el
enlace por email de provisioning funcione y el login caiga sobre su ficha demo.

Uso (local y una vez en producción):
    docker compose exec api python -m scripts.seed_keycloak_demo
"""
import asyncio

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.database import AsyncSessionLocal
from models.usuarios import Usuario
from services import keycloak_admin

DEMO_DOMAIN = "demo.rappi2.com"
DEMO_PASSWORD = "demo123"


async def _asegurar(usuario: Usuario) -> str:
    rol = usuario.rol.nombre if usuario.rol is not None else "Cliente"
    existente = await keycloak_admin.buscar_por_username(usuario.username)
    if existente is None:
        await keycloak_admin.crear_usuario(usuario.username, usuario.email, DEMO_PASSWORD, rol)
        return f"creado (rol {rol})"
    sub = existente["id"]
    resultado = "ya existía"
    if (existente.get("email") or "").lower() != usuario.email.lower() or not existente.get("enabled", True):
        await keycloak_admin.actualizar(sub, email=usuario.email, enabled=True)
        resultado = "email/estado alineado"
    # Password y rol siempre re-asegurados (idempotente; el demo debe ser predecible).
    await keycloak_admin.reset_password(sub, DEMO_PASSWORD)
    await keycloak_admin.asignar_rol(sub, rol)
    return resultado


async def main() -> None:
    async with AsyncSessionLocal() as db:
        usuarios = (
            await db.execute(
                select(Usuario)
                .options(selectinload(Usuario.rol))
                .where(Usuario.email.like(f"%@{DEMO_DOMAIN}"))
                .order_by(Usuario.id)
            )
        ).scalars().all()
    if not usuarios:
        print("No hay usuarios demo locales. Corre primero: python -m scripts.seed_demo")
        return
    print(f"Asegurando {len(usuarios)} usuarios demo en Keycloak (password: {DEMO_PASSWORD})…")
    for u in usuarios:
        resultado = await _asegurar(u)
        print(f"  {u.username:<14} {u.email:<34} → {resultado}")
    print("Listo: cualquier usuario demo (p. ej. conductor2 / demo123) ya puede iniciar sesión.")


if __name__ == "__main__":
    asyncio.run(main())
