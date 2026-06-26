"""Arranque idempotente para DESARROLLO: carga los datos demo SOLO si aún no están.

Se ejecuta en el comando de arranque del contenedor (docker-compose.override.yml),
después de `alembic upgrade head` y de `scripts.seed_admin`. Comportamiento:

- Si la base NO tiene datos demo (no hay clientes ``@demo.rappi2.com``), corre
  ``scripts.seed_demo`` y puebla todas las tablas.
- Si YA hay datos demo, no hace nada: así un reinicio del contenedor NO borra lo
  que creaste mientras experimentabas (el seed demo es destructivo: limpia y recarga).

Para forzar una recarga limpia en cualquier momento:
    docker compose exec api python -m scripts.seed_demo
"""
import asyncio

from sqlalchemy import func, select

from core.database import AsyncSessionLocal
from models.clientes import Cliente

DEMO_DOMAIN = "demo.rappi2.com"


async def _ya_cargado() -> bool:
    async with AsyncSessionLocal() as db:
        total = (
            await db.execute(
                select(func.count(Cliente.id)).where(Cliente.email.like(f"%@{DEMO_DOMAIN}"))
            )
        ).scalar() or 0
        return total > 0


async def main() -> None:
    if await _ya_cargado():
        print("seed_if_empty: datos demo ya presentes → se omite (usa scripts.seed_demo para recargar).")
        return
    print("seed_if_empty: base sin datos demo → cargando scripts.seed_demo…")
    from scripts.seed_demo import main as seed_demo_main

    await seed_demo_main()


if __name__ == "__main__":
    asyncio.run(main())
