"""Backfill idempotente: alinea las fichas Cliente/Conductor con el rol de cada usuario.

Repara datos historicos (P1): usuarios con rol Cliente sin `cliente_id` (no podian
crear/pagar pedidos) o con rol Conductor sin registro en `conductores`. Aplica la
misma logica que la CRUD de usuarios (services.provisioning). Seguro de re-ejecutar.

Uso (con el stack levantado):
    docker compose exec api python -m scripts.backfill_entidades
"""
import asyncio

from sqlalchemy.future import select

from core.database import AsyncSessionLocal
from models.roles import Rol
from models.usuarios import Usuario
from services.provisioning import sincronizar_por_rol


async def main() -> None:
    async with AsyncSessionLocal() as db:
        usuarios = (await db.execute(select(Usuario))).scalars().all()
        for usuario in usuarios:
            rol = await db.get(Rol, usuario.rol_id)
            await sincronizar_por_rol(db, usuario, rol.nombre if rol else None)
        await db.commit()
        print(f"Backfill completado: {len(usuarios)} usuarios revisados y sincronizados.")


if __name__ == "__main__":
    asyncio.run(main())
