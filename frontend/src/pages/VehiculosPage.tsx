import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Eye } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useApiMutation, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { EstadoVehiculo, Vehiculo } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { DetailModal } from "@/components/ui/DetailModal";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Pagination } from "@/components/ui/Pagination";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { formatNumber, formatDate } from "@/lib/utils";

const ESTADOS: EstadoVehiculo[] = ["Operativo", "Mantenimiento", "Inactivo"];
const PAGE_SIZE = 20;

export default function VehiculosPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Vehiculo | null>(null);
  const [viewing, setViewing] = useState<Vehiculo | null>(null);
  const [toDelete, setToDelete] = useState<Vehiculo | null>(null);
  const [page, setPage] = useState(0);
  const [estado, setEstado] = useState("");
  const [tipo, setTipo] = useState("");
  const [capMin, setCapMin] = useState("");
  const dq = useDebouncedValue(search.trim());
  const dTipo = useDebouncedValue(tipo.trim());
  const dCapMin = useDebouncedValue(capMin.trim());
  useEffect(() => setPage(0), [dq, estado, dTipo, dCapMin]);
  // Paginación y búsqueda server-side (header X-Total-Count + parámetro q).
  const { data, isLoading } = usePaginated<Vehiculo>("vehiculos", "/vehiculos/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(dq ? { q: dq } : {}),
    ...(estado ? { estado } : {}),
    ...(dTipo ? { tipo: dTipo } : {}),
    ...(dCapMin && !isNaN(Number(dCapMin)) ? { capacidad_min: Number(dCapMin) } : {}),
  });
  const writable = can("vehiculos", "write");
  const del = useApiMutation((placa: string) => api.delete(`/vehiculos/${placa}`), ["vehiculos"]);

  const rows = data?.items;
  const total = data?.total ?? 0;

  return (
    <div>
      <PageHeader
        title="Vehículos"
        subtitle="Flota disponible para asignaciones"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo vehículo</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por placa o tipo…" />
        <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="h-10 w-auto" title="Estado de flota">
          <option value="">Todo estado</option>
          {ESTADOS.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Input value={tipo} onChange={(e) => setTipo(e.target.value)} placeholder="Tipo (moto, camioneta…)" className="h-10 w-44" title="Tipo de vehículo" />
        <Input type="number" min="0" value={capMin} onChange={(e) => setCapMin(e.target.value)} placeholder="Cap. mín. (kg)" className="h-10 w-32" title="Capacidad mínima de carga" />
      </Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(v) => v.placa}
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          columns={[
            { header: "Placa", cell: (v) => <span className="font-mono font-semibold text-slate-800">{v.placa}</span> },
            { header: "Tipo", cell: (v) => v.tipo },
            { header: "Capacidad", align: "right", cell: (v) => `${formatNumber(v.capacidad_kg)} kg` },
            { header: "Dimensiones", cell: (v) => (v.largo_cm && v.ancho_cm && v.alto_cm) ? <span className="font-mono text-xs text-slate-500">{`${v.largo_cm}×${v.ancho_cm}×${v.alto_cm} cm`}</span> : <span className="text-slate-300">—</span> },
            { header: "Estado", cell: (v) => <StatusBadge kind="vehiculo" value={v.estado} /> },
            { header: "Activo", cell: (v) => <Badge tone={v.activo ? "green" : "gray"}>{v.activo ? "Sí" : "No"}</Badge> },
            { header: "", align: "right", cell: (v) => (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" onClick={() => setViewing(v)}><Eye className="h-4 w-4" /></Button>
                {writable && <Button size="icon" variant="ghost" onClick={() => setEditing(v)}><Pencil className="h-4 w-4" /></Button>}
                {writable && <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(v)}><Trash2 className="h-4 w-4" /></Button>}
              </div>
            )},
          ]}
        />
      </Card>
      {(creating || editing) && <VehiculoForm vehiculo={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
      {viewing && (
        <DetailModal
          open
          onClose={() => setViewing(null)}
          title={viewing.placa}
          description="Ficha del vehículo"
          rows={[
            { label: "Placa", value: <span className="font-mono">{viewing.placa}</span> },
            { label: "Tipo", value: viewing.tipo },
            { label: "Capacidad", value: `${formatNumber(viewing.capacidad_kg)} kg` },
            { label: "Dimensiones (cm)", value: viewing.largo_cm && viewing.ancho_cm && viewing.alto_cm ? `${viewing.largo_cm}×${viewing.ancho_cm}×${viewing.alto_cm}` : null },
            { label: "Estado", value: <StatusBadge kind="vehiculo" value={viewing.estado} /> },
            { label: "Activo", value: <Badge tone={viewing.activo ? "green" : "gray"}>{viewing.activo ? "Sí" : "No"}</Badge> },
            { label: "Último mantenimiento", value: formatDate(viewing.fecha_mantenimiento, false), full: true },
          ]}
        />
      )}
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
    largo_cm: vehiculo?.largo_cm ? String(vehiculo.largo_cm) : "",
    ancho_cm: vehiculo?.ancho_cm ? String(vehiculo.ancho_cm) : "",
    alto_cm: vehiculo?.alto_cm ? String(vehiculo.alto_cm) : "",
    estado: vehiculo?.estado ?? "Operativo",
  });
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/vehiculos/${vehiculo!.placa}`, body) : api.post("/vehiculos/", body)),
    ["vehiculos"],
  );

  const submit = () => {
    if ((!isEdit && !form.placa) || !form.tipo) return toast.error("Placa y tipo son obligatorios");
    if (!isEdit && !/^[A-Z]{3}-\d{3}$/.test(form.placa)) return toast.error("La placa debe tener el formato ABC-123 (3 letras, guion, 3 dígitos)");
    // Dimensiones obligatorias y > 0 al dar de alta (necesarias para validar el cubicaje).
    if (!isEdit && ![form.largo_cm, form.ancho_cm, form.alto_cm].every((v) => Number(v) > 0))
      return toast.error("Indica largo, ancho y alto (en cm, mayores que 0)");
    const dim = (v: string) => (v.trim() === "" ? null : Number(v));
    const body: any = {
      tipo: form.tipo, capacidad_kg: Number(form.capacidad_kg || 0), estado: form.estado,
      largo_cm: dim(form.largo_cm), ancho_cm: dim(form.ancho_cm), alto_cm: dim(form.alto_cm),
    };
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
        <Field label="Dimensiones útiles de carga (cm)" required={!isEdit} hint="Para validar si el paquete cabe físicamente">
          <div className="grid grid-cols-3 gap-3">
            <Input type="number" min="0" step="1" value={form.largo_cm} onChange={(e) => setForm({ ...form, largo_cm: e.target.value })} placeholder="Largo" />
            <Input type="number" min="0" step="1" value={form.ancho_cm} onChange={(e) => setForm({ ...form, ancho_cm: e.target.value })} placeholder="Ancho" />
            <Input type="number" min="0" step="1" value={form.alto_cm} onChange={(e) => setForm({ ...form, alto_cm: e.target.value })} placeholder="Alto" />
          </div>
        </Field>
      </div>
    </Modal>
  );
}
