"""Capa de tiempo real basada en Redis pub/sub.

El servidor publica eventos (cambios de orden/asignación, posición GPS, notificaciones)
en canales Redis y los entrega a los navegadores por SSE. Redis actúa como backplane
para que un evento producido en cualquier worker de uvicorn llegue a los clientes
conectados en otro worker.

Convención de canales:
  - ``user:{usuario_id}``        eventos dirigidos a un usuario concreto
  - ``cliente:{cliente_id}``     eventos de las órdenes de ese cliente (estado, posición)
  - ``conductor:{conductor_id}`` eventos de las asignaciones de ese conductor
  - ``staff``                    eventos operativos para Admin/Despachador
"""
import json
import logging
from typing import AsyncIterator, Optional

import redis.asyncio as aioredis

from core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:  # pragma: no cover - best effort en shutdown
            pass
        _redis = None


def canal_usuario(usuario_id: int) -> str:
    return f"user:{usuario_id}"


def canal_cliente(cliente_id: int) -> str:
    return f"cliente:{cliente_id}"


def canal_conductor(conductor_id: int) -> str:
    return f"conductor:{conductor_id}"


CANAL_STAFF = "staff"


async def publish(channel: str, data: dict) -> None:
    """Publica un evento (best-effort). Si Redis no está disponible no rompe la request."""
    try:
        await get_redis().publish(channel, json.dumps(data, default=str))
    except Exception as exc:
        logger.warning("No se pudo publicar evento en %s: %s", channel, exc)


async def event_stream(channels: list[str]) -> AsyncIterator[str]:
    """Generador SSE: se suscribe a los canales y emite cada mensaje recibido.
    Emite un comentario keepalive periódico para mantener viva la conexión y
    detectar desconexiones del cliente."""
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(*channels)
    try:
        yield ": conectado\n\n"
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
            except Exception as exc:
                logger.warning("Error leyendo pubsub SSE: %s", exc)
                break
            if message is None:
                yield ": keepalive\n\n"
                continue
            data = message.get("data")
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")
            yield f"data: {data}\n\n"
    finally:
        try:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()
        except Exception:  # pragma: no cover
            pass
