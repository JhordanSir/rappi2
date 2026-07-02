"""Arnés de pruebas del backend. Se ejecuta DENTRO del contenedor `api`:

    docker compose exec api pip install -r requirements-dev.txt
    docker compose exec api pytest

- BD: usa `rappi2_test` en el mismo Postgres del compose (se crea sola); el esquema se
  recrea desde los modelos en cada corrida (incluye los CHECK de estados).
- Servicios: Mongo/Redis reales del compose; auditoría desactivada por env.
- Auth: `get_current_user` se sobreescribe con un admin de prueba (permiso *:*), así
  los tests no dependen de Keycloak.
"""
import os

# Entorno ANTES de importar la app: BD de prueba y sin servicios externos.
_BASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/rappi2"
)
os.environ["DATABASE_URL"] = _BASE_URL.rsplit("/", 1)[0] + "/rappi2_test"
os.environ["AUDIT_ENABLED"] = "false"
os.environ["GEOCODING_ENABLED"] = "false"
os.environ["RUTA_AUTOGENERAR"] = "false"

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import get_current_user
from core.database import AsyncSessionLocal, Base, engine
from core.mongo import close_mongo_connection, connect_to_mongo
from main import app
from models.clientes import Cliente
from models.conductores import Conductor
from models.destinos import Destino
from models.ordenes import Orden
from models.roles import Permiso, Rol
from models.usuarios import Usuario
from models.vehiculos import Vehiculo


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _entorno():
    # Crear la BD de prueba si no existe (conexión administrativa con AUTOCOMMIT).
    admin = create_async_engine(
        _BASE_URL.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT"
    )
    async with admin.connect() as conn:
        existe = (
            await conn.execute(text("SELECT 1 FROM pg_database WHERE datname='rappi2_test'"))
        ).scalar()
        if not existe:
            await conn.execute(text("CREATE DATABASE rappi2_test"))
    await admin.dispose()

    # Esquema limpio desde los modelos.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await connect_to_mongo()

    # Datos base: roles + admin de prueba con permiso total.
    async with AsyncSessionLocal() as db:
        admin_rol = Rol(nombre="Admin")
        db.add_all([admin_rol, Rol(nombre="Conductor"), Rol(nombre="Cliente")])
        await db.flush()
        db.add(Permiso(rol_id=admin_rol.id, recurso="*", accion="*"))
        db.add(
            Usuario(
                username="admin_test",
                email="admin_test@testmail.com",
                password_hash=None,
                rol_id=admin_rol.id,
                auth_provider="keycloak",
            )
        )
        await db.commit()

    async def _admin_de_prueba():
        async with AsyncSessionLocal() as db:
            return (
                await db.execute(
                    select(Usuario)
                    .options(selectinload(Usuario.rol))
                    .where(Usuario.username == "admin_test")
                )
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _admin_de_prueba
    yield
    app.dependency_overrides.pop(get_current_user, None)
    await close_mongo_connection()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------- factorías (entidades mínimas válidas, directo en BD) ----------------
_seq = {"n": 0}


def _sig() -> int:
    _seq["n"] += 1
    return _seq["n"]


@pytest_asyncio.fixture
async def factoria(db):
    class F:
        @staticmethod
        async def cliente(**kw):
            n = _sig()
            c = Cliente(nombre=kw.get("nombre", f"Cliente {n}"), email=kw.get("email", f"cli{n}@testmail.com"))
            db.add(c)
            await db.commit()
            await db.refresh(c)
            return c

        @staticmethod
        async def vehiculo(**kw):
            n = _sig()
            v = Vehiculo(
                placa=kw.get("placa", f"TS{n % 10}-{n:03d}"),
                tipo=kw.get("tipo", "Moto"),
                capacidad_kg=kw.get("capacidad_kg", 100),
                largo_cm=kw.get("largo_cm", 100),
                ancho_cm=kw.get("ancho_cm", 100),
                alto_cm=kw.get("alto_cm", 100),
            )
            db.add(v)
            await db.commit()
            await db.refresh(v)
            return v

        @staticmethod
        async def conductor(vehiculo_placa=None, **kw):
            n = _sig()
            rol = (await db.execute(select(Rol).where(Rol.nombre == "Conductor"))).scalar_one()
            u = Usuario(username=f"cond{n}", email=f"cond{n}@testmail.com", rol_id=rol.id)
            db.add(u)
            await db.flush()
            c = Conductor(
                usuario_id=u.id,
                nombre=kw.get("nombre", f"Conductor {n}"),
                licencia=f"LIC-{n:05d}",
                disponibilidad=kw.get("disponibilidad", "Disponible"),
                vehiculo_placa=vehiculo_placa,
            )
            db.add(c)
            await db.commit()
            await db.refresh(c)
            return c

        @staticmethod
        async def orden(cliente_id, peso_kg=5, estado="Pendiente", total=None):
            n = _sig()
            o = Orden(
                cliente_id=cliente_id,
                estado=estado,
                direccion_origen=f"Origen {n}",
                lat_origen=-16.35,
                lon_origen=-71.55,
                direccion_destino=f"Destino {n}",
                lat_destino=-16.36,
                lon_destino=-71.54,
                total=total,
            )
            db.add(o)
            await db.flush()
            # Sin dimensiones: el peso cobrable = peso real (determinista para los tests).
            db.add(Destino(orden_id=o.id, secuencia=1, direccion=f"Destino {n}", lat=-16.36, lon=-71.54, peso_kg=peso_kg))
            await db.commit()
            await db.refresh(o)
            return o

    return F
