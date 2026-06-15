import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

COLLECTION = "auditoria"
RETENCION_SEGUNDOS = 90 * 24 * 60 * 60  # 90 dias

logger = logging.getLogger(__name__)


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("usuario_id", ASCENDING), ("timestamp", DESCENDING)], name="ix_audit_user_ts")
    await coll.create_index(
        [("timestamp", ASCENDING)],
        name="ix_audit_ttl",
        expireAfterSeconds=RETENCION_SEGUNDOS,
    )


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


async def registrar(
    db: AsyncIOMotorDatabase,
    usuario_id: Optional[int],
    ruta: str,
    metodo: str,
    ip: Optional[str],
    status_code: int,
    payload_hash: Optional[str] = None,
) -> None:
    try:
        await db[COLLECTION].insert_one({
            "usuario_id": usuario_id,
            "ruta": ruta,
            "metodo": metodo,
            "ip": ip,
            "status_code": status_code,
            "payload_hash": payload_hash,
            "timestamp": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning("No se pudo escribir auditoria: %s", exc)


async def buscar(
    db: AsyncIOMotorDatabase,
    usuario_id: Optional[int] = None,
    metodo: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if usuario_id is not None:
        query["usuario_id"] = usuario_id
    if metodo is not None:
        query["metodo"] = metodo
    cursor = db[COLLECTION].find(query).sort("timestamp", DESCENDING).skip(skip).limit(limit)
    return [_serialize(doc) async for doc in cursor]
