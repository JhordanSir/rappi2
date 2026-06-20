"""Plaqueo de Arequipa: restricción de circulación por placa en el centro histórico.

Por día (hora local) no pueden circular los vehículos cuya placa termina en:
  lunes 0–1 · martes 2–3 · miércoles 4–5 · jueves 6–7 · viernes 8–9 · fin de semana: libre.

La restricción aplica solo si la RUTA de la orden cruza una zona de tipo
'restriccion_vehicular' (geocerca editable por el admin), evaluada con la fecha de la
entrega (programada o, si es inmediata, hoy).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.destinos import Destino
from models.rutas import RutaPlanificada
from services.pricing_service import ZONA_LOCAL

# weekday(): lunes=0 … domingo=6. Dígitos restringidos por día.
RESTRICCION_POR_DIA: dict[int, set[int]] = {
    0: {0, 1}, 1: {2, 3}, 2: {4, 5}, 3: {6, 7}, 4: {8, 9},
}
_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def ultimo_digito(placa: str | None) -> int | None:
    for ch in reversed(placa or ""):
        if ch.isdigit():
            return int(ch)
    return None


def _local(cuando: datetime | None) -> datetime:
    cuando = cuando or datetime.now(timezone.utc)
    if cuando.tzinfo is None:
        cuando = cuando.replace(tzinfo=timezone.utc)
    return cuando.astimezone(ZONA_LOCAL)


def dia_nombre(cuando: datetime | None) -> str:
    return _DIAS[_local(cuando).weekday()]


def placa_restringida(placa: str | None, cuando: datetime | None) -> bool:
    """True si la placa no puede circular ese día (sin considerar la zona)."""
    dig = ultimo_digito(placa)
    if dig is None:
        return False
    return dig in RESTRICCION_POR_DIA.get(_local(cuando).weekday(), set())


async def _geom_de_orden(db: AsyncSession, orden) -> dict | None:
    """Geometría a evaluar: la ruta por calles si existe; si no, los puntos de la orden."""
    ruta = (
        await db.execute(
            select(RutaPlanificada).where(RutaPlanificada.orden_id == orden.id).order_by(RutaPlanificada.id.desc())
        )
    ).scalars().first()
    if ruta and ruta.geometria and ruta.geometria.get("coordinates"):
        return ruta.geometria
    pts: list[list[float]] = []
    if orden.lon_origen is not None and orden.lat_origen is not None:
        pts.append([float(orden.lon_origen), float(orden.lat_origen)])
    destinos = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalars().all()
    for d in destinos:
        if d.lon is not None and d.lat is not None:
            pts.append([float(d.lon), float(d.lat)])
    if not pts:
        return None
    return {"type": "MultiPoint", "coordinates": pts}


async def ruta_cruza_restriccion(mongo_db, geometry: dict | None) -> bool:
    """True si la geometría cruza alguna zona activa de restricción vehicular."""
    if not geometry:
        return False
    q = {
        "tipo": "restriccion_vehicular",
        "activa": True,
        "geometry": {"$geoIntersects": {"$geometry": geometry}},
    }
    return await mongo_db["geocercas"].count_documents(q) > 0


async def punto_en_restriccion(mongo_db, lon: float, lat: float) -> bool:
    return await ruta_cruza_restriccion(mongo_db, {"type": "Point", "coordinates": [lon, lat]})


async def zonas_restriccion(mongo_db) -> list[list[list[float]]]:
    """Anillos exteriores [lon,lat] de las zonas de restricción activas (para rebordear)."""
    rings: list[list[list[float]]] = []
    async for doc in mongo_db["geocercas"].find({"tipo": "restriccion_vehicular", "activa": True}):
        coords = (doc.get("geometry") or {}).get("coordinates") or []
        if coords:
            rings.append(coords[0])
    return rings


async def _puntos_orden(db: AsyncSession, orden) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    if orden.lon_origen is not None and orden.lat_origen is not None:
        pts.append((float(orden.lon_origen), float(orden.lat_origen)))
    destinos = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalars().all()
    for d in destinos:
        if d.lon is not None and d.lat is not None:
            pts.append((float(d.lon), float(d.lat)))
    return pts


async def evaluar_asignacion(db: AsyncSession, mongo_db, ordenes: list, placa: str | None) -> dict:
    """Decide el plaqueo al asignar un vehículo:
      - bloquear: hay un punto (recojo/entrega) DENTRO de la zona en un día restringido
        (inevitable, no se puede entrar) → la asignación se rechaza.
      - reroute: la placa está restringida y la ruta CRUZA la zona pero los puntos están
        fuera → se puede rebordear; la ruta se reconstruye evitando la zona.
    """
    if ultimo_digito(placa) is None:
        return {"bloquear": None, "reroute": False}
    reroute = False
    for orden in ordenes:
        cuando = orden.programado_para or datetime.now(timezone.utc)
        if not placa_restringida(placa, cuando):
            continue
        for lon, lat in await _puntos_orden(db, orden):
            if await punto_en_restriccion(mongo_db, lon, lat):
                return {"bloquear": {"orden_id": orden.id, "placa": placa, "digito": ultimo_digito(placa), "dia": dia_nombre(cuando)}, "reroute": False}
        if await ruta_cruza_restriccion(mongo_db, await _geom_de_orden(db, orden)):
            reroute = True
    return {"bloquear": None, "reroute": reroute}


async def fechas_con_cruce(db: AsyncSession, mongo_db, ordenes: list) -> list[datetime]:
    """Fechas de entrega de las órdenes cuya ruta cruza una zona de restricción
    (independiente de la placa). Sirve para evaluar candidatos en la sugerencia."""
    fechas: list[datetime] = []
    for orden in ordenes:
        if await ruta_cruza_restriccion(mongo_db, await _geom_de_orden(db, orden)):
            fechas.append(orden.programado_para or datetime.now(timezone.utc))
    return fechas


async def evaluar_run(db: AsyncSession, mongo_db, ordenes: list, placa: str | None) -> dict | None:
    """Evalúa el plaqueo para un conjunto de órdenes (un run) y una placa. Devuelve
    info de la primera orden restringida (placa bloqueada ese día + ruta que cruza la
    zona), o None si el run puede circular."""
    dig = ultimo_digito(placa)
    if dig is None:
        return None
    for orden in ordenes:
        cuando = orden.programado_para or datetime.now(timezone.utc)
        if not placa_restringida(placa, cuando):
            continue
        if await ruta_cruza_restriccion(mongo_db, await _geom_de_orden(db, orden)):
            return {"orden_id": orden.id, "placa": placa, "digito": dig, "dia": dia_nombre(cuando)}
    return None
