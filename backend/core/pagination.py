"""Paginación y ordenamiento server-side reutilizables para los listados.

Mantiene el body de la respuesta como una lista simple (sin envoltorio) y publica
el total de registros que coinciden con el filtro en el header `X-Total-Count`,
para que el frontend pueda construir los controles de paginación sin cambiar la
forma de los datos que ya consume.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

TOTAL_HEADER = "X-Total-Count"


def ordenar(
    stmt: Select,
    orden_por: Optional[str],
    direccion: Optional[str],
    mapa: Dict[str, Any],
    por_defecto: Any = None,
) -> Select:
    """Aplica ordenamiento server-side con whitelist (clic en cabecera "estilo Excel").

    `mapa` define los campos ordenables del endpoint (nombre público → columna).
    Sin `orden_por` se usa `por_defecto` (o nada). Campo fuera del whitelist → 422
    (evita ordenar por columnas arbitrarias). `direccion`: asc (default) | desc.
    """
    if not orden_por:
        return stmt.order_by(por_defecto) if por_defecto is not None else stmt
    columna = mapa.get(orden_por)
    if columna is None:
        raise HTTPException(
            status_code=422,
            detail=f"orden_por inválido: '{orden_por}'. Válidos: {', '.join(sorted(mapa))}",
        )
    if direccion not in (None, "asc", "desc"):
        raise HTTPException(status_code=422, detail="dir debe ser 'asc' o 'desc'")
    return stmt.order_by(columna.desc() if direccion == "desc" else columna.asc())


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
