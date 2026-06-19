import { lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { AppLayout } from "@/components/layout/AppLayout";
import { ClienteLayout } from "@/components/layout/ClienteLayout";
import { ConductorLayout } from "@/components/layout/ConductorLayout";
import { useAuth } from "@/auth/AuthContext";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";

// Code-splitting: cada página se carga bajo demanda (chunk por ruta).
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const ClientesPage = lazy(() => import("@/pages/ClientesPage"));
const OrdenesPage = lazy(() => import("@/pages/OrdenesPage"));
const OrdenDetailPage = lazy(() => import("@/pages/OrdenDetailPage"));
const AsignacionesPage = lazy(() => import("@/pages/AsignacionesPage"));
const ConductoresPage = lazy(() => import("@/pages/ConductoresPage"));
const VehiculosPage = lazy(() => import("@/pages/VehiculosPage"));
const RutasPage = lazy(() => import("@/pages/RutasPage"));
const GeocercasPage = lazy(() => import("@/pages/GeocercasPage"));
const IncidenciasPage = lazy(() => import("@/pages/IncidenciasPage"));
const TrackingPage = lazy(() => import("@/pages/TrackingPage"));
const ReportesPage = lazy(() => import("@/pages/ReportesPage"));
const PagosPage = lazy(() => import("@/pages/PagosPage"));
const FacturasPage = lazy(() => import("@/pages/FacturasPage"));
const UsuariosPage = lazy(() => import("@/pages/UsuariosPage"));
const RolesPage = lazy(() => import("@/pages/RolesPage"));
const TarifaPage = lazy(() => import("@/pages/TarifaPage"));
const AuditoriaPage = lazy(() => import("@/pages/AuditoriaPage"));
const SesionesPage = lazy(() => import("@/pages/SesionesPage"));

// Experiencias de usuario final
const ClienteHome = lazy(() => import("@/pages/cliente/ClienteHome"));
const NuevoEnvio = lazy(() => import("@/pages/cliente/NuevoEnvio"));
const SeguimientoCliente = lazy(() => import("@/pages/cliente/SeguimientoCliente"));
const CalificarOrden = lazy(() => import("@/pages/cliente/CalificarOrden"));
const PagoSimulado = lazy(() => import("@/pages/cliente/PagoSimulado"));
const PagoEstado = lazy(() => import("@/pages/cliente/PagoEstado"));
const ConductorHome = lazy(() => import("@/pages/conductor/ConductorHome"));
const AsignacionDetalle = lazy(() => import("@/pages/conductor/AsignacionDetalle"));

/** Experiencia interna (Admin / Despachador): el panel administrativo/operativo. */
function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/clientes" element={<ClientesPage />} />
        <Route path="/ordenes" element={<OrdenesPage />} />
        <Route path="/ordenes/:id" element={<OrdenDetailPage />} />
        <Route path="/asignaciones" element={<AsignacionesPage />} />
        <Route path="/conductores" element={<ConductoresPage />} />
        <Route path="/vehiculos" element={<VehiculosPage />} />
        <Route path="/rutas" element={<RutasPage />} />
        <Route path="/geocercas" element={<GeocercasPage />} />
        <Route path="/incidencias" element={<IncidenciasPage />} />
        <Route path="/tracking" element={<TrackingPage />} />
        <Route path="/auditoria" element={<AuditoriaPage />} />
        <Route path="/sesiones" element={<SesionesPage />} />
        <Route path="/reportes" element={<ReportesPage />} />
        <Route path="/pagos" element={<PagosPage />} />
        <Route path="/facturas" element={<FacturasPage />} />
        <Route path="/tarifa" element={<TarifaPage />} />
        <Route path="/usuarios" element={<UsuariosPage />} />
        <Route path="/roles" element={<RolesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** Experiencia de Cliente (autoservicio): mis pedidos, crear/pagar, seguir, calificar. */
function ClienteRoutes() {
  return (
    <Routes>
      <Route element={<ClienteLayout />}>
        <Route path="/" element={<ClienteHome />} />
        <Route path="/nuevo" element={<NuevoEnvio />} />
        <Route path="/orden/:id" element={<SeguimientoCliente />} />
        <Route path="/orden/:id/calificar" element={<CalificarOrden />} />
        <Route path="/pago/simulado" element={<PagoSimulado />} />
        <Route path="/pago/exito" element={<PagoEstado estado="exito" />} />
        <Route path="/pago/fallo" element={<PagoEstado estado="fallo" />} />
        <Route path="/pago/pendiente" element={<PagoEstado estado="pendiente" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** Experiencia de Conductor (PWA mobile-first). Las pantallas se amplían en la Fase 3. */
function ConductorRoutes() {
  return (
    <Routes>
      <Route element={<ConductorLayout />}>
        <Route path="/" element={<ConductorHome />} />
        <Route path="/asignacion/:id" element={<AsignacionDetalle />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** Enruta a la experiencia correspondiente según el rol del usuario autenticado. */
function RoleApp() {
  const { user } = useAuth();
  const rol = user?.rol?.nombre;
  if (rol === "Cliente" || user?.cliente_id != null) return <ClienteRoutes />;
  if (rol === "Conductor") return <ConductorRoutes />;
  return <AdminRoutes />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registro" element={<RegisterPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <RoleApp />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
