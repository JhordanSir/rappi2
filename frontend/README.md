# Rappi2 · Frontend

Panel web (SPA) para la plataforma de logística y tracking **Rappi2**. Consume el API FastAPI
y ofrece gestión operativa completa con mapas en tiempo real.

## Stack

- **React 18 + TypeScript + Vite**
- **Tailwind CSS** (design system propio, look SaaS moderno)
- **TanStack Query** (data fetching, caché e invalidación)
- **React Router** (ruteo + rutas protegidas por sesión)
- **React-Leaflet + Leaflet** (mapas, marcadores, geocercas, selección de coordenadas)
- **Recharts** (gráficas de KPIs/reportes)
- **Axios** con interceptores (Bearer + refresh token automático)

## Módulos (cubren los principales endpoints del backend)

| Módulo | Qué hace | Endpoints |
|---|---|---|
| **Auth** | Login con JWT, refresh automático, RBAC | `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/logout` |
| **Dashboard** | KPIs + recaudación + órdenes por estado + top clientes | `/reportes/dashboard`, `/operativo`, `/ventas`, `/top-clientes` |
| **Clientes** | CRUD + direcciones con **lat/lon** (selector en mapa) | `/clientes`, `/clientes/{id}/direcciones` |
| **Órdenes** | Lista + alta con **mapa de origen/destino** + detalle con **tracking en vivo** | `/ordenes`, `/tracking/orden/{id}`, `/rutas/planificar` |
| **Asignaciones** | Flujo crear → iniciar → finalizar con **confirmación de entrega** | `/asignaciones`, `/iniciar`, `/finalizar` |
| **Conductores / Vehículos** | CRUD de flota | `/conductores`, `/vehiculos` |
| **Rutas** | Rutas planificadas (ORS) y sus paradas | `/rutas` |
| **Tracking en vivo** | Mapa con **conductores cercanos** a un punto ($geoNear) | `/tracking/conductores-cerca` |
| **Incidencias** | Registro y listado por severidad | `/incidencias` |
| **Pagos / Facturas** | Cobros y comprobantes por orden | `/pagos`, `/facturas` |
| **Geocercas** | Mapa con **dibujo de polígonos** (zona de entrega / corredor / restringida), listar y desactivar | `/geocercas` |
| **Incidencias** | Registro + **evidencias** (subir/listar/descargar archivos GridFS) | `/incidencias`, `/incidencias/{id}/evidencias` |
| **Notificaciones** | Campana en la barra superior (no leídas, marcar leída, eliminar) | `/notificaciones/mias` |
| **Reportes** | Ventas, tiempos de entrega, incidencias, desempeño | `/reportes/*` |
| **Usuarios / Roles** | Administración de cuentas y permisos (RBAC) | `/usuarios`, `/roles` |
| **Auditoría** | Logs HTTP + resumen (KPIs por método/estado) | `/auditoria`, `/auditoria/resumen` |
| **Sesiones** | Mis sesiones activas + revocar (desde el menú de usuario) | `/usuarios/me/sesiones` |

La navegación lateral se filtra automáticamente según los **permisos** del rol del usuario.

## Identidad visual

Ambientación **arequipeña** inspirada en el logo (gopher de Go sobre scooter):

- **Teal** (gopher) como color primario · **ámbar** (scooter / sol) como acento.
- Fondos **sillar** (cremas cálidos de la Ciudad Blanca) y sidebar en piedra volcánica.
- Mapas centrados en **Arequipa** (Plaza de Armas) y login con silueta del **Misti**.
- Logo `public/rapi2.png` usado en sidebar, login y favicon.

## Cómo ejecutar

### Opción A — Todo con Docker (recomendado)

Desde la raíz del repo (levanta postgres, mongo, api y frontend):

```bash
docker compose up --build
```

- Frontend: <http://localhost:5173>
- API / Swagger: <http://localhost:8000/docs>
- Login demo: **admin / admin123**

### Datos de prueba (Arequipa)

Para poblar todos los módulos con datos demo (clientes, flota, órdenes en todos los
estados, asignaciones, rutas, pagos/facturas, incidencias, pings GPS en vivo, geocercas y
notificaciones):

```bash
docker compose exec api python -m scripts.seed_demo
```

Usuarios creados (password `demo123`, salvo admin):

| Usuario | Rol | Para probar |
|---|---|---|
| `admin` / `admin123` | Admin | Todo |
| `despachador` | Despachador | Operación (sin admin) |
| `conductor1`…`conductor6` | Conductor | Vista de conductor |
| `cliente` | Cliente | Aislamiento "Mis órdenes" |

### Opción B — Desarrollo local (hot reload)

Requiere Node 18+. El backend debe estar corriendo en `:8000`
(`docker compose up postgres mongodb api`).

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxy /api -> :8000)
```

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `VITE_API_URL` | Base del API | `/api` (proxy en dev / nginx en prod) |

## Scripts

- `npm run dev` — servidor de desarrollo
- `npm run build` — build de producción (`dist/`)
- `npm run typecheck` — chequeo de tipos TypeScript
- `npm run preview` — previsualizar el build

## Estructura

```
src/
  api/hooks.ts          # hooks de datos (TanStack Query) por recurso
  auth/AuthContext.tsx  # sesión, login/logout, can(recurso,accion)
  components/
    ui/                 # design system (Button, Card, Table, Modal, …)
    layout/             # Sidebar, Topbar, AppLayout, ProtectedRoute
    map/                # MapView, LocationPicker, iconos Leaflet
  lib/                  # api (axios+refresh), utils (formatos), queryClient
  pages/                # una página por módulo
  types/                # tipos alineados a los schemas del backend
```
