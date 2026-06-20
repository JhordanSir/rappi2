import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Route as RouteIcon, ExternalLink, MapPin, Clock, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useRutas, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Ruta } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { PageLoader, EmptyState } from "@/components/ui/Feedback";
import { ConfirmModal } from "@/components/ui/Confirm";
import { formatCoord } from "@/lib/utils";

function intervalToText(iso?: string | null): string {
  if (!iso) return "—";
  const raw = String(iso);

  // El backend serializa el timedelta como duración ISO-8601 ("PT15M", "PT1H30M")
  // o, como respaldo, "H:MM:SS". Lo normalizamos a segundos para mostrarlo legible.
  let totalSec: number | null = null;
  const iso8601 = raw.match(/^P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$/);
  if (iso8601) {
    const [, d, h, m, s] = iso8601;
    totalSec = Number(d ?? 0) * 86400 + Number(h ?? 0) * 3600 + Number(m ?? 0) * 60 + Number(s ?? 0);
  } else {
    const parts = raw.split(".")[0].split(":").map(Number);
    if (parts.length === 3 && parts.every((n) => !Number.isNaN(n))) {
      totalSec = parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
  }
  if (totalSec === null) return raw; // formato desconocido: mostrar tal cual

  const totalMin = Math.round(totalSec / 60);
  if (totalMin < 1) return "<1 min";
  if (totalMin < 60) return `${totalMin} min`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

export default function RutasPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { data, isLoading } = useRutas({});
  const [toDelete, setToDelete] = useState<Ruta | null>(null);
  const del = useApiMutation((id: number) => api.delete(`/rutas/${id}`), ["rutas"]);

  if (isLoading) return <PageLoader />;

  return (
    <div>
      <PageHeader title="Rutas planificadas" subtitle="Rutas generadas con OpenRouteService y sus paradas" />
      {!data || data.length === 0 ? (
        <Card>
          <EmptyState
            icon={<RouteIcon className="h-7 w-7" />}
            title="Aún no hay rutas"
            description="Planifica una ruta desde el detalle de una orden con coordenadas de origen y destino."
            action={<Button onClick={() => navigate("/ordenes")}>Ir a órdenes</Button>}
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.map((r) => (
            <Card key={r.id}>
              <CardBody>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><RouteIcon className="h-4 w-4" /></div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800">Ruta #{r.id}</p>
                      <button onClick={() => navigate(`/ordenes/${r.orden_id}`)} className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline">
                        Orden #{r.orden_id} <ExternalLink className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  {can("rutas", "delete") && (
                    <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(r)}><Trash2 className="h-4 w-4" /></Button>
                  )}
                </div>
                <div className="mb-3 flex gap-2">
                  <Badge tone="blue"><MapPin className="h-3 w-3" /> {Number(r.distancia_km ?? 0).toFixed(1)} km</Badge>
                  <Badge tone="indigo"><Clock className="h-3 w-3" /> {intervalToText(r.tiempo_estimado)}</Badge>
                  <Badge tone="gray">{r.paradas.length} paradas</Badge>
                </div>
                <div className="space-y-2">
                  {r.paradas.slice(0, 4).map((p) => (
                    <div key={p.id} className="flex items-center gap-2 text-xs">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 font-bold text-slate-500">{p.secuencia}</span>
                      <span title={p.direccion} className="flex-1 truncate text-slate-600">{p.direccion}</span>
                      <StatusBadge kind="parada" value={p.estado} />
                    </div>
                  ))}
                  {r.paradas[0] && <p className="pl-7 font-mono text-[11px] text-slate-400">{formatCoord(r.paradas[0].lat, r.paradas[0].lon)}</p>}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar ruta"
        description={`¿Eliminar la ruta #${toDelete?.id} y sus paradas?`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Ruta eliminada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}
