import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Truck, Star, ChevronRight, PackageCheck, Navigation } from "lucide-react";
import { api } from "@/lib/api";
import { PageLoader } from "@/components/ui/Feedback";
import { formatDate } from "@/lib/utils";
import type { Asignacion, Conductor } from "@/types";

const ESTADO_LABEL: Record<string, string> = {
  Asignada: "Por iniciar",
  EnCurso: "En curso",
  Finalizada: "Entregada",
  Cancelada: "Cancelada",
};

function AsignacionCard({ a, onClick }: { a: Asignacion; onClick: () => void }) {
  const activa = a.estado === "EnCurso";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-2xl border p-4 text-left transition ${
        activa ? "border-amber-500/50 bg-amber-500/10" : "border-stone-700 bg-stone-800 hover:bg-stone-700/60"
      }`}
    >
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${activa ? "bg-amber-500/20 text-amber-400" : "bg-stone-700 text-stone-300"}`}>
        <Navigation className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-stone-100">
          Run #{a.id}
          {(a.orden_ids?.length ?? 1) > 1 && <span className="ml-1 text-xs font-normal text-stone-400">· {a.orden_ids!.length} órdenes</span>}
        </p>
        <p className="text-xs text-stone-400">
          {ESTADO_LABEL[a.estado] ?? a.estado}
          {a.fecha_inicio && ` · inició ${formatDate(a.fecha_inicio, false)}`}
        </p>
      </div>
      <ChevronRight className="h-5 w-5 text-stone-500" />
    </button>
  );
}

export default function ConductorHome() {
  const navigate = useNavigate();
  const [verTodo, setVerTodo] = useState(false);
  const { data: me } = useQuery({
    queryKey: ["conductor-me"],
    queryFn: async () => (await api.get<Conductor>("/conductores/me")).data,
  });
  const { data: asgs, isLoading } = useQuery({
    queryKey: ["mis-asignaciones"],
    queryFn: async () => (await api.get<Asignacion[]>("/asignaciones/", { params: { limit: 100 } })).data,
  });
  const { data: rating } = useQuery({
    queryKey: ["mi-rating", me?.id],
    enabled: !!me?.id,
    queryFn: async () => (await api.get<{ promedio: number | null; total: number }>(`/conductores/${me!.id}/calificaciones`)).data,
  });

  if (isLoading) return <PageLoader />;
  const activas = (asgs ?? []).filter((a) => a.estado === "Asignada" || a.estado === "EnCurso");
  const historial = (asgs ?? []).filter((a) => a.estado === "Finalizada" || a.estado === "Cancelada");

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-stone-700 bg-stone-800 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400">
            <Truck className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <p className="font-semibold text-stone-100">{me?.nombre}</p>
            <p className="text-xs text-stone-400">Vehículo: {me?.vehiculo_placa ?? "—"}</p>
          </div>
          {rating && rating.total > 0 && (
            <div className="flex items-center gap-1 rounded-lg bg-stone-700 px-2.5 py-1 text-amber-400">
              <Star className="h-4 w-4 fill-amber-400" />
              <span className="text-sm font-semibold">{rating.promedio}</span>
              <span className="text-xs text-stone-400">({rating.total})</span>
            </div>
          )}
        </div>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-stone-400">Entregas activas</h2>
        {activas.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-stone-700 bg-stone-800/50 p-6 text-center text-sm text-stone-400">
            No tienes entregas asignadas ahora.
          </p>
        ) : (
          <div className="space-y-2">
            {activas.map((a) => (
              <AsignacionCard key={a.id} a={a} onClick={() => navigate(`/asignacion/${a.id}`)} />
            ))}
          </div>
        )}
      </section>

      {historial.length > 0 && (
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wide text-stone-400">
            <PackageCheck className="h-4 w-4" /> Historial <span className="normal-case text-stone-500">({historial.length})</span>
          </h2>
          <div className="space-y-2">
            {(verTodo ? historial : historial.slice(0, 10)).map((a) => (
              <AsignacionCard key={a.id} a={a} onClick={() => navigate(`/asignacion/${a.id}`)} />
            ))}
          </div>
          {historial.length > 10 && (
            <button
              type="button"
              onClick={() => setVerTodo((v) => !v)}
              className="mt-2 w-full rounded-2xl border border-dashed border-stone-700 bg-stone-800/50 p-3 text-center text-sm text-stone-300 hover:bg-stone-800"
            >
              {verTodo ? "Mostrar menos" : `Ver todo el historial (${historial.length})`}
            </button>
          )}
        </section>
      )}
    </div>
  );
}
