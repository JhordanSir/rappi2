import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Play, CheckCircle2, Trash2, ExternalLink } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useAsignaciones, useOrdenes, useConductores, useVehiculos, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Asignacion } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Toolbar, SearchInput } from "@/components/ui/Toolbar";
import { LocationPicker } from "@/components/map/MapView";
import { formatDate } from "@/lib/utils";

export default function AsignacionesPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const [creating, setCreating] = useState(false);
  const [finalizing, setFinalizing] = useState<Asignacion | null>(null);
  const [toDelete, setToDelete] = useState<Asignacion | null>(null);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useAsignaciones({ limit: 200 });
  const { data: conductores } = useConductores({ limit: 200 });
  const writable = can("asignaciones", "write");

  const condName = (id: number) => conductores?.find((c) => c.id === id)?.nombre ?? `#${id}`;
  const iniciar = useApiMutation((id: number) => api.patch(`/asignaciones/${id}/iniciar`), ["asignaciones", "ordenes"]);
  const del = useApiMutation((id: number) => api.delete(`/asignaciones/${id}`), ["asignaciones"]);

  const rows = useMemo(
    () => (data ?? []).filter((a) => !search || String(a.orden_id).includes(search) || a.vehiculo_placa.toLowerCase().includes(search.toLowerCase())),
    [data, search],
  );

  return (
    <div>
      <PageHeader
        title="Asignaciones"
        subtitle="Asigna órdenes a conductores y vehículos, e impulsa el flujo de entrega"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nueva asignación</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por orden o placa…" />
      </Toolbar>

      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(a) => a.id}
          columns={[
            { header: "ID", cell: (a) => <span className="font-mono text-xs text-slate-500">#{a.id}</span> },
            {
              header: "Orden",
              cell: (a) => (
                <button onClick={() => navigate(`/ordenes/${a.orden_id}`)} className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
                  #{a.orden_id} <ExternalLink className="h-3 w-3" />
                </button>
              ),
            },
            { header: "Conductor", cell: (a) => condName(a.conductor_id) },
            { header: "Vehículo", cell: (a) => <span className="font-mono text-xs">{a.vehiculo_placa}</span> },
            { header: "Estado", cell: (a) => <StatusBadge kind="asignacion" value={a.estado} /> },
            { header: "Inicio", cell: (a) => <span className="text-slate-500">{a.fecha_inicio ? formatDate(a.fecha_inicio) : "—"}</span> },
            {
              header: "",
              align: "right",
              cell: (a) =>
                writable && (
                  <div className="flex justify-end gap-1">
                    {a.estado === "Asignada" && (
                      <Button size="sm" variant="secondary" onClick={() => iniciar.mutate(a.id, { onSuccess: () => toast.success("Asignación iniciada"), onError: (e) => toast.error(apiError(e)) })}>
                        <Play className="h-3.5 w-3.5" /> Iniciar
                      </Button>
                    )}
                    {a.estado === "EnCurso" && (
                      <Button size="sm" variant="success" onClick={() => setFinalizing(a)}>
                        <CheckCircle2 className="h-3.5 w-3.5" /> Finalizar
                      </Button>
                    )}
                    {a.estado !== "EnCurso" && (
                      <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(a)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ),
            },
          ]}
        />
      </Card>

      {creating && <AsignacionForm onClose={() => setCreating(false)} />}
      {finalizing && <FinalizarModal asignacion={finalizing} onClose={() => setFinalizing(null)} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar asignación"
        description={`¿Eliminar la asignación #${toDelete?.id}?`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Asignación eliminada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

type Sugerencia = { conductor_id: number; nombre: string; vehiculo_placa: string | null; distancia_km: number | null; rating: number | null; total_calificaciones: number };

function AsignacionForm({ onClose }: { onClose: () => void }) {
  const { data: ordenes } = useOrdenes({ estado: "Pendiente", limit: 200 });
  const { data: conductores } = useConductores({ disponibilidad: "Disponible", limit: 200 });
  const { data: vehiculos } = useVehiculos({ estado: "Operativo", limit: 200 });
  const [form, setForm] = useState({ orden_id: "", conductor_id: "", vehiculo_placa: "" });
  const [sugerencias, setSugerencias] = useState<Sugerencia[] | null>(null);
  const [loadingSug, setLoadingSug] = useState(false);
  const m = useApiMutation((body: any) => api.post("/asignaciones/", body), ["asignaciones", "ordenes", "conductores"]);

  const sugerir = async () => {
    if (!form.orden_id) return toast.error("Selecciona primero una orden");
    setLoadingSug(true);
    try {
      const { data } = await api.get<Sugerencia[]>("/asignaciones/sugerencia", { params: { orden_id: Number(form.orden_id) } });
      setSugerencias(data);
      if (data.length === 0) toast("No hay conductores disponibles ahora", { icon: "ℹ️" });
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoadingSug(false);
    }
  };

  const elegir = (s: Sugerencia) =>
    setForm({ ...form, conductor_id: String(s.conductor_id), vehiculo_placa: s.vehiculo_placa ?? "" });

  const submit = () => {
    if (!form.orden_id || !form.conductor_id || !form.vehiculo_placa) return toast.error("Completa todos los campos");
    m.mutate(
      { orden_id: Number(form.orden_id), conductor_id: Number(form.conductor_id), vehiculo_placa: form.vehiculo_placa },
      { onSuccess: () => { toast.success("Asignación creada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Nueva asignación"
      description="Solo se muestran órdenes pendientes, conductores disponibles y vehículos operativos."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Asignar</Button></>}
    >
      <div className="space-y-4">
        <Field label="Orden pendiente" required>
          <Select value={form.orden_id} onChange={(e) => { setForm({ ...form, orden_id: e.target.value }); setSugerencias(null); }}>
            <option value="">Seleccionar…</option>
            {ordenes?.map((o) => <option key={o.id} value={o.id}>#{o.id} · {o.direccion_destino}</option>)}
          </Select>
        </Field>

        {/* Asignación híbrida: el sistema sugiere y el despachador confirma. */}
        <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-brand-800">Sugerencia automática</p>
            <Button size="sm" variant="outline" loading={loadingSug} disabled={!form.orden_id} onClick={sugerir}>
              Sugerir conductor
            </Button>
          </div>
          {sugerencias && sugerencias.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {sugerencias.map((s) => (
                <li key={s.conductor_id}>
                  <button
                    type="button"
                    onClick={() => elegir(s)}
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition ${
                      String(s.conductor_id) === form.conductor_id ? "border-brand-500 bg-white ring-1 ring-brand-300" : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <span className="font-medium text-slate-700">{s.nombre} <span className="font-mono text-xs text-slate-400">{s.vehiculo_placa}</span></span>
                    <span className="text-xs text-slate-500">
                      {s.distancia_km != null ? `${s.distancia_km} km` : "sin ubic."}
                      {s.rating != null && ` · ★ ${s.rating}`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <Field label="Conductor disponible" required>
          <Select value={form.conductor_id} onChange={(e) => setForm({ ...form, conductor_id: e.target.value })}>
            <option value="">Seleccionar…</option>
            {conductores?.map((c) => <option key={c.id} value={c.id}>{c.nombre} {c.vehiculo_placa ? `· ${c.vehiculo_placa}` : ""}</option>)}
          </Select>
        </Field>
        <Field label="Vehículo operativo" required>
          <Select value={form.vehiculo_placa} onChange={(e) => setForm({ ...form, vehiculo_placa: e.target.value })}>
            <option value="">Seleccionar…</option>
            {vehiculos?.map((v) => <option key={v.placa} value={v.placa}>{v.placa} · {v.tipo}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function FinalizarModal({ asignacion, onClose }: { asignacion: Asignacion; onClose: () => void }) {
  const [receptor, setReceptor] = useState("");
  const [nota, setNota] = useState("");
  const [coord, setCoord] = useState<[number, number] | null>(null);
  const m = useApiMutation(
    (body: any) => api.patch(`/asignaciones/${asignacion.id}/finalizar`, body),
    ["asignaciones", "ordenes"],
  );
  const submit = () =>
    m.mutate(
      { receptor: receptor || null, nota: nota || null, lat: coord?.[0], lon: coord?.[1] },
      { onSuccess: () => { toast.success("Entrega confirmada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Confirmar entrega"
      description="Registra quién recibió y dónde. La orden pasará a «Entregado»."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button variant="success" loading={m.isPending} onClick={submit}>Confirmar entrega</Button></>}
    >
      <div className="space-y-4">
        <Field label="Recibido por"><Input value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre de quien recibe" /></Field>
        <Field label="Nota"><Textarea value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Observaciones de la entrega…" /></Field>
        <Field label="Ubicación de entrega" hint="Opcional · clic en el mapa para fijar coordenadas">
          <LocationPicker value={coord} onChange={setCoord} height={220} color="#10b981" />
        </Field>
      </div>
    </Modal>
  );
}
