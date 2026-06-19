"""Endpoint SSE para que el navegador reciba eventos en tiempo real.

EventSource no permite enviar cabeceras, por eso el access token viaja como query
param. Los canales a los que se suscribe la conexión se derivan SIEMPRE de la
identidad del token (nunca de parámetros del cliente), evitando que alguien escuche
canales ajenos."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import STAFF_ROLES
from core.database import get_db
from core.realtime import event_stream
from core.security import decode_access_token
from models.conductores import Conductor
from models.usuarios import Usuario

router = APIRouter(prefix="/realtime", tags=["realtime"])


async def _canales_de(token: str, db: AsyncSession) -> list[str]:
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invalidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
    except JWTError:
        raise cred_error
    if user_id is None:
        raise cred_error

    user = (
        await db.execute(select(Usuario).options(selectinload(Usuario.rol)).where(Usuario.id == user_id))
    ).scalar_one_or_none()
    if user is None or not user.activo:
        raise cred_error

    canales = [f"user:{user.id}"]
    rol = user.rol.nombre if user.rol is not None else None
    if user.cliente_id is not None:
        canales.append(f"cliente:{user.cliente_id}")
    elif rol not in STAFF_ROLES:
        conductor_id = (
            await db.execute(select(Conductor.id).where(Conductor.usuario_id == user.id))
        ).scalar_one_or_none()
        if conductor_id is not None:
            canales.append(f"conductor:{conductor_id}")
    if rol in STAFF_ROLES:
        canales.append("staff")
    return canales


@router.get("/stream")
async def stream(
    token: str = Query(..., description="access token (EventSource no envía cabeceras)"),
    db: AsyncSession = Depends(get_db),
):
    canales = await _canales_de(token, db)
    return StreamingResponse(
        event_stream(canales),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # evita el buffering de nginx en prod
        },
    )
