import { useMemo, useState } from "react";
import { Plus, Pencil, Truck, IdCard } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useConductores, useVehiculos, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Conductor, DisponibilidadConductor } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select } from "@/components/ui/Field";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";

const DISPO: DisponibilidadConductor[] = ["Disponible", "Ocupado", "Inactivo"];

export default function ConductoresPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Conductor | null>(null);
  const { data, isLoading } = useConductores({ limit: 200 });
  const writable = can("conductores", "write");

  const rows = useMemo(
    () => (data ?? []).filter((c) => !search || c.nombre.toLowerCase().includes(search.toLowerCase()) || c.licencia.toLowerCase().includes(search.toLowerCase())),
    [data, search],
  );

  return (
    <div>
      <PageHeader
        title="Conductores"
        subtitle="Personal de reparto y su vehículo asignado"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo conductor</Button>}
      />
      <Toolbar><SearchInput value={search} onChange={setSearch} placeholder="Buscar por nombre o licencia…" /></Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(c) => c.id}
          columns={[
            { header: "Conductor", cell: (c) => (
              <div>
                <p className="font-medium text-slate-800">{c.nombre}</p>
                <p className="flex items-center gap-1 text-xs text-slate-500"><IdCard className="h-3 w-3" /> {c.licencia}</p>
              </div>
            )},
            { header: "Vehículo", cell: (c) => c.vehiculo_placa ? <span className="inline-flex items-center gap-1 font-mono text-xs"><Truck className="h-3.5 w-3.5 text-slate-400" /> {c.vehiculo_placa}</span> : <span className="text-slate-400">Sin vehículo</span> },
            { header: "Disponibilidad", cell: (c) => <StatusBadge kind="dispo" value={c.disponibilidad} /> },
            { header: "Estado", cell: (c) => <Badge tone={c.activo ? "green" : "gray"}>{c.activo ? "Activo" : "Inactivo"}</Badge> },
            { header: "", align: "right", cell: (c) => writable && <Button size="icon" variant="ghost" onClick={() => setEditing(c)}><Pencil className="h-4 w-4" /></Button> },
          ]}
        />
      </Card>
      {(creating || editing) && <ConductorForm conductor={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
    </div>
  );
}

function ConductorForm({ conductor, onClose }: { conductor: Conductor | null; onClose: () => void }) {
  const isEdit = !!conductor;
  const { data: vehiculos } = useVehiculos({ limit: 200 });
  const [form, setForm] = useState({
    nombre: conductor?.nombre ?? "",
    licencia: conductor?.licencia ?? "",
    usuario_id: conductor?.usuario_id ? String(conductor.usuario_id) : "",
    disponibilidad: conductor?.disponibilidad ?? "Disponible",
    vehiculo_placa: conductor?.vehiculo_placa ?? "",
  });
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/conductores/${conductor!.id}`, body) : api.post("/conductores/", body)),
    ["conductores"],
  );

  const submit = () => {
    const base: any = { nombre: form.nombre, disponibilidad: form.disponibilidad, vehiculo_placa: form.vehiculo_placa || null };
    if (!isEdit) { base.licencia = form.licencia; base.usuario_id = Number(form.usuario_id); }
    if (!form.nombre || (!isEdit && (!form.licencia || !form.usuario_id))) return toast.error("Completa los campos obligatorios");
    m.mutate(base, { onSuccess: () => { toast.success(isEdit ? "Conductor actualizado" : "Conductor creado"); onClose(); }, onError: (e) => toast.error(apiError(e)) });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? "Editar conductor" : "Nuevo conductor"}
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>{isEdit ? "Guardar" : "Crear"}</Button></>}
    >
      <div className="space-y-4">
        <Field label="Nombre" required><Input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field>
        {!isEdit && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Licencia" required><Input value={form.licencia} onChange={(e) => setForm({ ...form, licencia: e.target.value })} placeholder="ABC-123" /></Field>
            <Field label="Usuario ID" required hint="ID de usuario vinculado"><Input type="number" value={form.usuario_id} onChange={(e) => setForm({ ...form, usuario_id: e.target.value })} /></Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <Field label="Disponibilidad">
            <Select value={form.disponibilidad} onChange={(e) => setForm({ ...form, disponibilidad: e.target.value as DisponibilidadConductor })}>
              {DISPO.map((d) => <option key={d} value={d}>{d}</option>)}
            </Select>
          </Field>
          <Field label="Vehículo">
            <Select value={form.vehiculo_placa} onChange={(e) => setForm({ ...form, vehiculo_placa: e.target.value })}>
              <option value="">Sin vehículo</option>
              {vehiculos?.map((v) => <option key={v.placa} value={v.placa}>{v.placa} · {v.tipo}</option>)}
            </Select>
          </Field>
        </div>
      </div>
    </Modal>
  );
}
