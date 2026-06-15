import { lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { AppLayout } from "@/components/layout/AppLayout";
import LoginPage from "@/pages/LoginPage";

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
const AuditoriaPage = lazy(() => import("@/pages/AuditoriaPage"));
const SesionesPage = lazy(() => import("@/pages/SesionesPage"));

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
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
        <Route path="/usuarios" element={<UsuariosPage />} />
        <Route path="/roles" element={<RolesPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
