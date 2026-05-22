from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING

from schemas.mongo_evidencias import EvidenciaIn

COLLECTION = "evidencias"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("incidencia_id", ASCENDING)], name="ix_evidencias_incidencia")


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def crear(
    db: AsyncIOMotorDatabase,
    incidencia_id: int,
    evidencia: EvidenciaIn,
    uploaded_by: Optional[int],
) -> Dict[str, Any]:
    doc = {
        "incidencia_id": incidencia_id,
        **evidencia.model_dump(),
        "uploaded_by": uploaded_by,
        "timestamp": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def listar_por_incidencia(db: AsyncIOMotorDatabase, incidencia_id: int) -> List[Dict[str, Any]]:
    cursor = db[COLLECTION].find({"incidencia_id": incidencia_id}).sort("timestamp", -1)
    return [_serialize(doc) async for doc in cursor]


async def obtener(db: AsyncIOMotorDatabase, evidencia_id: str) -> Optional[Dict[str, Any]]:
    try:
        oid = ObjectId(evidencia_id)
    except Exception:
        return None
    doc = await db[COLLECTION].find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def eliminar(db: AsyncIOMotorDatabase, evidencia_id: str) -> bool:
    try:
        oid = ObjectId(evidencia_id)
    except Exception:
        return False
    result = await db[COLLECTION].delete_one({"_id": oid})
    return result.deleted_count > 0


async def eliminar_por_incidencia(db: AsyncIOMotorDatabase, incidencia_id: int) -> int:
    result = await db[COLLECTION].delete_many({"incidencia_id": incidencia_id})
    return result.deleted_count
