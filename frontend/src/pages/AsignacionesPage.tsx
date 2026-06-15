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

function AsignacionForm({ onClose }: { onClose: () => void }) {
  const { data: ordenes } = useOrdenes({ estado: "Pendiente", limit: 200 });
  const { data: conductores } = useConductores({ disponibilidad: "Disponible", limit: 200 });
  const { data: vehiculos } = useVehiculos({ estado: "Operativo", limit: 200 });
  const [form, setForm] = useState({ orden_id: "", conductor_id: "", vehiculo_placa: "" });
  const m = useApiMutation((body: any) => api.post("/asignaciones/", body), ["asignaciones", "ordenes", "conductores"]);

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
          <Select value={form.orden_id} onChange={(e) => setForm({ ...form, orden_id: e.target.value })}>
            <option value="">Seleccionar…</option>
            {ordenes?.map((o) => <option key={o.id} value={o.id}>#{o.id} · {o.direccion_destino}</option>)}
          </Select>
        </Field>
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
