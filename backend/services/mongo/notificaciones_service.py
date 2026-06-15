from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from schemas.mongo_notificaciones import NotificacionIn

COLLECTION = "notificaciones"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index(
        [("destinatario_tipo", ASCENDING), ("destinatario_id", ASCENDING), ("fecha", DESCENDING)],
        name="ix_notif_destinatario_fecha",
    )
    await coll.create_index([("leida", ASCENDING)], name="ix_notif_leida")


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def crear(db: AsyncIOMotorDatabase, noti: NotificacionIn) -> Dict[str, Any]:
    doc = {
        **noti.model_dump(),
        "leida": False,
        "fecha": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def listar_para(
    db: AsyncIOMotorDatabase,
    destinatario_tipo: str,
    destinatario_id: int,
    leida: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {
        "destinatario_tipo": destinatario_tipo,
        "destinatario_id": destinatario_id,
    }
    if leida is not None:
        query["leida"] = leida
    cursor = db[COLLECTION].find(query).sort("fecha", DESCENDING).skip(skip).limit(limit)
    return [_serialize(doc) async for doc in cursor]


async def marcar_leida(
    db: AsyncIOMotorDatabase,
    notif_id: str,
    destinatario_tipo: str,
    destinatario_id: int,
) -> bool:
    try:
        oid = ObjectId(notif_id)
    except Exception:
        return False
    result = await db[COLLECTION].update_one(
        {"_id": oid, "destinatario_tipo": destinatario_tipo, "destinatario_id": destinatario_id},
        {"$set": {"leida": True}},
    )
    return result.modified_count > 0


async def eliminar(
    db: AsyncIOMotorDatabase,
    notif_id: str,
    destinatario_tipo: str,
    destinatario_id: int,
) -> bool:
    try:
        oid = ObjectId(notif_id)
    except Exception:
        return False
    result = await db[COLLECTION].delete_one(
        {"_id": oid, "destinatario_tipo": destinatario_tipo, "destinatario_id": destinatario_id}
    )
    return result.deleted_count > 0
