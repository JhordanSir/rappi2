import { useMemo, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useVehiculos, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { EstadoVehiculo, Vehiculo } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { formatNumber } from "@/lib/utils";

const ESTADOS: EstadoVehiculo[] = ["Operativo", "Mantenimiento", "Inactivo"];

export default function VehiculosPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Vehiculo | null>(null);
  const [toDelete, setToDelete] = useState<Vehiculo | null>(null);
  const { data, isLoading } = useVehiculos({ limit: 200 });
  const writable = can("vehiculos", "write");
  const del = useApiMutation((placa: string) => api.delete(`/vehiculos/${placa}`), ["vehiculos"]);

  const rows = useMemo(
    () => (data ?? []).filter((v) => !search || v.placa.toLowerCase().includes(search.toLowerCase()) || v.tipo.toLowerCase().includes(search.toLowerCase())),
    [data, search],
  );

  return (
    <div>
      <PageHeader
        title="Vehículos"
        subtitle="Flota disponible para asignaciones"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo vehículo</Button>}
      />
      <Toolbar><SearchInput value={search} onChange={setSearch} placeholder="Buscar por placa o tipo…" /></Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(v) => v.placa}
          columns={[
            { header: "Placa", cell: (v) => <span className="font-mono font-semibold text-slate-800">{v.placa}</span> },
            { header: "Tipo", cell: (v) => v.tipo },
            { header: "Capacidad", align: "right", cell: (v) => `${formatNumber(v.capacidad_kg)} kg` },
            { header: "Estado", cell: (v) => <StatusBadge kind="vehiculo" value={v.estado} /> },
            { header: "Activo", cell: (v) => <Badge tone={v.activo ? "green" : "gray"}>{v.activo ? "Sí" : "No"}</Badge> },
            { header: "", align: "right", cell: (v) => writable && (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" onClick={() => setEditing(v)}><Pencil className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(v)}><Trash2 className="h-4 w-4" /></Button>
              </div>
            )},
          ]}
        />
      </Card>
      {(creating || editing) && <VehiculoForm vehiculo={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
      <ConfirmModal
        open={!!toDelete}
        title="Desactivar vehículo"
        description={`¿Desactivar el vehículo ${toDelete?.placa}?`}
        danger
        confirmLabel="Desactivar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.placa, { onSuccess: () => { toast.success("Vehículo desactivado"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

function VehiculoForm({ vehiculo, onClose }: { vehiculo: Vehiculo | null; onClose: () => void }) {
  const isEdit = !!vehiculo;
  const [form, setForm] = useState({
    placa: vehiculo?.placa ?? "",
    tipo: vehiculo?.tipo ?? "",
    capacidad_kg: vehiculo?.capacidad_kg ? String(vehiculo.capacidad_kg) : "",
    estado: vehiculo?.estado ?? "Operativo",
  });
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/vehiculos/${vehiculo!.placa}`, body) : api.post("/vehiculos/", body)),
    ["vehiculos"],
  );

  const submit = () => {
    if ((!isEdit && !form.placa) || !form.tipo) return toast.error("Placa y tipo son obligatorios");
    const body: any = { tipo: form.tipo, capacidad_kg: Number(form.capacidad_kg || 0), estado: form.estado };
    if (!isEdit) body.placa = form.placa;
    m.mutate(body, { onSuccess: () => { toast.success(isEdit ? "Vehículo actualizado" : "Vehículo creado"); onClose(); }, onError: (e) => toast.error(apiError(e)) });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? `Editar ${vehiculo!.placa}` : "Nuevo vehículo"}
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>{isEdit ? "Guardar" : "Crear"}</Button></>}
    >
      <div className="space-y-4">
        {!isEdit && <Field label="Placa" required><Input value={form.placa} onChange={(e) => setForm({ ...form, placa: e.target.value.toUpperCase() })} placeholder="ABC-123" /></Field>}
        <Field label="Tipo" required><Input value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })} placeholder="Camioneta, Moto…" /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Capacidad (kg)"><Input type="number" step="0.1" value={form.capacidad_kg} onChange={(e) => setForm({ ...form, capacidad_kg: e.target.value })} /></Field>
          <Field label="Estado">
            <Select value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value as EstadoVehiculo })}>
              {ESTADOS.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </Field>
        </div>
      </div>
    </Modal>
  );
}
