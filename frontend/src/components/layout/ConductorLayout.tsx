import { Suspense } from "react";
import { Outlet } from "react-router-dom";
import { LogOut, Truck } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { NotificationsBell } from "./NotificationsBell";
import { PageLoader } from "@/components/ui/Feedback";
import { useRealtime } from "@/api/useRealtime";

/**
 * Shell de la experiencia de Conductor (mobile-first). En la Fase 1 es el
 * contenedor con cabecera compacta; las pantallas de ruta, iniciar/finalizar,
 * GPS y prueba de entrega se construyen en la Fase 3 (como PWA instalable).
 */
export function ConductorLayout() {
  const { user, logout } = useAuth();
  useRealtime();
  return (
    <div className="flex min-h-screen flex-col bg-stone-900 text-stone-100">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-stone-700 bg-stone-900/90 px-4 backdrop-blur">
        <div className="flex items-center gap-2 font-semibold text-amber-400">
          <Truck className="h-5 w-5" />
          Rappi2 · Conductor
        </div>
        <div className="flex items-center gap-2">
          <NotificationsBell />
          <span className="hidden text-sm text-stone-300 sm:block">{user?.username}</span>
          <button
            onClick={() => logout()}
            title="Cerrar sesión"
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-rose-400 hover:bg-stone-800"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto max-w-xl">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}
