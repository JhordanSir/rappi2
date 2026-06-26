import { useMemo, useState } from "react";
import { Polygon, Polyline, CircleMarker, Tooltip as LTooltip } from "react-leaflet";
import { Plus, Trash2, Hexagon, Check, X, Undo2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useGeocercas, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Geocerca } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Field, Select } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { MapView, type LatLng } from "@/components/map/MapView";

// El corredor de ruta (ruta_buffer) se genera automáticamente al planificar; aquí se
// dibujan zonas de entrega, zonas prohibidas y la zona de restricción vehicular (plaqueo).
const TIPOS = ["zona_entrega", "prohibida", "restriccion_vehicular"] as const;
const TIPO_COLOR: Record<string, string> = { zona_entrega: "#10b981", ruta_buffer: "#0d9488", prohibida: "#f43f5e", restriccion_vehicular: "#f59e0b" };
const TIPO_TONE: Record<string, string> = { zona_entrega: "green", ruta_buffer: "brand", prohibida: "red", restriccion_vehicular: "amber" };
const TIPO_LABEL: Record<string, string> = { zona_entrega: "Zona de entrega", ruta_buffer: "Corredor de ruta", prohibida: "Zona prohibida", restriccion_vehicular: "Restricción vehicular (plaqueo)" };

function ring(g: Geocerca): LatLng[] {
  if (g.geometry?.type !== "Polygon") return [];
  const coords = (g.geometry.coordinates as number[][][])[0] ?? [];
  return coords.map((c) => [c[1], c[0]] as LatLng);
}

