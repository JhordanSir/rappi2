# Rappi2 — API de Logística (FastAPI + PostgreSQL + MongoDB)

Sistema híbrido de gestión de entregas con tracking GPS, geocercas, notificaciones, auditoría y evidencias multimedia, alineado al diagrama `diseno_tablas.png`.

## Integrantes

- Huamani Huamani Jhordan
- Flores Leon Miguel
- Mares Graos Frederick
- Ortiz Castañeda Jorge

## Stack

- **FastAPI** (async, OpenAPI/Swagger)
- **PostgreSQL 15** (datos transaccionales, sin PostGIS) + **SQLAlchemy 2.0 async**
- **MongoDB 6.0** con índices `2dsphere` y TTL (Motor async)
- **Alembic** para migraciones
- **JWT (HS256)** + **refresh tokens** persistidos (rotación obligatoria)
- **OpenRouteService** para planificación de rutas

## Arquitectura híbrida

**PostgreSQL** — 15 tablas: `roles`, `permisos`, `usuarios`, `tokens`, `clientes`, `clientes_direcciones`, `ordenes`, `pagos`, `facturas`, `vehiculos` (PK = `placa`), `conductores`, `asignaciones`, `rutas_planificadas`, `paradas`, `incidencias`.

**MongoDB** — 5 colecciones:

| Colección | Propósito | Índices |
|---|---|---|
| `gps_tracking` | Pings GPS de conductores/asignaciones | `2dsphere(location)`, `(asignacion_id, timestamp DESC)` |
| `geocercas` | Polígonos / LineStrings de rutas, zonas, prohibidas | `2dsphere(geometry)`, `(ruta_id, activa)` |
| `notificaciones` | Notificaciones in-app a usuarios/clientes | `(destinatario_tipo, destinatario_id, fecha)`, `(leida)` |
| `auditoria` | Log de cada request HTTP (vía middleware) | `(usuario_id, timestamp)`, **TTL 90 días** |
| `evidencias` | Multimedia de incidencias | `(incidencia_id)` |

## Arranque local (Docker)

```powershell
# 1. Configurar entorno
Copy-Item .env.example .env
# Editar .env: cambiar SECRET_KEY y poner ORS_API_KEY si vas a planificar rutas

# 2. Volumen limpio (si vienes de la version anterior con PostGIS)
docker compose down -v

# 3. Levantar servicios
docker compose up --build -d

# 4. Aplicar migraciones (crea las 15 tablas)
docker compose exec api alembic upgrade head

# 5. Seed: roles base + permiso *:* para Admin + usuario admin/admin123
docker compose exec api python -m scripts.seed_admin
```

Endpoints disponibles tras el arranque:

- API:       http://localhost:8000
- Swagger:   http://localhost:8000/docs
- OpenAPI:   http://localhost:8000/openapi.json

## Estructura

```
.
├── main.py
├── core\               # config, database (Postgres), mongo, security (JWT + refresh)
├── models\             # SQLAlchemy 2.0 (15 modelos en 9 archivos)
├── schemas\            # Pydantic v2 (Postgres + Mongo)
├── api\                # Routers por dominio (15 routers)
├── services\
│   ├── ors_service.py  # OpenRouteService
│   └── mongo\          # 5 servicios Mongo (tracking, geocerca, notif, auditoria, evidencias)
├── middleware\
│   └── audit.py        # AuditMiddleware -> escribe a Mongo `auditoria` async
├── alembic\            # Migraciones versionadas
├── scripts\
│   └── seed_admin.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Flujo de autenticación

1. `POST /api/auth/register` → crea `Usuario` (y `Cliente` si rol = "Cliente").
2. `POST /api/auth/login` (form `username` + `password`) → devuelve `access_token` (15min) + `refresh_token` (7 días).
3. Cliente envía `Authorization: Bearer <access_token>` en cada request.
4. `POST /api/auth/refresh` con el refresh → emite par nuevo y **revoca el anterior** (rotación obligatoria).
5. `POST /api/auth/logout` → marca refresh como revocado.

Los refresh tokens se persisten en la tabla `tokens` como SHA-256 (nunca el valor crudo).

## Verificación end-to-end (resumen)

```powershell
# Login (form-urlencoded)
curl -X POST localhost:8000/api/auth/login -d "username=admin&password=admin123"

# Crear cliente
curl -X POST localhost:8000/api/clientes/ -H "Authorization: Bearer <token>" `
  -H "Content-Type: application/json" `
  -d '{"nombre":"Juan","email":"j@x.com"}'

