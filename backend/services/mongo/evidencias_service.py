from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorGridFSBucket
from pymongo import ASCENDING

COLLECTION = "evidencias"
GRIDFS_BUCKET = "evidencias_files"


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    coll = db[COLLECTION]
    await coll.create_index([("incidencia_id", ASCENDING)], name="ix_evidencias_incidencia")
    await coll.create_index([("archivos.file_id", ASCENDING)], name="ix_evidencias_file_id")


def _bucket(db: AsyncIOMotorDatabase) -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)


def _serialize(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    doc.setdefault("urls", [])
    doc.setdefault("archivos", [])
    return doc


async def crear_con_archivos(
    db: AsyncIOMotorDatabase,
    incidencia_id: int,
    archivos: List[UploadFile],
    tipo: str,
    descripcion: Optional[str],
    uploaded_by: Optional[int],
) -> Dict[str, Any]:
    from services.imaging import comprimir_imagen

    bucket = _bucket(db)
    refs: List[Dict[str, Any]] = []
    for upload in archivos:
        contenido = await upload.read()
        if not contenido:
            continue
        contenido, ctype, fname = comprimir_imagen(contenido, upload.content_type, upload.filename or "evidencia")
        file_id = await bucket.upload_from_stream(
            fname,
            contenido,
            metadata={
                "content_type": ctype,
                "incidencia_id": incidencia_id,
                "uploaded_by": uploaded_by,
            },
        )
        refs.append(
            {
                "file_id": str(file_id),
                "filename": fname,
                "content_type": ctype,
                "size": len(contenido),
            }
        )

    if not refs:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="No se recibieron archivos validos")

    doc = {
        "incidencia_id": incidencia_id,
        "urls": [],
        "archivos": refs,
        "tipo": tipo,
        "descripcion": descripcion,
        "uploaded_by": uploaded_by,
        "timestamp": datetime.now(timezone.utc),
    }
    result = await db[COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


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
    doc = await db[COLLECTION].find_one({"_id": oid})
    if doc is None:
        return False
    await _eliminar_archivos(db, doc.get("archivos", []))
    result = await db[COLLECTION].delete_one({"_id": oid})
    return result.deleted_count > 0


async def eliminar_por_incidencia(db: AsyncIOMotorDatabase, incidencia_id: int) -> int:
    cursor = db[COLLECTION].find({"incidencia_id": incidencia_id}, {"archivos": 1})
    async for doc in cursor:
        await _eliminar_archivos(db, doc.get("archivos", []))
    result = await db[COLLECTION].delete_many({"incidencia_id": incidencia_id})
    return result.deleted_count
