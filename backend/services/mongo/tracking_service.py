from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, GEOSPHERE

from schemas.mongo_tracking import GPSPingIn

COLLECTION = "gps_tracking"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("location", GEOSPHERE)], name="ix_gps_location")
    await coll.create_index([("asignacion_id", ASCENDING), ("timestamp", DESCENDING)], name="ix_gps_asignacion_ts")


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def crear_ping(db: AsyncIOMotorDatabase, ping: GPSPingIn) -> Dict[str, Any]:
    ts = ping.timestamp or datetime.now(timezone.utc)
    doc = {
        "asignacion_id": ping.asignacion_id,
        "conductor_id": ping.conductor_id,
        "vehiculo_placa": ping.vehiculo_placa,
        "location": {"type": "Point", "coordinates": [ping.lon, ping.lat]},
        "speed_kmh": ping.speed_kmh,
        "heading": ping.heading,
        "accuracy_m": ping.accuracy_m,
        "timestamp": ts,
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def listar_por_asignacion(
    db: AsyncIOMotorDatabase,
    asignacion_id: int,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {"asignacion_id": asignacion_id}
    rango: Dict[str, Any] = {}
    if desde is not None:
        rango["$gte"] = desde
    if hasta is not None:
        rango["$lte"] = hasta
    if rango:
        query["timestamp"] = rango
    cursor = db[COLLECTION].find(query).sort("timestamp", DESCENDING).limit(limit)
    return [_serialize(doc) async for doc in cursor]


async def ultimo_ping(db: AsyncIOMotorDatabase, asignacion_id: int) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION].find_one({"asignacion_id": asignacion_id}, sort=[("timestamp", DESCENDING)])
    return _serialize(doc) if doc else None


async def eliminar_por_asignacion(db: AsyncIOMotorDatabase, asignacion_id: int) -> int:
    result = await db[COLLECTION].delete_many({"asignacion_id": asignacion_id})
    return result.deleted_count


async def conductores_cerca(
    db: AsyncIOMotorDatabase,
    lon: float,
    lat: float,
    max_distance_m: int = 2000,
    ventana_minutos: int = 5,
) -> List[Dict[str, Any]]:
    """Devuelve el ultimo ping de conductores cuyo ping mas reciente este dentro del radio y ventana."""
    from datetime import timedelta
    desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_minutos)
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lon, lat]},
                "distanceField": "distance_m",
                "maxDistance": max_distance_m,
                "spherical": True,
                "query": {"timestamp": {"$gte": desde}},
            }
        },
        {"$sort": {"conductor_id": 1, "timestamp": -1}},
        {
            "$group": {
                "_id": "$conductor_id",
                "ultimo_ping_id": {"$first": "$_id"},
                "asignacion_id": {"$first": "$asignacion_id"},
                "vehiculo_placa": {"$first": "$vehiculo_placa"},
                "location": {"$first": "$location"},
                "speed_kmh": {"$first": "$speed_kmh"},
                "timestamp": {"$first": "$timestamp"},
                "distance_m": {"$first": "$distance_m"},
            }
        },
        {"$sort": {"distance_m": 1}},
    ]
    return [
        {"conductor_id": d["_id"], **{k: v for k, v in d.items() if k != "_id"}, "ultimo_ping_id": str(d["ultimo_ping_id"])}
        async for d in db[COLLECTION].aggregate(pipeline)
    ]


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distancia haversine en metros entre dos puntos (lon, lat)."""
    import math
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def estadisticas_asignacion(
    db: AsyncIOMotorDatabase,
    asignacion_id: int,
) -> Dict[str, Any]:
    """Recorre los pings de una asignacion y calcula distancia total, duracion, velocidad promedio."""
    cursor = db[COLLECTION].find({"asignacion_id": asignacion_id}).sort("timestamp", 1)
    pings: List[Dict[str, Any]] = [doc async for doc in cursor]
    if not pings:
        return {
            "asignacion_id": asignacion_id,
            "pings": 0,
            "distancia_total_m": 0.0,
            "duracion_segundos": 0.0,
            "velocidad_promedio_kmh": None,
            "primer_ping": None,
            "ultimo_ping": None,
        }
    distancia = 0.0
    prev = None
    for p in pings:
        coords = p["location"]["coordinates"]
        if prev is not None:
            distancia += _haversine_m(prev[0], prev[1], coords[0], coords[1])
        prev = coords
    duracion = (pings[-1]["timestamp"] - pings[0]["timestamp"]).total_seconds()
    vel_prom = (distancia / 1000.0) / (duracion / 3600.0) if duracion > 0 else None
    return {
        "asignacion_id": asignacion_id,
        "pings": len(pings),
        "distancia_total_m": round(distancia, 2),
        "distancia_total_km": round(distancia / 1000.0, 3),
        "duracion_segundos": duracion,
        "duracion_minutos": round(duracion / 60.0, 2),
        "velocidad_promedio_kmh": round(vel_prom, 2) if vel_prom else None,
        "primer_ping": pings[0]["timestamp"],
        "ultimo_ping": pings[-1]["timestamp"],
    }
