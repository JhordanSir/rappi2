import { NavLink } from "react-router-dom";
import { X } from "lucide-react";
import { NAV } from "./nav";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { can } = useAuth();

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-ink-900/40 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-ink-900 text-slate-300 transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/10">
              <img src="/logo.png" alt="Rappi2" className="h-8 w-8 object-contain" />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight text-white">Rappi2</p>
              <p className="-mt-0.5 text-[11px] text-sun-400">Logística · Arequipa</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-stone-400 hover:bg-white/10 lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6 pt-2">
          {NAV.map((group) => {
            const items = group.items.filter((it) => it.recurso === null || can(it.recurso, "read"));
            if (items.length === 0) return null;
            return (
              <div key={group.title}>
                <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {group.title}
                </p>
                <div className="space-y-0.5">
                  {items.map((it) => (
                    <NavLink
                      key={it.to}
                      to={it.to}
                      end={it.to === "/"}
                      onClick={onClose}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                          isActive
                            ? "bg-brand-600 text-white shadow-sm"
                            : "text-slate-300 hover:bg-white/5 hover:text-white",
                        )
                      }
                    >
                      <it.icon className="h-[18px] w-[18px]" />
                      {it.label}
                    </NavLink>
                  ))}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-white/10 px-5 py-3 text-[11px] text-stone-500">
          v1.0 · Hecho en la Ciudad Blanca
        </div>
      </aside>
    </>
  );
}