# Crear orden → asignar → planificar ruta → trackear GPS
# Detalle completo en el plan: C:\Users\<user>\.claude\plans\diseno-tablas-png-en-base-a-enumerated-wall.md
```

Validar Mongo:

```powershell
docker compose exec mongodb mongosh -u admin -p admin
> use rappi2_mongo
> db.gps_tracking.getIndexes()    # debe mostrar 2dsphere
> db.geocercas.getIndexes()       # debe mostrar 2dsphere
> db.auditoria.getIndexes()       # debe mostrar TTL 7776000s
> db.auditoria.find().sort({timestamp:-1}).limit(5)
```

## Comandos Alembic útiles

```powershell
docker compose exec api alembic upgrade head           # aplicar migraciones
docker compose exec api alembic downgrade -1           # revertir una
docker compose exec api alembic current                # ver version actual
docker compose exec api alembic revision --autogenerate -m "mensaje"
```

## Permisos

Sistema RBAC simple: cada rol tiene `(recurso, accion)` en `permisos`. Wildcards `*` soportados.

Por defecto el seed crea:
- Rol **Admin** con permiso `*:*` (acceso total).
- Roles **Despachador**, **Conductor**, **Cliente** sin permisos (asignar manualmente vía `POST /api/roles/{id}/permisos`).

Recursos en uso: `roles`, `usuarios`, `tokens`, `clientes`, `ordenes`, `pagos`, `facturas`, `vehiculos`, `conductores`, `asignaciones`, `rutas`, `incidencias`, `tracking`, `geocercas`, `notificaciones`, `auditoria`, `reportes`. Acciones: `read`, `write`, `delete`.

## Endpoints de funcionalidad / reportes

Más allá del CRUD básico, la API expone:

**Reportes** (`/api/reportes`, requiere `reportes:read`):
- `GET /dashboard` — KPIs globales (counts por entidad, órdenes por estado, conductores por disponibilidad, vehículos por estado, recaudación últimas 24h, incidencias severas).
- `GET /ventas?desde=&hasta=&granularidad=dia|mes` — serie temporal de recaudación + total facturado.
- `GET /top-clientes?limit=10` — top clientes por monto pagado.
- `GET /conductores` — métricas por conductor (asignaciones totales, finalizadas, en curso, incidencias).
- `GET /incidencias?desde=&hasta=` — distribución por severidad y tipo.
- `GET /tiempos-entrega?desde=&hasta=` — promedio/min/max de duración de asignaciones finalizadas.
- `GET /cliente/{id}/resumen` — vista 360 de un cliente.
- `GET /sla-entregas?desde=&hasta=&sla_minutos=60` — % de entregas on-time + percentiles p50/p95.
- `GET /conductores/eficiencia?desde=&hasta=&limit=20` — entregas/hora, horas activas, tasa de incidencias por conductor.
- `GET /distribucion-geografica?desde=&hasta=&top=10` — top distritos por volumen (origen y destino).

**Auditoría** (`/api/auditoria`, requiere `auditoria:read`):
- `GET /` — listar logs (filtros: usuario_id, metodo).
- `GET /resumen?horas=24` — agregaciones MongoDB (requests por status, método, top rutas, top usuarios, errores 4xx/5xx).

**Sesiones** (sub-recurso de usuarios, requiere `sesiones:*` si no es el propio usuario):
- `GET /api/usuarios/me/sesiones` — sesiones del usuario autenticado.
- `GET /api/usuarios/{id}/sesiones` — sesiones de cualquier usuario (admin).
- `DELETE /api/usuarios/{id}/sesiones/{sesion_id}` — revocar una sesión.
- `DELETE /api/usuarios/{id}/sesiones` — forzar logout total de un usuario.

**Tracking avanzado** (`/api/tracking`, requiere `tracking:read`):
- `GET /tracking/asignacion/{id}/estadisticas` — distancia total (haversine), duración, velocidad promedio.
- `GET /tracking/conductores-cerca?lon=&lat=&radio_m=2000&ventana_min=5` — conductores con ping reciente cerca del punto (usa `$geoNear`).

**Flujos de negocio** (en routers ya descritos):
- `POST /asignaciones/` — crea la asignación y transiciona orden a "En Proceso", conductor a "Ocupado".
- `PATCH /asignaciones/{id}/iniciar` — marca inicio y orden a "En Tránsito".
- `PATCH /asignaciones/{id}/finalizar` — marca fin, orden a "Entregado", conductor de nuevo "Disponible".
- `POST /rutas/planificar` — llama a OpenRouteService y crea automáticamente la geocerca de la ruta en MongoDB.
- `GET /geocercas/contiene?lon=&lat=` — geocercas activas que contienen el punto (`$geoIntersects`).
- `POST /incidencias/{id}/evidencias/upload` (multipart) — sube archivos físicos a GridFS y crea el documento de evidencia.
- `GET /incidencias/evidencias/archivos/{file_id}` — stream de descarga desde GridFS.
