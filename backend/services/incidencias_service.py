"""Lógica de incidencias: derivación de severidad por tipo y creación automática.

El chofer ya no fija la severidad: reporta solo el tipo (+ nota/foto). El sistema deriva
la severidad por tipo, y el admin puede ajustarla luego. Además el sistema crea
incidencias automáticas (p.ej. desvío de ruta) sin intervención del chofer.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.incidencias import Incidencia

TIPO_DESVIO = "Desvío de ruta"

# Severidad sugerida por tipo (1=leve … 5=crítica). El admin puede ajustarla.
SEVERIDAD_POR_TIPO: dict[str, int] = {
    "Retraso por tráfico": 2,
    "Clima adverso": 2,
    "Dirección incorrecta": 3,
    "Cliente ausente": 3,
    "Daño en paquete": 4,
    TIPO_DESVIO: 4,
}
SEVERIDAD_DEFAULT = 3

# Ventana anti-spam para no crear una incidencia de desvío en cada ping fuera de ruta.
DEDUP_DESVIO_MIN = 10


def derivar_severidad(tipo: str) -> int:
    return SEVERIDAD_POR_TIPO.get(tipo, SEVERIDAD_DEFAULT)


async def crear_incidencia_desvio(db: AsyncSession, asignacion_id: int) -> Incidencia | None:
    """Crea una incidencia automática de desvío para la asignación, salvo que ya
    exista una reciente (anti-spam). Devuelve la incidencia creada o None."""
    limite = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_DESVIO_MIN)
    reciente = (
        await db.execute(
            select(Incidencia.id).where(
                Incidencia.asignacion_id == asignacion_id,
                Incidencia.tipo == TIPO_DESVIO,
                Incidencia.origen == "automatica",
                Incidencia.fecha >= limite,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if reciente is not None:
        return None
    inc = Incidencia(
        asignacion_id=asignacion_id,
        tipo=TIPO_DESVIO,
        severidad=derivar_severidad(TIPO_DESVIO),
        origen="automatica",
        notas="Detección automática: el conductor salió del corredor de la ruta.",
    )
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return inc
