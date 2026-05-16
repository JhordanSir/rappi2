from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.config import settings
from core.mongo import connect_to_mongo, close_mongo_connection
from api import auth, clientes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB
    await connect_to_mongo()
    yield
    # Shutdown: Close connection
    await close_mongo_connection()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(auth.router, prefix="/api")
app.include_router(clientes.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Bienvenido a la API", "docs_url": "/docs"}
