from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    asignaciones,
    auditoria,
    auth,
    calificaciones,
    clientes,
    conductores,
    facturas,
    incidencias,
    notificaciones,
    ordenes,
    pagos,
    realtime,
    reportes,
    roles,
    rutas,
    sesiones,
    tarifa,
    tracking,
    usuarios,
    vehiculos,
)
from core.config import settings
from core.mongo import close_mongo_connection, connect_to_mongo, ensure_all_indexes
from core.realtime import close_redis
from middleware.audit import AuditMiddleware


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
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
app.include_router(sesiones.router, prefix=PREFIX)
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


@app.get("/", tags=["root"])
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
