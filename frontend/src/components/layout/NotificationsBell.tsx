import { useState, useRef, useEffect } from "react";
import { Bell, Check, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useNotificaciones, useApiMutation } from "@/api/hooks";
import { timeAgo } from "@/lib/utils";

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

/**
 * Campana de notificaciones compartida por todas las experiencias (admin,
 * despachador, cliente y conductor). Se refresca por polling y, sobre todo, en
 * tiempo real cuando `useRealtime` invalida la query ["notificaciones"].
 */
export function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const ref = useClickOutside<HTMLDivElement>(() => setOpen(false));
  const { data } = useNotificaciones({ limit: 20 }, 30000);
  const leer = useApiMutation((id: string) => api.patch(`/notificaciones/${id}/leer`), ["notificaciones"]);
  const borrar = useApiMutation((id: string) => api.delete(`/notificaciones/${id}`), ["notificaciones"]);
  const items = data ?? [];
  const unread = items.filter((n) => !n.leida).length;

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="relative rounded-lg p-2 text-stone-500 hover:bg-sillar-100">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 animate-fade-in overflow-hidden rounded-xl border border-sillar-300 bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-sillar-200 px-4 py-3">
            <p className="text-sm font-semibold text-stone-800">Notificaciones</p>
            {unread > 0 && <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">{unread} sin leer</span>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 && <p className="px-4 py-8 text-center text-sm text-stone-400">Sin notificaciones</p>}
            {items.map((n) => (
              <div key={n.id} className={`group flex gap-2 border-b border-sillar-100 px-4 py-3 ${!n.leida ? "bg-brand-50/40" : ""}`}>
                <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.leida ? "bg-stone-300" : "bg-brand-500"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-stone-800">{n.titulo}</p>
                  <p className="text-xs text-stone-500">{n.mensaje}</p>
                  <p className="mt-0.5 text-[11px] text-stone-400">{timeAgo(n.fecha)}</p>
                </div>
                <div className="flex flex-col gap-1 opacity-0 transition group-hover:opacity-100">
                  {!n.leida && (
                    <button title="Marcar leída" onClick={() => leer.mutate(n.id)} className="rounded p-1 text-stone-400 hover:bg-brand-50 hover:text-brand-600">
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button title="Eliminar" onClick={() => borrar.mutate(n.id)} className="rounded p-1 text-stone-400 hover:bg-rose-50 hover:text-rose-600">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
