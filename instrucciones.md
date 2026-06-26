# Vistas de Usuario Final — Rappi2 (Documento de Requerimientos por Fases)

## Contexto (por qué)

Rappi2 es una plataforma de logística/delivery (Arequipa, PE) con un backend FastAPI muy completo
(80+ endpoints, PostgreSQL + MongoDB, JWT/RBAC, tracking GPS, rutas OSRM, geocercas, incidencias,
evidencias GridFS, pagos, facturas, notificaciones) y un frontend React **que hoy es 100% panel
interno administrativo** (19 páginas). No existe ninguna experiencia pensada para el **usuario final**.

El objetivo es **contener vistas desde el punto de visualización de los usuarios finales** y cerrar las
brechas de endpoints/permisos/datos para sostenerlas. Tras la elicitación, el sistema tendrá **cuatro
experiencias por rol dentro de la misma app React**:

| Rol | Experiencia | Estado hoy |
|-----|-------------|-----------|
| **Cliente** | Portal de autoservicio (registro, crear+pagar, rastrear, historial, calificar) | ❌ No existe |
| **Conductor** | App de entrega PWA mobile-first (ruta, iniciar/finalizar, GPS, prueba, incidencias) | ❌ No existe |
| **Despachador** | Panel de operación (órdenes, asignación híbrida, rutas, geocercas, flota, tracking) | ⚠️ Mezclado con Admin |
| **Administrador** | Panel de sistema (usuarios, roles, auditoría, configuración, reportes globales) | ⚠️ Mezclado con Despachador |

## Decisiones cerradas en la elicitación

1. **Destino:** cuatro experiencias por rol **dentro de la misma app React** (mismo login, ruteo/landing por rol).
2. **Cliente:** autoservicio completo (registro abierto, crear y **pagar por adelantado**, gestionar direcciones, rastrear en vivo, historial, reportar incidencia, calificar).
3. **Conductor:** ciclo de entrega completo. Cuentas **provisionadas internamente** (no registro público). Forma: **PWA instalable mobile-first** con geolocalización del navegador.
4. **Pagos:** **MercadoPago, Checkout Pro** (redirección + webhook), **modo sandbox** con llaves del usuario. Moneda PEN. **Pago por adelantado**: la orden solo es despachable tras pago aprobado.
5. **Calificaciones:** el cliente califica la **entrega + conductor** (1–5 + comentario), expuesto como KPI. Requiere modelo + endpoints nuevos.
6. **Tiempo real:** **SSE + Redis pub/sub** como backplane (compatible con varios workers de uvicorn en prod). El conductor envía GPS por POST; el servidor empuja posición/estado al cliente por SSE.
7. **Notificaciones a usuarios finales:** in-app en tiempo real (campana + SSE), reutilizando la colección `notificaciones`.
8. **Asignación:** **híbrida** — el sistema sugiere el conductor disponible más cercano (geoNear que ya existe) y el despachador confirma.
9. **Administrador y Despachador:** experiencias **separadas** entre sí.
10. **Prioridad de construcción:** cimientos comunes → **Cliente** → Conductor → separación Despachador/Admin.

## Reutilización (lo que YA existe y se aprovecha)

