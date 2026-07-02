import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import (
    asignaciones,
    auditoria,
    auth,
    calificaciones,
    clientes,
    conductores,
    facturas,
    geo,
    incidencias,
    notificaciones,
    ordenes,
    pagos,
    realtime,
    reportes,
    roles,
    rutas,
    tarifa,
    tracking,
    usuarios,
    vehiculos,
)
from core.config import settings
from core.database import get_db
from core.mongo import close_mongo_connection, connect_to_mongo, ensure_all_indexes
from core.realtime import close_redis
from middleware.audit import AuditMiddleware

# Logging central de la app: formato uniforme (fecha, nivel, logger, mensaje) y nivel
# por LOG_LEVEL (.env). No pisa los loggers de uvicorn/alembic (disable_existing=False);
# todos los `logging.getLogger(__name__)` del código heredan este formato vía root.
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "app": {"format": "%(asctime)s %(levelname)-7s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "app"},
    },
    "root": {"level": settings.LOG_LEVEL.upper(), "handlers": ["console"]},
})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    try:
        await ensure_all_indexes()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("No se pudieron crear indices MongoDB: %s", exc)
    yield
    await close_mongo_connection()
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API hibrida PostgreSQL + MongoDB para logistica tipo Rappi",
    version="1.0.0",
    lifespan=lifespan,
)

# Con wildcard ("*") + credenciales, Starlette REFLEJA cualquier Origin con
# Access-Control-Allow-Credentials: true → cualquier sitio podría hacer peticiones
# autenticadas (CSRF/robo de sesión). Con wildcard se desactivan las credenciales;
# la API usa Bearer por cabecera (no cookies), así que el frontend no se ve afectado.
_cors_wildcard = settings.CORS_ORIGINS == ["*"]
if _cors_wildcard:
    logging.getLogger(__name__).warning(
        "CORS_ORIGINS=['*']: credenciales CORS deshabilitadas. "
        "En producción restringe los orígenes (p. ej. CORS_ORIGINS=[\"https://app.midominio.com\"])."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=not _cors_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
    # Necesario para que el navegador exponga el total de paginación a JS.
    expose_headers=["X-Total-Count"],
)
app.add_middleware(AuditMiddleware)

PREFIX = "/api"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(roles.router, prefix=PREFIX)
app.include_router(usuarios.router, prefix=PREFIX)
app.include_router(clientes.router, prefix=PREFIX)
app.include_router(ordenes.router, prefix=PREFIX)
app.include_router(pagos.router, prefix=PREFIX)
app.include_router(facturas.router, prefix=PREFIX)
app.include_router(vehiculos.router, prefix=PREFIX)
app.include_router(conductores.router, prefix=PREFIX)
app.include_router(asignaciones.router, prefix=PREFIX)
app.include_router(rutas.router, prefix=PREFIX)
app.include_router(tarifa.router, prefix=PREFIX)
app.include_router(incidencias.router, prefix=PREFIX)
app.include_router(tracking.router, prefix=PREFIX)
app.include_router(notificaciones.router, prefix=PREFIX)
app.include_router(auditoria.router, prefix=PREFIX)
app.include_router(reportes.router, prefix=PREFIX)
app.include_router(calificaciones.router, prefix=PREFIX)
app.include_router(realtime.router, prefix=PREFIX)
app.include_router(geo.router, prefix=PREFIX)


@app.get("/", tags=["root"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health", tags=["root"])
async def health(db: AsyncSession = Depends(get_db)):
    """Healthcheck para orquestadores (compose/Dokploy): responde 200 solo si la app
    está arriba Y la base de datos contesta. Sin auth (no expone datos)."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
