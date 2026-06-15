from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE

from schemas.mongo_tracking import GeocercaIn

COLLECTION = "geocercas"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("geometry", GEOSPHERE)], name="ix_geocercas_geometry")
    await coll.create_index([("ruta_id", ASCENDING), ("activa", ASCENDING)], name="ix_geocercas_ruta_activa")


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def crear(db: AsyncIOMotorDatabase, geocerca: GeocercaIn) -> Dict[str, Any]:
    doc = {
        "ruta_id": geocerca.ruta_id,
        "orden_id": geocerca.orden_id,
        "tipo": geocerca.tipo,
        "geometry": {"type": "Polygon", "coordinates": geocerca.coordinates},
        "tolerance_m": geocerca.tolerance_m,
        "activa": geocerca.activa,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def crear_desde_geometry(
    db: AsyncIOMotorDatabase,
    ruta_id: int,
    orden_id: int,
    geometry: Dict[str, Any],
    tolerance_m: int,
    tipo: str = "ruta_buffer",
) -> Dict[str, Any]:
    doc = {
        "ruta_id": ruta_id,
        "orden_id": orden_id,
        "tipo": tipo,
        "geometry": geometry,
        "tolerance_m": tolerance_m,
        "activa": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def listar(
    db: AsyncIOMotorDatabase,
    ruta_id: Optional[int] = None,
    activa: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if ruta_id is not None:
        query["ruta_id"] = ruta_id
    if activa is not None:
        query["activa"] = activa
    cursor = db[COLLECTION].find(query).sort("created_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def contiene_punto(db: AsyncIOMotorDatabase, lon: float, lat: float) -> List[Dict[str, Any]]:
    query = {
        "activa": True,
        "geometry": {
            "$geoIntersects": {
                "$geometry": {"type": "Point", "coordinates": [lon, lat]}
            }
        },
    }
    cursor = db[COLLECTION].find(query)
    return [_serialize(doc) async for doc in cursor]


async def desactivar(db: AsyncIOMotorDatabase, geocerca_id: str) -> bool:
    try:
        oid = ObjectId(geocerca_id)
    except Exception:
        return False
    result = await db[COLLECTION].update_one({"_id": oid}, {"$set": {"activa": False}})
    return result.modified_count > 0


async def obtener(db: AsyncIOMotorDatabase, geocerca_id: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(geocerca_id)
    except Exception:
        return None
    doc = await db[COLLECTION].find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def actualizar(
    db: AsyncIOMotorDatabase,
    geocerca_id: str,
    update: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(geocerca_id)
    except Exception:
        return None
    if "coordinates" in update and update["coordinates"] is not None:
        update["geometry"] = {"type": "Polygon", "coordinates": update.pop("coordinates")}
    else:
        update.pop("coordinates", None)
    clean = {k: v for k, v in update.items() if v is not None}
    if not clean:
        return await obtener(db, geocerca_id)
    await db[COLLECTION].update_one({"_id": oid}, {"$set": clean})
    return await obtener(db, geocerca_id)


async def eliminar_por_ruta(db: AsyncIOMotorDatabase, ruta_id: int) -> int:
    result = await db[COLLECTION].delete_many({"ruta_id": ruta_id})
    return result.deleted_count


async def eliminar_por_asignacion(db: AsyncIOMotorDatabase, asignacion_id: int) -> int:
    result = await db[COLLECTION].delete_many({"asignacion_id": asignacion_id})
    return result.deleted_count
