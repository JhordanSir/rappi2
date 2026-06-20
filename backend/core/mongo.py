import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import settings

logger = logging.getLogger(__name__)


class MongoState:
    client: AsyncIOMotorClient | None = None


_state = MongoState()


async def connect_to_mongo() -> None:
    _state.client = AsyncIOMotorClient(settings.MONGO_URL, uuidRepresentation="standard")
    logger.info("MongoDB conectado a %s", settings.MONGO_DB)


async def close_mongo_connection() -> None:
    if _state.client is not None:
        _state.client.close()
        _state.client = None
        logger.info("MongoDB desconectado")


def get_client() -> AsyncIOMotorClient:
    if _state.client is None:
        raise RuntimeError("MongoDB no inicializado. Llama a connect_to_mongo primero.")
    return _state.client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.MONGO_DB]


async def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_database()


async def ensure_all_indexes() -> None:
    from services.mongo import (
        tracking_service,
        geocerca_service,
        notificaciones_service,
        auditoria_service,
        evidencias_service,
        entregas_service,
    )
    db = get_database()
    await tracking_service.ensure_indexes(db)
    await geocerca_service.ensure_indexes(db)
    await notificaciones_service.ensure_indexes(db)
    await auditoria_service.ensure_indexes(db)
    await evidencias_service.ensure_indexes(db)
    await entregas_service.ensure_indexes(db)
    logger.info("Indices MongoDB asegurados")
