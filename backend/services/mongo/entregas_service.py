from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from pymongo import ASCENDING

COLLECTION = "entregas"
GRIDFS_BUCKET = "entregas_files"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("asignacion_id", ASCENDING)], name="ix_entregas_asignacion")
    await coll.create_index([("archivos.file_id", ASCENDING)], name="ix_entregas_file_id")


def _bucket(db: AsyncIOMotorDatabase) -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)


def _serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    doc.setdefault("archivos", [])
    return doc


async def crear_con_archivos(
    db: AsyncIOMotorDatabase,
    asignacion_id: int,
    archivos: List[UploadFile],
    tipo: str,
    descripcion: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    receptor: Optional[str],
    uploaded_by: Optional[int],
) -> Dict[str, Any]:
    bucket = _bucket(db)
    refs: List[Dict[str, Any]] = []
    for upload in archivos:
        contenido = await upload.read()
        if not contenido:
            continue
        file_id = await bucket.upload_from_stream(
            upload.filename or "entrega",
            contenido,
            metadata={
                "content_type": upload.content_type,
                "asignacion_id": asignacion_id,
                "uploaded_by": uploaded_by,
            },
        )
        refs.append(
            {
                "file_id": str(file_id),
                "filename": upload.filename or "entrega",
                "content_type": upload.content_type,
                "size": len(contenido),
            }
        )

    if not refs:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="No se recibieron archivos validos")

    doc = {
        "asignacion_id": asignacion_id,
        "archivos": refs,
        "tipo": tipo,
        "descripcion": descripcion,
        "lat": lat,
        "lon": lon,
        "receptor": receptor,
        "uploaded_by": uploaded_by,
        "timestamp": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def listar_por_asignacion(db: AsyncIOMotorDatabase, asignacion_id: int) -> List[Dict[str, Any]]:
    cursor = db[COLLECTION].find({"asignacion_id": asignacion_id}).sort("timestamp", -1)
    return [_serialize(doc) async for doc in cursor]


async def abrir_descarga(db: AsyncIOMotorDatabase, file_id: str):
    """Devuelve un AsyncIOMotorGridOut listo para streamear, o None si no existe."""
    try:
        oid = ObjectId(file_id)
    except Exception:
        return None
    bucket = _bucket(db)
    try:
        return await bucket.open_download_stream(oid)
    except Exception:
        return None


async def _eliminar_archivos(db: AsyncIOMotorDatabase, refs: List[Dict[str, Any]]) -> None:
    if not refs:
        return
    bucket = _bucket(db)
    for ref in refs:
        try:
            await bucket.delete(ObjectId(ref["file_id"]))
        except Exception:
            continue


async def eliminar_por_asignacion(db: AsyncIOMotorDatabase, asignacion_id: int) -> int:
    cursor = db[COLLECTION].find({"asignacion_id": asignacion_id}, {"archivos": 1})
    async for doc in cursor:
        await _eliminar_archivos(db, doc.get("archivos", []))
    result = await db[COLLECTION].delete_many({"asignacion_id": asignacion_id})
    return result.deleted_count