- **Auth/onboarding:** `POST /auth/register` ya crea la ficha `Cliente` y enlaza `usuario.cliente_id` ([backend/api/auth.py:55-81](backend/api/auth.py#L55-L81)). Login/refresh/logout/me completos.
- **Órdenes, pagos, facturas, clientes+direcciones, asignaciones, rutas+paradas, incidencias+evidencias, tracking GPS, geocercas, notificaciones, reportes:** CRUD y consultas ya implementados.
- **Tracking/seguimiento:** `GET /api/tracking/orden/{orden_id}` ya agrega asignación + posición + ruta + paradas + geocercas + estadísticas (ideal para la vista de seguimiento del cliente).
- **Prueba de entrega:** `POST /api/asignaciones/{id}/prueba-entrega` (foto/firma → GridFS) ya existe (núcleo del cierre del conductor).
- **geoNear:** `GET /api/tracking/conductores-cerca` ya hace la consulta geoespacial para la sugerencia de asignación.
- **Paginación:** `core/pagination.py` (header `X-Total-Count`) + `usePaginated` en el front.
- **Permisos en front:** `useAuth().can(recurso, accion)` y `user.rol.nombre` / `user.cliente_id` ([frontend/src/auth/AuthContext.tsx:70-75](frontend/src/auth/AuthContext.tsx#L70-L75)).

## Cross-cutting (aplica a todas las fases)

- **Seguridad de fila (ownership):** el RBAC actual es solo recurso+acción. Los usuarios finales solo deben ver/operar **sus propios datos** (cliente → sus órdenes/pagos/incidencias/calificaciones; conductor → sus asignaciones/tracking). Se impone **en el backend** con una dependencia de alcance, no confiando en el filtro del cliente.
- **Mapeo usuario→entidad:** cliente vía `usuario.cliente_id`; conductor vía `Conductor.usuario_id` (resolver "mi conductor_id" del token).
- **Ruteo por rol en el front:** branch por `user.rol.nombre` a layouts distintos (Admin/Despachador/Conductor/Cliente). Hoy hay un único `AppLayout` plano ([frontend/src/App.tsx:27-59](frontend/src/App.tsx#L27-L59)).

---

# FASE 1 — Cimientos comunes (seguridad, roles, tiempo real)

**Objetivo:** dejar la plataforma lista para alojar experiencias por rol con seguridad y tiempo real. Al
terminar, cada rol aterriza en su propio "shell" (los de cliente/conductor pueden ser placeholders).

### Backend
- **Blindar registro público:** `POST /auth/register` debe **ignorar `rol_id`** del payload y forzar rol `Cliente` (evita escalada de privilegios). Mantener auto-creación de ficha + enlace. Archivo: [backend/api/auth.py](backend/api/auth.py), `schemas/auth.py`.
- **Expandir permisos por rol** (en `seed_admin.py`/`seed_demo.py` + migración de datos):
  - `Cliente` += `ordenes:write`, `pagos:read/write`, `clientes:write` (solo propias direcciones), `incidencias:read/write`, `calificaciones:read/write`, `facturas:read`, `notificaciones:read`, `tracking:read`.
  - `Conductor` += `asignaciones:write`, `entregas:write` (prueba de entrega), `conductores:read`, `calificaciones:read`, `rutas:write` (marcar parada visitada).
  - Nuevos recursos de permiso: `calificaciones`, `entregas`, `realtime`.
- **Capa de ownership:** dependencia FastAPI reutilizable (p. ej. `scope_cliente()` / `scope_conductor()`) que inyecta el `cliente_id`/`conductor_id` del usuario y filtra/valida en `ordenes`, `pagos`, `incidencias`, `asignaciones`, `tracking`. Archivos: [backend/api/dependencies.py](backend/api/dependencies.py) y los routers afectados.
- **Redis + SSE:**
  - Añadir servicio **Redis** a `docker-compose.yml` + `REDIS_URL` en [backend/core/config.py](backend/core/config.py).
  - Módulo `core/realtime.py`: publisher a Redis pub/sub + endpoint **`GET /api/realtime/stream`** (SSE) autenticado, suscrito a canales (`user:{id}`, `cliente:{id}`, `orden:{id}`, `asignacion:{id}`).
  - Publicar eventos en los puntos clave existentes: cambio de estado de orden/asignación, nuevo ping GPS, nueva notificación.

### Frontend
- **Ruteo por rol:** introducir `RoleRouter` que, según `user.rol.nombre`, monte `AdminLayout` / `DespachadorLayout` (de momento el panel actual para ambos) / `ClienteShell` / `ConductorShell`. Archivos: [frontend/src/App.tsx](frontend/src/App.tsx), nuevos layouts en `frontend/src/components/layout/`.
- **Cliente SSE:** hook `useRealtime()` (EventSource con token) que invalida queries de react-query y alimenta la campana de notificaciones.

### Verificación Fase 1
- Registrarse por `/register` pasando `rol_id` de Admin → el usuario queda como **Cliente** (no Admin).
- Login como `cliente`/`conductor`/`despachador`/`admin` → cada uno aterriza en su shell.
- Con `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`, Redis arriba; abrir `GET /api/realtime/stream` con token recibe un evento al crear una notificación.
- Un cliente NO puede leer la orden de otro cliente (403/filtrado), validado por endpoint.

---

# FASE 2 — Portal del Cliente (autoservicio · prioridad #1)

**Objetivo:** el cliente se registra, crea y **paga** su orden, la **rastrea en vivo**, ve su historial,
reporta problemas y **califica**.

### Backend
- **MercadoPago Checkout Pro** (`backend/services/payments/mercadopago.py` + `backend/api/pagos.py`):
  - `POST /api/ordenes/{orden_id}/checkout` → crea preferencia MP (PEN), devuelve `init_point` (URL de pago) y `back_urls`.
  - `POST /api/pagos/webhook/mercadopago` → webhook **público** verificado; al aprobarse, marca el `Pago` como `Pagado` y promueve la orden a despachable.
  - Config: `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `MP_WEBHOOK_SECRET`, `PUBLIC_BASE_URL` en `core/config.py` (sandbox).
- **Ciclo de orden con pago por adelantado:** la orden creada por el cliente nace en estado **"Pendiente de Pago"** (nuevo estado) y solo pasa a `Pendiente` (visible para el despachador) cuando el webhook confirma. Migración Alembic para el `CHECK` de `estado` en [backend/models/ordenes.py](backend/models/ordenes.py) + `alembic/versions/`.
- **Calificaciones (nuevo):**
  - Modelo `Calificacion` (`orden_id`, `conductor_id`, `cliente_id`, `puntaje` 1–5, `comentario`, `fecha`) + migración.
  - `POST /api/ordenes/{orden_id}/calificacion` (solo cliente dueño, orden `Entregado`), `GET .../calificacion`, `GET /api/conductores/{id}/calificaciones` (promedio).
- **Ownership en consultas del cliente:** `GET /api/ordenes/` y `/{id}`, `POST /api/ordenes/` (fuerza `cliente_id` del token), direcciones, `GET /api/tracking/orden/{id}`, incidencias propias, `GET /api/notificaciones/mias` (unificar destinatario `cliente` vs `usuario`).

### Frontend (vistas del Cliente)
- Registro/login de cliente · **Home "Mis pedidos"** (lista paginada con estado) · **Crear orden** (mapa origen/destino, direcciones guardadas) · **Checkout** (redirección a MP + páginas de retorno éxito/fallo/pendiente) · **Seguimiento en vivo** (mapa + SSE, posición del conductor, ETA, paradas) · **Detalle/historial** · **Reportar problema** · **Calificar entrega** · **Perfil/direcciones** · **Campana de notificaciones**.
- Reutiliza `MapView`, `usePaginated`, `Pagination`, `useRealtime`.

### Verificación Fase 2
- Cliente nuevo: registro → crear orden → redirige a MP sandbox → pagar con tarjeta de prueba → webhook → la orden aparece como `Pendiente` para el despachador.
- Tras asignación e inicio (desde panel), el cliente ve moverse al conductor en vivo (SSE) en su seguimiento.
- Al marcar `Entregado`, el cliente puede calificar; el promedio del conductor refleja la nota.
- Un cliente no ve órdenes/pagos de otro (ownership).

---

# FASE 3 — App del Conductor (PWA mobile-first)

**Objetivo:** el conductor opera su ciclo de entrega completo desde el móvil.

### Backend (mayormente reutilización; permisos ya ampliados en Fase 1)
- `GET /api/asignaciones/?mias` (alcance al `conductor_id` del token) · `GET /{id}` (propia).
- `PATCH /{id}/iniciar` y `/{id}/finalizar` (requieren `asignaciones:write` + ownership).
- `POST /api/tracking/ping` (validado: solo asignación propia y `EnCurso`).
- `POST /api/asignaciones/{id}/prueba-entrega` (foto/firma) · `PATCH /api/rutas/{ruta_id}/paradas/{id}/visitar`.
- Incidencias + evidencias (reutilizar) · `GET /api/conductores/{id}` (perfil propio + rating).

### Frontend (PWA)
- **PWA:** `manifest.webmanifest` + service worker (instalable, offline básico) en `frontend/`.
- Vistas mobile-first: **login** · **Mis asignaciones / Hoy** · **Detalle de asignación** (ruta + paradas en mapa) · **Iniciar/Finalizar** · **Captura GPS en vivo** (Geolocation API → ping periódico mientras `EnCurso`) · **Prueba de entrega** (cámara/firma) · **Reportar incidencia + evidencia** · **Historial**.

### Verificación Fase 3
- Instalar la PWA en un móvil/emulador; login como `conductor1`.
- Iniciar una asignación propia → el navegador emite pings GPS → el cliente los ve en su seguimiento (SSE).
- Subir prueba de entrega y finalizar → orden pasa a `Entregado`, conductor vuelve a `Disponible`.
- Un conductor no puede iniciar/ver la asignación de otro (ownership).

---

# FASE 4 — Separación Despachador/Admin + asignación híbrida + KPIs

**Objetivo:** dos paneles internos distintos y la asignación híbrida; cerrar KPIs nuevos.

### Backend
- **Sugerencia de asignación:** `GET /api/asignaciones/sugerencia?orden_id=` → mejor conductor disponible más cercano al origen (geoNear) + score; el despachador confirma con `POST /api/asignaciones/` existente.
- **KPIs:** integrar calificaciones en `reportes` (rating por conductor, ranking) y eventos a despachador/admin por SSE (nueva orden pendiente, conductor fuera de ruta).

### Frontend
- **Despachador:** panel de operación (órdenes pendientes/pagadas, asignación híbrida 1-clic, rutas, geocercas, tracking, flota, incidencias, reportes operativos).
- **Admin:** panel de sistema (usuarios, roles, auditoría, sesiones, configuración, reportes globales).
- Navegación/landing por rol y ocultamiento de módulos no correspondientes (refina el filtrado por `can()` ya existente).

### Verificación Fase 4
- Login `despachador` ve solo operación; login `admin` ve solo sistema.
- Sobre una orden pagada, "Sugerir conductor" propone el más cercano disponible; confirmar crea la asignación.
- El reporte de conductores muestra el rating promedio proveniente de Fase 2.

---

## Infraestructura nueva (resumen)

| Pieza | Dónde | Notas |
|-------|-------|-------|
| **Redis** | `docker-compose.yml`, `core/config.py` | Backplane pub/sub para SSE entre workers |
| **SSE** | `core/realtime.py`, `GET /api/realtime/stream` | Push de posición/estado/notificaciones |
| **MercadoPago** | `services/payments/`, `api/pagos.py`, `.env` | Checkout Pro sandbox (token, public key, webhook secret) |
| **Calificaciones** | `models/`, `api/`, migración Alembic | Tabla nueva + endpoints + KPI |
| **PWA** | `frontend/` (manifest + SW) | App del conductor instalable |

## Migraciones Alembic nuevas
- Estado de orden "Pendiente de Pago" (ajuste del `CHECK`).
- Tabla `calificaciones`.
- Campos de `pagos` para MercadoPago (`metodo`, `proveedor`, `preference_id`, `external_id`, `status`).
- Semilla de permisos ampliada por rol.

## Modo de avance
El documento está dividido en **4 fases**. **No se inicia una fase sin tu aprobación explícita**; al
terminar cada una se verifica y se te consulta antes de pasar a la siguiente (empezando por Fase 1).
