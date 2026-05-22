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

### Auth
![Login](images/rappi2_auth_login.jpeg)
![Register](images/rappi2_auth_register.jpeg)
![Me](images/rappi2_auth_me.jpeg)
![Refresh](images/rappi2_auth_refresh.jpeg)
![Logout](images/rappi2_auth_logout.jpeg)

---

### Sesiones
![Me sesiones](images/rappi2_sesiones_me_sesiones.jpeg)
![Usuario sesiones](images/rappi2_sesiones_usuario_sesiones.jpeg)
![Revocar](images/rappi2_sesiones_revocar.jpeg)
![Revocar todas](images/rappi2_sesiones_revocar_todas.jpeg)

---

### Roles y permisos
![Roles](images/rappi2_roles.jpeg)
![Roles ID](images/rappi2_roles_id.jpeg)
![Roles ID Patch](images/rappi2_roles_id_patch.jpeg)
![Roles ID Delete](images/rappi2_roles_id_delete.jpeg)
![Roles ID Permisos](images/rappi2_roles_id_permisos.jpeg)
![Roles ID Permisos ID](images/rappi2_roles_id_permisos_id.jpeg)
![Roles permisos all id](images/rappi2_roles_permisos_all_id.jpeg)
![Roles permisos id](images/rappi2_roles_permisos_id.jpeg)
![Roles post](images/rappi2_roles_post.jpeg)

---

### Usuarios
![Usuarios](images/rappi2_usuarios.jpeg)
![Usuarios ID](images/rappi2_usuarios_id.jpeg)
![Usuarios ID Patch](images/rappi2_usuarios_id_patch.jpeg)
![Usuarios ID Delete](images/rappi2_usuarios_id_delete.jpeg)
![Usuarios post](images/rappi2_usuarios_post.jpeg)

---

### Clientes
![Clientes](images/rappi2_clientes.jpeg)
![Clientes post](images/rappi2_clientes_post.jpeg)
![Clientes id](images/rappi2_clientes_id.jpeg)
![Clientes id patch](images/rappi2_clientes_id%20patch.jpeg)
![Clientes id delete](images/rappi2_clientes_id_delete.jpeg)
![Clientes id direcciones](images/rappi2_clientes_id_direcciones.jpeg)
![Clientes id direcciones post](images/rappi2_clientes_id_direcciones_post.jpeg)
![Clientes id direcciones id](images/rappi2_clientes_id_direcciones_id.jpeg)
![Clientes id direcciones id delete](images/rappi2_clientes_id_direcciones_id_delete.jpeg)

---

### Conductores
![Conductores](images/rappi2_conductores.jpeg)
![Conductores post](images/rappi2_conductores_post.jpeg)
![Conductores id](images/rappi2_conductores_id.jpeg)
![Conductores id patch](images/rappi2_conductores_id_patch.jpeg)
![Conductores id delete](images/rappi2_conductores_id_delete.jpeg)
![Conductores id vehiculo](images/rappi2_conductores_id_vehiculo.jpeg)

---

### Vehiculos
![Vehiculos](images/rappi2_vehiculos.jpeg)
![Vehiculos post](images/rappi2_vehiculos_post.jpeg)
![Vehiculos placa](images/rappi2_vehiculos_placa.jpeg)
![Vehiculos placa patch](images/rappi2_vehiculos_placa_patch.jpeg)
![Vehiculos placa delete](images/rappi2_vehiculos_placa_delete.jpeg)

---

### Ordenes
![Ordenes](images/rappi2_ordenes.jpeg)
![Ordenes post](images/rappi2_ordenes_post.jpeg)
![Ordenes id](images/rappi2_ordenes_id.jpeg)
![Ordenes id patch](images/rappi2_ordenes_id_patch.jpeg)
![Ordenes id delete](images/rappi2_ordenes_id_delete.jpeg)
![Ordenes id pagos](images/rappi2_ordenes_id_pagos.jpeg)
![Ordenes id facturas](images/rappi2_ordenes_id_facturas.jpeg)

