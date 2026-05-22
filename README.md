# Rappi2 — API de Logística (FastAPI + PostgreSQL + MongoDB)

## Integrantes

- Huamani Huamani Jhordan
- Flores Leon Miguel
- Mares Graos Frederick
- Ortiz Castañeda Jorge

---

## Roles

### Jorge Ortiz Castañeda

**Rol:** Líder técnico / Backend principal  
**Porcentaje de participación:** 100%

**Aportes:**

Arquitectura y arranque del sistema:

- `main.py`
- Configuración general
- Estructura de carpetas
- `core/`
  - Configuración
  - Conexión DB
  - Seguridad base
- Docker y ejecución:
  - `Dockerfile`
  - `docker-compose.yml`
  - `.env.example`

Seguridad y acceso:

- `api/auth.py`
  - Login
  - Register
  - Refresh
  - Logout
- JWT
- Refresh tokens
- Helpers de seguridad:
  - `core/security.py`
- Dependencias de auth/permisos:
  - `api/dependencies.py`

Diseño de base de datos y modelo:

- `models/`
- Tablas SQLAlchemy
- Migraciones:
  - `alembic/` si aplica en su repo

Flujos principales del negocio:

- Órdenes / Asignaciones / Rutas como flujo completo:
  - `api/ordenes.py`
  - `api/asignaciones.py`
  - `api/rutas.py`
- Integración con servicios externos:
  - `services/ors_service.py`

---

### Jhordan Huamani Huamani

**Rol:** Backend developer  
**Porcentaje de participación:** 23%

**Aportes:**

Módulos CRUD + reglas de negocio secundarias:

- Clientes:
  - `api/clientes.py`
  - Schemas/models relacionados
- Conductores y vehículos:
  - `api/conductores.py`
  - `api/vehiculos.py`
- Pagos y facturas:
  - `api/pagos.py`
  - `api/facturas.py`

Incidencias y evidencias:

- `api/incidencias.py`
- `services/mongo/evidencias_service.py`
- Schemas Mongo asociados

Apoyo a endpoints de reportes:

- `api/reportes.py`
  - Consultas
  - Agregados
  - KPIs

---

### Miguel Flores León

**Rol:** QA / Testing + Documentación  
**Porcentaje de participación:** 100%

**Aportes:**

Documentación principal:

- `README.md`
  - Instalación
  - Ejecución
  - Endpoints clave
  - Ejemplos

Colecciones de pruebas y validación:

- `postman.json`
- Colección Postman o Thunder Client
- Checklist de pruebas:
  - Casos felices
  - Errores
  - Login
  - Permisos
  - CRUDs
  - Rutas
  - Tracking

Pruebas automatizadas:

- Pytest para endpoints clave:
  - Auth
  - Órdenes
  - Asignaciones
- Validación de respuestas:
  - Status codes
  - Esquemas
  - Permisos

---

### Frederick Mares Graos

**Rol:** Integración / DevOps ligero + soporte  
**Porcentaje de participación:** 100%

**Aportes:**

Configuración y entorno:

- `requirements.txt`
- Dependencias limpias
- `.env.example`
- Manejo de variables
- Scripts de inicialización:
  - `scripts/seed_admin.py` o similares

Persistencia e infraestructura:

- Conexión PostgreSQL/Mongo:
  - `core/database.py`
  - `core/mongo.py`
- Indexación/TTL en Mongo:
  - Tracking
  - Auditoría
  - Geocercas
- Desde:
  - `services/mongo/*`

Middleware y logging:

- `middleware/audit.py`
- Logging
- Manejo de errores

---

## Descripción breve del sistema

Rappi2 es una API de logística construida con FastAPI para gestionar entregas: clientes,
órdenes, asignaciones a conductores, planificación de rutas, y funcionalidades transversales
como tracking GPS, geocercas, notificaciones, auditoría y evidencias multimedia. Está diseñada
como una solución híbrida: usa PostgreSQL para datos transaccionales y MongoDB para datos
geoespaciales/logs y contenido no relacional.

---

## Motivación

La motivación técnica y de negocio que se desprende del diseño es:

- Separar lo transaccional de lo operacional/geoespacial:
  - PostgreSQL para integridad, relaciones y consistencia (usuarios, órdenes, pagos, etc.).
  - MongoDB para eventos y consultas geoespaciales (pings GPS, geocercas), auditoría
    con TTL y evidencias.
- Soportar procesos reales de logística: asignación de órdenes, estados de entrega,
  seguimiento, KPIs/reportes, y auditoría de acciones.
- Seguridad y control de acceso mediante RBAC (roles/permisos) y autenticación con
  JWT + refresh tokens con rotación obligatoria.

---

## Requerimientos

### Requerimientos funcionales principales

- Autenticación y sesiones
  - Registro, login, refresh token, logout.
  - Persistencia de refresh tokens (revocables).
- RBAC (Roles/Permisos)
  - Gestión de roles y permisos por (recurso, acción) con comodines `*`.
  - Gestión operativa
  - CRUD de clientes y direcciones.
  - CRUD de órdenes, pagos, facturas.
  - Gestión de conductores y vehículos.
  - Flujo de asignaciones: crear, iniciar, finalizar; transiciones de estado
    (orden y conductor).
- Planificación de rutas
  - Integración con OpenRouteService para planificar y registrar rutas.
