import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, LogOut, ChevronDown, MonitorSmartphone } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
import { NotificationsBell } from "./NotificationsBell";
import { initials } from "@/lib/utils";

function useClickOutside<T extends HTMLElement>(onOut: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOut();
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [onOut]);
  return ref;
}

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-sillar-200 bg-white/80 px-4 backdrop-blur sm:px-6">
      <button onClick={onMenu} className="rounded-lg p-2 text-stone-600 hover:bg-sillar-100 lg:hidden">
        <Menu className="h-5 w-5" />
      </button>
      <div className="hidden lg:block" />

      <div className="flex items-center gap-1">
        <NotificationsBell />
        <div className="relative" ref={ref}>
          <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-2.5 rounded-lg py-1.5 pl-1.5 pr-2 hover:bg-sillar-100">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
              {initials(user?.username)}
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold leading-tight text-stone-800">{user?.username}</p>
              <p className="text-xs leading-tight text-stone-500">{user?.rol?.nombre ?? "—"}</p>
            </div>
            <ChevronDown className="h-4 w-4 text-stone-400" />
          </button>

          {open && (
            <div className="absolute right-0 mt-2 w-56 animate-fade-in rounded-xl border border-sillar-300 bg-white p-1.5 shadow-soft">
              <div className="px-3 py-2">
                <p className="truncate text-sm font-medium text-stone-800">{user?.email}</p>
                <p className="text-xs text-stone-500">Rol: {user?.rol?.nombre ?? "—"}</p>
              </div>
              <div className="my-1 h-px bg-sillar-200" />
              <button
                onClick={() => { setOpen(false); navigate("/sesiones"); }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-stone-700 hover:bg-sillar-100"
              >
                <MonitorSmartphone className="h-4 w-4" /> Mis sesiones
              </button>
              <button
                onClick={() => logout().then(() => toast.success("Sesión cerrada"))}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-rose-600 hover:bg-rose-50"
              >
                <LogOut className="h-4 w-4" /> Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
