from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_mongo_db, require_permiso
from schemas.mongo_auditoria import AuditoriaOut
from services.mongo import auditoria_service

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/", response_model=list[AuditoriaOut])
async def list_auditoria(
    usuario_id: Optional[int] = None,
    metodo: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(100, le=500),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("auditoria", "read")),
):
    return await auditoria_service.buscar(mongo_db, usuario_id, metodo, skip, limit)


@router.get("/resumen")
async def resumen_auditoria(
    horas: int = Query(24, ge=1, le=720, description="Ventana en horas (1..720 = 30d)"),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("auditoria", "read")),
) -> dict[str, Any]:
    """Resumen agregado: requests por status, por metodo, top rutas, top usuarios."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    coll = mongo_db[auditoria_service.COLLECTION]
    base_match = {"timestamp": {"$gte": desde}}

    total = await coll.count_documents(base_match)

    pipeline_status = [{"$match": base_match}, {"$group": {"_id": "$status_code", "n": {"$sum": 1}}}]
    pipeline_metodo = [{"$match": base_match}, {"$group": {"_id": "$metodo", "n": {"$sum": 1}}}]
    pipeline_rutas = [
        {"$match": base_match},
        {"$group": {"_id": "$ruta", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 10},
    ]
    pipeline_usuarios = [
        {"$match": {**base_match, "usuario_id": {"$ne": None}}},
        {"$group": {"_id": "$usuario_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 10},
    ]
    pipeline_errores = [
        {"$match": {**base_match, "status_code": {"$gte": 400}}},
        {"$group": {"_id": "$status_code", "n": {"$sum": 1}}},
    ]

    by_status = {str(d["_id"]): d["n"] async for d in coll.aggregate(pipeline_status)}
    by_metodo = {d["_id"]: d["n"] async for d in coll.aggregate(pipeline_metodo)}
    top_rutas = [{"ruta": d["_id"], "requests": d["n"]} async for d in coll.aggregate(pipeline_rutas)]
    top_usuarios = [{"usuario_id": d["_id"], "requests": d["n"]} async for d in coll.aggregate(pipeline_usuarios)]
    errores = {str(d["_id"]): d["n"] async for d in coll.aggregate(pipeline_errores)}

    return {
        "ventana_horas": horas,
        "desde": desde,
        "total_requests": total,
        "by_status": by_status,
        "by_metodo": by_metodo,
        "top_rutas": top_rutas,
        "top_usuarios": top_usuarios,
        "errores_4xx_5xx": errores,
    }