- Tracking GPS y geocercas
  - Guardar pings GPS y obtener métricas/estadísticas.
  - Consultas geoespaciales (conductores cerca, punto dentro de geocerca).
- Auditoría
  - Registrar requests HTTP en MongoDB y consultar resúmenes.
- Evidencias
  - Subida/descarga de archivos relacionados a incidencias (p.ej., fotos)
    usando GridFS.
- Reportes
  - Endpoints de dashboard/KPIs, ventas, SLA, top clientes, eficiencia de
    conductores, etc.

### Requerimientos no funcionales

- Asíncrono: API y DB access async (FastAPI + SQLAlchemy async + Motor).
- Contenerización: arranque con Docker Compose.
- Migraciones: Alembic para versionar esquema PostgreSQL.
- Seguridad:
  - Hash de contraseñas (bcrypt).
  - JWT HS256.
  - Refresh tokens con rotación y revocación.
  - CORS configurable.
- Observabilidad mínima: auditoría HTTP en MongoDB (y TTL).

---

## Arquitectura

### Estilo y componentes

Arquitectura tipo API monolítica modular:

- `main.py`: arranque de la app FastAPI.
- `api/`: routers por dominio (roles, usuarios, clientes, órdenes, tracking, auditoría, etc.).
- `models/`: modelos SQLAlchemy (PostgreSQL).
- `schemas/`: esquemas Pydantic (DTOs).
- `services/`:
  - Integración externa OpenRouteService (`ors_service.py`).
  - Servicios Mongo (tracking, geocercas, notificaciones, auditoría, evidencias).
- `middleware/`:
  - Middleware de auditoría (escribe logs a Mongo).
- `core/`:
  - Config (`config.py`)
  - PostgreSQL async (`database.py`)
  - Mongo (`mongo.py`)
  - Seguridad (JWT, hashing, etc.)
- `alembic/`: migraciones.
- `scripts/`: seed inicial (roles/permisos/admin).

---

## Persistencia híbrida (PostgreSQL + MongoDB)

- PostgreSQL: entidad-relación, transacciones, integridad referencial.
- MongoDB: colecciones para:
  - Tracking GPS (alto volumen, geoespacial)
  - Geocercas (polígonos/LineStrings, geoespacial)
  - Notificaciones
  - Auditoría con TTL
  - Evidencias (metadatos + archivos en GridFS)

---

## Esquema de Bases de Datos

### PostgreSQL

Su diseño integra diferentes módulos relacionados entre sí, como usuarios, clientes,
órdenes, conductores, vehículos, rutas, pagos e incidencias, facilitando el control y
seguimiento de todo el proceso del servicio.

- El esquema de la base de datos está orientado a un sistema de gestión logística
  y transporte.
- Gestión de usuarios: incluye las tablas usuarios, roles, permisos y tokens, que
  permiten controlar el acceso al sistema y definir qué acciones puede realizar
  cada usuario.
- Gestión de clientes: se manejan los datos de los clientes y sus direcciones
  mediante las tablas clientes y clientes_direcciones.
- Gestión de órdenes: la tabla ordenes registra los pedidos o servicios solicitados,
  incluyendo origen, destino, estado, fecha de creación y costo total.
- Gestión operativa: las tablas conductores, vehículos y asignaciones permiten
  asignar un conductor y un vehículo a cada orden.
- Planificación de rutas: las tablas rutas_planificadas y paradas permiten registrar
  la ruta, distancia estimada, tiempo aproximado y puntos de parada del servicio.
- Gestión económica: las tablas pagos y facturas permiten controlar los pagos
  realizados y la emisión de comprobantes.
- Control de incidencias: la tabla incidencias registra problemas o eventos
  ocurridos durante la ejecución del servicio.
- En conjunto, la base de datos permite administrar clientes, usuarios, órdenes,
  transporte, rutas, pagos, facturación e incidencias de forma organizada.

![Diseño de tablas SQL](diseno_tablas.png)

---

### MongoDB

El siguiente esquema corresponde a una base de datos NoSQL en MongoDB, diseñada
para complementar el sistema logístico mediante colecciones orientadas al seguimiento
operativo, viajes, alertas, geocercas y estadísticas. A diferencia de una base de datos
relacional, la información se organiza en documentos JSON, lo que permite almacenar
datos flexibles y consultar eventos del servicio de manera rápida.

- Colección `eventos_operacionales`: registra eventos generados durante la
  operación, como el escaneo de paquetes, junto con la fecha, dispositivo utilizado
  y datos adicionales del evento.
- Colección `alerta_logistica`: almacena alertas relacionadas con problemas
  logísticos, como desvíos de ruta o incumplimiento de geocercas, indicando si la
  alerta fue resuelta o no.
- Colección `viajes`: guarda información resumida de cada viaje, incluyendo la orden
  asociada, el conductor, la distancia estimada, el tiempo estimado y la cantidad de
  paradas.
- Colección `geocercas`: define zonas geográficas importantes, como almacenes o
  áreas de control, usando coordenadas en formato de polígono.
- Colección `estadisticas_por_orden`: almacena métricas de cada orden, como
  distancia recorrida, tiempo en tránsito y velocidad promedio.
- En conjunto, estas colecciones permiten monitorear la operación logística en
  tiempo real, controlar rutas, detectar incidencias y generar estadísticas útiles
  para la toma de decisiones.

![Diseño de documentos MongoDB](diseño_documentos.png)

---

## Evidencias Postman