---

### Pagos
![Pagos](images/rappi2_pagos.jpeg)
![Pagos post](images/rappi2_pagos_post.jpeg)
![Pagos id](images/rappi2_pagos_id.jpeg)
![Pagos id patch](images/rappi2_pagos_id_patch.jpeg)
![Pagos id delete](images/rappi2_pagos_id_delete.jpeg)

---

### Facturas
![Facturas](images/rappi2_facturas.jpeg)
![Facturas post](images/rappi2_facturas_post.jpeg)
![Facturas id](images/rappi2_facturas_id.jpeg)
![Facturas id patch](images/rappi2_facturas_id_patch.jpeg)
![Facturas delete](images/rappi2_facturas_delete.jpeg)

---

### Root / Docs
![Info](images/miguel_endpoints/rappi2_root_info.jpeg)
![Swagger UI](images/miguel_endpoints/rappi2_root_swagger-ui.jpeg)
![OpenAPI JSON](images/miguel_endpoints/rappi2_root_openapi-json.jpeg)

---

### Asignaciones
![Listar](images/miguel_endpoints/rappi2_asignaciones_listar.jpeg)
![Obtener](images/miguel_endpoints/rappi2_asignaciones_obtener.jpeg)
![Crear](images/miguel_endpoints/rappi2_asignaciones_crear.jpeg)
![Actualizar](images/miguel_endpoints/rappi2_asignaciones_actualizar.jpeg)
![Iniciar](images/miguel_endpoints/rappi2_asignaciones_iniciar.jpeg)
![Finalizar](images/miguel_endpoints/rappi2_asignaciones_finalizar.jpeg)
![Eliminar](images/miguel_endpoints/rappi2_asignaciones_eliminar.jpeg)

---

### Auditoría
![Listar logs auditoría](images/miguel_endpoints/rappi2_auditoria_listar-logs-auditoria.jpeg)
![Resumen auditoría](images/miguel_endpoints/rappi2_auditoria_resumen-auditoria.jpeg)

---

### Geocercas
![Listar](images/miguel_endpoints/rappi2_geocerca_listar.jpeg)
![Obtener uno](images/miguel_endpoints/rappi2_geocerca_obtener_uno.jpeg)
![Crear](images/miguel_endpoints/rappi2_geocerca_crear.jpeg)
![Actualizar](images/miguel_endpoints/rappi2_geocerca_actualizar.jpeg)
![Desactivar](images/miguel_endpoints/rappi2_geocerca_desactivar.jpeg)
![Punto en geocerca](images/miguel_endpoints/rappi2_geocerca_geocerca_punto.jpeg)

---

### Incidencias (CRUD)
![Listar incidencias](images/miguel_endpoints/rappi2_incidencias_listar-incidencias.jpeg)
![Obtener incidencia](images/miguel_endpoints/rappi2_incidencias_obtener-incidencias.jpeg)
![Crear incidencia](images/miguel_endpoints/rappi2_incidencias_crear-incidencias.jpeg)
![Actualizar incidencia](images/miguel_endpoints/rappi2_incidencias_actualizar-incidencias.jpeg)
![Eliminar incidencia](images/miguel_endpoints/rappi2_incidencias_eliminar-incidencias.jpeg)

---

### Incidencias (Evidencias)
![Listar evidencias](images/miguel_endpoints/rappi2_incidencias_listar-evidencias.jpeg)
![Obtener evidencia](images/miguel_endpoints/rappi2_incidencias_obtener-evidencias.jpeg)
![Subir evidencia](images/miguel_endpoints/rappi2_incidencias_subir-evidencias.jpeg)
![Descargar evidencia](images/miguel_endpoints/rappi2_incidencias_descargar-evidencias.jpeg)
![Eliminar evidencia](images/miguel_endpoints/rappi2_incidencias_eliminar-evidencias.jpeg)

---

