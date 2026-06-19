from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import get_current_user, get_mongo_db, require_permiso
from core.realtime import canal_cliente, canal_usuario, publish
from models.usuarios import Usuario
from schemas.common import MessageResponse
from schemas.mongo_notificaciones import NotificacionIn, NotificacionOut
from services.mongo import notificaciones_service

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


@router.post("/", response_model=NotificacionOut, status_code=status.HTTP_201_CREATED)
async def crear_notificacion(
    payload: NotificacionIn,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("notificaciones", "write")),
):
    notif = await notificaciones_service.crear(mongo_db, payload)
    # Empuja la notificación al destinatario en tiempo real (campana).
    canal = (
        canal_cliente(payload.destinatario_id)
        if payload.destinatario_tipo == "cliente"
        else canal_usuario(payload.destinatario_id)
    )
    await publish(canal, {"tipo": "notificacion", "titulo": payload.titulo, "mensaje": payload.mensaje})
    return notif


@router.get("/mias", response_model=list[NotificacionOut])
async def mis_notificaciones(
    leida: Optional[bool] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    current_user: Usuario = Depends(get_current_user),
    mongo_db = Depends(get_mongo_db),
):
    destinatario_tipo = "cliente" if current_user.cliente_id is not None else "usuario"
    destinatario_id = current_user.cliente_id if current_user.cliente_id is not None else current_user.id
    return await notificaciones_service.listar_para(mongo_db, destinatario_tipo, destinatario_id, leida, skip, limit)


@router.patch("/{notif_id}/leer", response_model=MessageResponse)
async def marcar_leida(
    notif_id: str,
    current_user: Usuario = Depends(get_current_user),
    mongo_db = Depends(get_mongo_db),
):
    destinatario_tipo = "cliente" if current_user.cliente_id is not None else "usuario"
    destinatario_id = current_user.cliente_id if current_user.cliente_id is not None else current_user.id
    ok = await notificaciones_service.marcar_leida(mongo_db, notif_id, destinatario_tipo, destinatario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notificacion no encontrada")
    return MessageResponse(message="Notificacion marcada como leida")


@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_notificacion(
    notif_id: str,
    current_user: Usuario = Depends(get_current_user),
    mongo_db = Depends(get_mongo_db),
):
    destinatario_tipo = "cliente" if current_user.cliente_id is not None else "usuario"
    destinatario_id = current_user.cliente_id if current_user.cliente_id is not None else current_user.id
    ok = await notificaciones_service.eliminar(mongo_db, notif_id, destinatario_tipo, destinatario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notificacion no encontrada")
