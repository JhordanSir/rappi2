import { Navigate } from "react-router-dom";
import { Truck, Navigation, ShieldCheck, LogIn } from "lucide-react";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/Button";

export default function LoginPage() {
  const { user, login } = useAuth();

  if (user) return <Navigate to="/" replace />;

  return (
    <div className="flex min-h-screen">
      {/* Panel de marca · Arequipa */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-ink-900 p-12 text-white lg:flex">
        <div className="absolute inset-0 bg-gradient-to-br from-ink-900 via-ink-800 to-brand-950" />
        {/* sol arequipeño */}
        <div className="absolute right-16 top-20 h-28 w-28 rounded-full bg-sun-400/80 blur-[2px] shadow-[0_0_80px_30px_rgba(251,191,36,.35)]" />
        {/* silueta del Misti */}
        <svg className="absolute bottom-0 left-0 w-full text-ink-900" viewBox="0 0 600 200" preserveAspectRatio="none" fill="currentColor">
          <path opacity="0.55" d="M0 200 L120 80 L180 130 L300 40 L360 95 L470 55 L600 150 L600 200 Z" />
          <path d="M0 200 L150 120 L230 160 L330 90 L420 140 L520 100 L600 170 L600 200 Z" />
        </svg>

        <div className="relative flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
            <img src="/logo.png" alt="Rappi2" className="h-9 w-9 object-contain" />
          </div>
          <div>
            <p className="text-lg font-bold">Rappi2</p>
            <p className="-mt-1 text-sm text-sun-300">Logística desde la Ciudad Blanca</p>
          </div>
        </div>

        <div className="relative">
          <h1 className="max-w-md text-4xl font-bold leading-tight">
            Cada entrega bajo el <span className="text-sun-400">Misti</span>, en tiempo real.
          </h1>
          <p className="mt-4 max-w-md text-stone-300">
            Gestiona órdenes, asigna conductores, planifica rutas y sigue cada paquete sobre el mapa
            de Arequipa — desde un solo lugar.
          </p>
          <div className="mt-8 grid grid-cols-1 gap-3 text-sm">
            {[
              { icon: Navigation, t: "Seguimiento GPS y geocercas" },
              { icon: Truck, t: "Flota, conductores y asignaciones" },
              { icon: ShieldCheck, t: "Acceso por roles y permisos" },
            ].map(({ icon: Icon, t }) => (
              <div key={t} className="flex items-center gap-3 text-stone-200">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="h-4 w-4 text-sun-300" />
                </div>
                {t}
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-stone-400">© {new Date().getFullYear()} Rappi2 · Arequipa, Perú 🇵🇪</p>
      </div>

      {/* Acceso */}
      <div className="flex w-full items-center justify-center bg-sillar-100 px-6 lg:w-1/2">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white shadow-card">
              <img src="/logo.png" alt="Rappi2" className="h-9 w-9 object-contain" />
            </div>
            <p className="text-lg font-bold text-stone-900">Rappi2</p>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-stone-900">Iniciar sesión</h2>
          <p className="mt-1 text-sm text-stone-500">
            Te redirigiremos a Keycloak para autenticarte de forma segura.
          </p>

          <Button onClick={login} size="lg" className="mt-8 w-full">
            <LogIn className="mr-2 h-5 w-5" />
            Iniciar sesión con Keycloak
          </Button>

          <div className="mt-6 rounded-xl border border-sillar-300 bg-white p-3 text-center text-xs text-stone-500">
            Demo: <span className="font-semibold text-stone-700">admin</span> /{" "}
            <span className="font-semibold text-stone-700">admin123</span>
          </div>
        </div>
      </div>
    </div>
  );
}