### Notificaciones
![Mis notificaciones](images/miguel_endpoints/rappi2_notificaciones_mis-notificaciones.jpeg)
![Crear](images/miguel_endpoints/rappi2_notificaciones_crear.jpeg)
![Marcar leído](images/miguel_endpoints/rappi2_notificaciones_marcar-leido.jpeg)
![Eliminar](images/miguel_endpoints/rappi2_notificaciones_eliminar.jpeg)

---

### Tracking GPS
![Enviar ping](images/miguel_endpoints/rappi2_tracking-gps_enviar-ping.jpeg)
![Un ping (asignación)](images/miguel_endpoints/rappi2_tracking-gps_un-ping-asignacion.jpeg)
![Último ping (asignación)](images/miguel_endpoints/rappi2_tracking-gps_ultimo-ping-asignacion.jpeg)
![Estadística (asignación)](images/miguel_endpoints/rappi2_tracking-gps_estad%C3%ADstica-asignacion.jpeg)
![Conductores (asignación)](images/miguel_endpoints/rappi2_tracking-gps_conductores-asignacion.jpeg)

---

### Reportes / KPIs
![Dashboard KPIs](images/miguel_endpoints/rappi2_reportes_dashboard-kpis.jpeg)
![KPIs operativos](images/miguel_endpoints/rappi2_reportes_kpis-operativos.jpeg)
![SLA entregas](images/miguel_endpoints/rappi2_reportes_sla-entregas.jpeg)
![Tiempos de entrega](images/miguel_endpoints/rappi2_reportes_tiempos-entrega.jpeg)
![Ventas (serie temporal)](images/miguel_endpoints/rappi2_reportes_ventas-serie-temporal.jpeg)
![Top clientes](images/miguel_endpoints/rappi2_reportes_top-clientes.jpeg)
![Eficiencia conductor](images/miguel_endpoints/rappi2_reportes_eficiencia-conductor.jpeg)
![Métricas conductor](images/miguel_endpoints/rappi2_reportes_metricas-conductor.jpeg)
![Resumen incidencias](images/miguel_endpoints/rappi2_reportes_resumen-incidencias.jpeg)
![Resumen notificaciones](images/miguel_endpoints/rappi2_reportes_resumen-notificaciones.jpeg)
![Análisis evidencias](images/miguel_endpoints/rappi2_reportes_analisis-evidencias.jpeg)
![Vista 360 (asignación)](images/miguel_endpoints/rappi2_reportes_vista-360-asignacion.jpeg)
![Vista 360 (cliente)](images/miguel_endpoints/rappi2_reportes_vista-360-cliente.jpeg)

---

### Reportes / Rutas y Paradas
![Planificar rutas](images/miguel_endpoints/rappi2_reportes-paradas_planificar-rutas.jpeg)
![Listar rutas](images/miguel_endpoints/rappi2_reportes-paradas_listar-rutas.jpeg)
![Obtener ruta](images/miguel_endpoints/rappi2_reportes-paradas_obtener-rutas.jpeg)
![Crear rutas](images/miguel_endpoints/rappi2_reportes-paradas_crear-rutas.jpeg)
![Actualizar rutas](images/miguel_endpoints/rappi2_reportes-paradas_actualizar-rutas.jpeg)
![Eliminar rutas](images/miguel_endpoints/rappi2_reportes-paradas_eliminar-rutas.jpeg)

![Listar paradas (rutas)](images/miguel_endpoints/rappi2_reportes-paradas_listar-paradas-rutas.jpeg)
![Obtener parada (rutas)](images/miguel_endpoints/rappi2_reportes-paradas_obtener-paradas-rutas.jpeg)
![Crear paradas (rutas)](images/miguel_endpoints/rappi2_reportes-paradas_crear-paradas-rutas.jpeg)
![Actualizar paradas (rutas)](images/miguel_endpoints/rappi2_reportes-paradas_actualizar-paradas-rutas.jpeg)
![Eliminar paradas (rutas)](images/miguel_endpoints/rappi2_reportes-paradas_eliminar-paradas-rutas.jpeg)

---
