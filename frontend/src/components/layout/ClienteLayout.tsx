import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { LogOut, Package } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
import { NotificationsBell } from "./NotificationsBell";
import { PageLoader } from "@/components/ui/Feedback";
import { useRealtime } from "@/api/useRealtime";

/**
 * Shell de la experiencia de Cliente (autoservicio). En la Fase 1 es el contenedor
 * con cabecera (marca + campana en tiempo real + cerrar sesión); las pantallas de
 * crear/pagar/rastrear/calificar se construyen en la Fase 2.
 */
export function ClienteLayout() {
  const { user, logout } = useAuth();
  useRealtime();
  return (
    <div className="flex min-h-screen flex-col bg-sillar-100">
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-sillar-200 bg-white/80 px-4 backdrop-blur sm:px-6">
        <div className="flex items-center gap-2 font-semibold text-brand-700">
          <Package className="h-5 w-5" />
          Rappi2 · Mis envíos
        </div>
        <div className="flex items-center gap-2">
          <NotificationsBell />
          <span className="hidden text-sm text-stone-600 sm:block">{user?.username}</span>
          <button
            onClick={() => logout().then(() => toast.success("Sesión cerrada"))}
            title="Cerrar sesión"
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-rose-600 hover:bg-rose-50"
          >
            <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Salir</span>
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-5xl">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