export default function GeocercasPage() {
  const { can } = useAuth();
  const [soloActivas, setSoloActivas] = useState(true);
  const { data, isLoading } = useGeocercas(soloActivas ? { activa: true } : {});
  const [draw, setDraw] = useState(false);
  const [draft, setDraft] = useState<LatLng[]>([]);
  const [tipo, setTipo] = useState<(typeof TIPOS)[number]>("zona_entrega");
  const [toDelete, setToDelete] = useState<Geocerca | null>(null);
  const writable = can("geocercas", "write");

  const crear = useApiMutation((body: any) => api.post("/geocercas", body), ["geocercas"]);
  const del = useApiMutation((id: string) => api.delete(`/geocercas/${id}`), ["geocercas"]);
  const reactivar = useApiMutation((id: string) => api.patch(`/geocercas/${id}`, { activa: true }), ["geocercas"]);

  const allPoints = useMemo(() => (data ?? []).flatMap(ring), [data]);

  const guardar = () => {
    if (draft.length < 3) return toast.error("Marca al menos 3 puntos en el mapa");
    const ringLonLat = draft.map(([la, lo]) => [lo, la]);
    ringLonLat.push(ringLonLat[0]); // cerrar anillo
    crear.mutate(
      { tipo, coordinates: [ringLonLat], activa: true },
      {
        onSuccess: () => { toast.success("Geocerca creada"); setDraft([]); setDraw(false); },
        onError: (e) => toast.error(apiError(e)),
      },
    );
  };

  return (
    <div>
      <PageHeader
        title="Geocercas"
        subtitle="Zonas de entrega, corredores de ruta y áreas restringidas sobre el mapa de Arequipa"
        actions={
          writable &&
          (draw ? (
            <>
              <Button variant="outline" onClick={() => setDraft((d) => d.slice(0, -1))} disabled={!draft.length}><Undo2 className="h-4 w-4" /> Deshacer</Button>
              <Button variant="outline" onClick={() => { setDraw(false); setDraft([]); }}><X className="h-4 w-4" /> Cancelar</Button>
              <Button variant="success" loading={crear.isPending} onClick={guardar}><Check className="h-4 w-4" /> Guardar zona ({draft.length})</Button>
            </>
          ) : (
            <Button onClick={() => setDraw(true)}><Plus className="h-4 w-4" /> Dibujar zona</Button>
          ))
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="overflow-hidden">
            <CardHeader
              title="Mapa de geocercas"
              subtitle={draw ? "Haz clic para agregar vértices; mínimo 3" : "Polígonos activos en el sistema"}
              action={draw && <Badge tone="amber">Modo dibujo</Badge>}
            />
            <MapView points={allPoints.length ? allPoints : draft} height={480} onClick={draw ? (p) => setDraft((d) => [...d, p]) : undefined}>
              {(data ?? []).map((g) => {
                const pts = ring(g);
                if (pts.length < 3) return null;
                return (
                  <Polygon key={g.id} positions={pts} pathOptions={{ color: TIPO_COLOR[g.tipo] ?? "#0d9488", weight: 2, fillOpacity: 0.12 }}>
                    <LTooltip>{TIPO_LABEL[g.tipo] ?? g.tipo} {g.activa ? "" : "(inactiva)"}</LTooltip>
                  </Polygon>
                );
              })}
              {draft.length > 0 && (
                <>
                  {draft.length >= 3 ? (
                    <Polygon positions={draft} pathOptions={{ color: TIPO_COLOR[tipo], weight: 2, dashArray: "6 6", fillOpacity: 0.15 }} />
                  ) : (
                    <Polyline positions={draft} pathOptions={{ color: TIPO_COLOR[tipo], weight: 2, dashArray: "6 6" }} />
                  )}
                  {draft.map((p, i) => (
                    <CircleMarker key={i} center={p} radius={5} pathOptions={{ color: "#fff", weight: 2, fillColor: TIPO_COLOR[tipo], fillOpacity: 1 }} />
                  ))}
                </>
              )}
            </MapView>
            {draw && (
              <CardBody className="flex items-center gap-3 border-t border-sillar-100">
                <Field label="Tipo de zona" className="w-56">
                  <Select value={tipo} onChange={(e) => setTipo(e.target.value as any)}>
                    {TIPOS.map((t) => <option key={t} value={t}>{TIPO_LABEL[t] ?? t}</option>)}
                  </Select>
                </Field>
                <p className="text-sm text-stone-500">{draft.length} vértices marcados</p>
              </CardBody>
            )}
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader
              title="Listado"
              action={
                <label className="flex items-center gap-1.5 text-xs text-stone-500">
                  <input type="checkbox" checked={soloActivas} onChange={(e) => setSoloActivas(e.target.checked)} className="h-3.5 w-3.5 rounded border-stone-300" />
                  Solo activas
                </label>
              }
            />
            <div className="max-h-[460px] divide-y divide-sillar-100 overflow-y-auto">
              {isLoading && <p className="px-5 py-6 text-center text-sm text-stone-400">Cargando…</p>}
              {data?.length === 0 && <p className="px-5 py-8 text-center text-sm text-stone-400">Sin geocercas</p>}
              {data?.map((g) => (
                <div key={g.id} className="flex items-center justify-between gap-2 px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <Hexagon className="h-4 w-4" style={{ color: TIPO_COLOR[g.tipo] }} />
                    <div>
                      <p className="text-sm font-medium text-stone-800">{TIPO_LABEL[g.tipo] ?? g.tipo}</p>
                      <p className="text-xs text-stone-400">{g.ruta_id ? `Ruta #${g.ruta_id}` : "Manual"} {g.tolerance_m ? `· ${g.tolerance_m}m` : ""}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge tone={(TIPO_TONE[g.tipo] ?? "gray") as any}>{g.activa ? "activa" : "inactiva"}</Badge>
                    {writable && (g.activa ? (
                      <Button size="icon" variant="ghost" className="text-rose-500" title="Desactivar" onClick={() => setToDelete(g)}><Trash2 className="h-4 w-4" /></Button>
                    ) : (
                      <Button size="icon" variant="ghost" className="text-emerald-600" title="Reactivar" loading={reactivar.isPending} onClick={() => reactivar.mutate(g.id, { onSuccess: () => toast.success("Geocerca reactivada"), onError: (e) => toast.error(apiError(e)) })}><Undo2 className="h-4 w-4" /></Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <ConfirmModal
        open={!!toDelete}
        title="Desactivar geocerca"
        description="La geocerca dejará de evaluarse. ¿Continuar?"
        danger
        confirmLabel="Desactivar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Geocerca desactivada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}
