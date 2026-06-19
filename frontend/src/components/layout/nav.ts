import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Package,
  ClipboardList,
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
  Tag,
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

// Panel reagrupado en 4 áreas. Rutas y la evidencia de entrega viven dentro del
// detalle de la orden; las incidencias (incluidas las automáticas) se gestionan aquí.
export const NAV: NavGroup[] = [
  {
    title: "Operación",
    items: [
      { label: "Dashboard", to: "/", icon: LayoutDashboard, recurso: null },
      { label: "Órdenes", to: "/ordenes", icon: Package, recurso: "ordenes" },
      { label: "Asignaciones", to: "/asignaciones", icon: ClipboardList, recurso: "asignaciones" },
      { label: "Tracking en vivo", to: "/tracking", icon: Navigation, recurso: "tracking" },
      { label: "Incidencias", to: "/incidencias", icon: TriangleAlert, recurso: "incidencias" },
      { label: "Geocercas", to: "/geocercas", icon: Hexagon, recurso: "geocercas" },
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
      { label: "Tarifa", to: "/tarifa", icon: Tag, recurso: "tarifa" },
      { label: "Reportes", to: "/reportes", icon: BarChart3, recurso: "reportes" },
    ],
  },
  {
    title: "Sistema",
    items: [
      { label: "Usuarios", to: "/usuarios", icon: UserCog, recurso: "usuarios" },
      { label: "Roles & Permisos", to: "/roles", icon: Shield, recurso: "roles" },
      { label: "Auditoría", to: "/auditoria", icon: ScrollText, recurso: "auditoria" },
    ],
  },
];
