"""Paginación server-side reutilizable para los listados.

Mantiene el body de la respuesta como una lista simple (sin envoltorio) y publica
el total de registros que coinciden con el filtro en el header `X-Total-Count`,
para que el frontend pueda construir los controles de paginación sin cambiar la
forma de los datos que ya consume.
"""
from typing import Any, List

from fastapi import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

TOTAL_HEADER = "X-Total-Count"


async def paginate(
    db: AsyncSession,
    stmt: Select,
    response: Response,
    skip: int,
    limit: int,
) -> List[Any]:
    """Ejecuta `stmt` paginado y expone el total (sin paginar) en `X-Total-Count`.

    `stmt` debe venir con sus filtros y `order_by` aplicados pero SIN `offset`/`limit`:
    el total se calcula sobre la misma consulta (descartando el orden, irrelevante
    para un count) y luego se devuelve la página pedida.
    """
    total = (
        await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    response.headers[TOTAL_HEADER] = str(total)
    result = await db.execute(stmt.offset(skip).limit(limit))
    return result.scalars().all()
