import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
  Route as RouteIcon,
  Navigation,
  Users,
  Truck,
  UserSquare2,
  CreditCard,
  ReceiptText,
  TriangleAlert,
  BarChart3,
  Shield,
  UserCog,
  Hexagon,
  ScrollText,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  /** recurso requerido (read). null = siempre visible. */
  recurso: string | null;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    title: "General",
    items: [{ label: "Dashboard", to: "/", icon: LayoutDashboard, recurso: null }],
  },
  {
    title: "Operación",
    items: [
      { label: "Órdenes", to: "/ordenes", icon: Package, recurso: "ordenes" },
      { label: "Asignaciones", to: "/asignaciones", icon: ClipboardList, recurso: "asignaciones" },
      { label: "Rutas", to: "/rutas", icon: RouteIcon, recurso: "rutas" },
      { label: "Geocercas", to: "/geocercas", icon: Hexagon, recurso: "geocercas" },
      { label: "Tracking en vivo", to: "/tracking", icon: Navigation, recurso: "tracking" },
    ],
  },
  {
    title: "Flota",
    items: [
      { label: "Conductores", to: "/conductores", icon: UserSquare2, recurso: "conductores" },
      { label: "Vehículos", to: "/vehiculos", icon: Truck, recurso: "vehiculos" },
    ],
  },
  {
    title: "Comercial",
    items: [
      { label: "Clientes", to: "/clientes", icon: Users, recurso: "clientes" },
      { label: "Pagos", to: "/pagos", icon: CreditCard, recurso: "pagos" },
      { label: "Facturas", to: "/facturas", icon: ReceiptText, recurso: "facturas" },
    ],
  },
  {
    title: "Soporte & Análisis",
    items: [
      { label: "Incidencias", to: "/incidencias", icon: TriangleAlert, recurso: "incidencias" },
      { label: "Reportes", to: "/reportes", icon: BarChart3, recurso: "reportes" },
    ],
  },
  {
    title: "Administración",
    items: [
      { label: "Usuarios", to: "/usuarios", icon: UserCog, recurso: "usuarios" },
      { label: "Roles & Permisos", to: "/roles", icon: Shield, recurso: "roles" },
      { label: "Auditoría", to: "/auditoria", icon: ScrollText, recurso: "auditoria" },
    ],
  },
];
