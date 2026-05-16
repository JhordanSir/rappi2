# Rappi2 — API de Logística

Sistema híbrido de gestión de entregas con tracking GPS en tiempo real.

## Integrantes

- Huamani Huamani Jhordan
- Flores Leon Miguel
- Mares Graos Frederick
- Ortiz Castañeda Jorge

## Stack

- **FastAPI** (async)
- **PostgreSQL 15 + PostGIS** (datos transaccionales y geoespaciales)
- **MongoDB 6.0** (telemetría GPS y geocercas en tiempo real)
- **SQLAlchemy 2.0 + asyncpg** | **Motor** (Mongo async)
- **Alembic** (migraciones SQL)

## Arranque local (Docker)

1. Copia el archivo de entorno:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Levanta los servicios:

   ```powershell
   docker compose up -d --build
   ```

3. Aplica la migración inicial (habilita PostGIS):

   ```powershell
   docker compose exec app alembic upgrade head
   ```

4. Verifica:

   - API:           http://localhost:8000
   - Swagger:       http://localhost:8000/docs
   - Healthcheck:   http://localhost:8000/api/v1/health
   - Health DB:     http://localhost:8000/api/v1/health/db

## Estructura

```
app/
├── api/            # Routers FastAPI por versión
│   └── v1/
│       ├── endpoints/
│       └── router.py
├── core/           # Configuración, settings, seguridad
├── db/             # Conexiones Postgres (async) y Mongo
├── models/         # ORM SQLAlchemy 2.0
├── repositories/   # Acceso a datos
├── schemas/        # Pydantic v2
├── services/       # Lógica de negocio
└── main.py
alembic/            # Migraciones SQL
```

## Comandos Alembic

```powershell
# Generar migración automática
docker compose exec app alembic revision --autogenerate -m "mensaje"

# Aplicar migraciones
docker compose exec app alembic upgrade head

# Revertir una versión
docker compose exec app alembic downgrade -1
```
