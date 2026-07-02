import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Eye, Truck, IdCard } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useConductores, useVehiculos, useUsuarios, useApiMutation, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Conductor, DisponibilidadConductor } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { DetailModal } from "@/components/ui/DetailModal";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Field, Input, Select } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { formatNumber } from "@/lib/utils";

const DISPO: DisponibilidadConductor[] = ["Disponible", "Ocupado", "Inactivo"];
const PAGE_SIZE = 20;

export default function ConductoresPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Conductor | null>(null);
  const [viewing, setViewing] = useState<Conductor | null>(null);
  const [toDelete, setToDelete] = useState<Conductor | null>(null);
  const [page, setPage] = useState(0);
  const dq = useDebouncedValue(search.trim());
  useEffect(() => setPage(0), [dq]);
  // Paginación y búsqueda server-side (header X-Total-Count + parámetro q).
  const { data, isLoading } = usePaginated<Conductor>("conductores", "/conductores/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(dq ? { q: dq } : {}),
  });
  const writable = can("conductores", "write");
  const deletable = can("conductores", "delete");
  // Eliminar un conductor lo desactiva y, en cascada, desactiva su usuario (P6).
  const del = useApiMutation((id: number) => api.delete(`/conductores/${id}`), ["conductores", "usuarios"]);

  const rows = data?.items;
  const total = data?.total ?? 0;

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
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          columns={[
            { header: "Conductor", cell: (c) => (
              <div>
                <p className="font-medium text-slate-800">{c.nombre}</p>
                <p className="flex items-center gap-1 text-xs text-slate-500"><IdCard className="h-3 w-3" /> {c.licencia}</p>
              </div>
            )},
            { header: "Usuario", cell: (c) => c.usuario ? (
              <div>
                <p className="text-sm text-slate-700">{c.usuario.username}</p>
                <p className="text-xs text-slate-500">{c.usuario.email}</p>
              </div>
            ) : <span className="text-slate-400">—</span> },
            { header: "Vehículo", cell: (c) => c.vehiculo_placa ? <span className="inline-flex items-center gap-1 font-mono text-xs"><Truck className="h-3.5 w-3.5 text-slate-400" /> {c.vehiculo_placa}</span> : <span className="text-slate-400">Sin vehículo</span> },
            { header: "Disponibilidad", cell: (c) => <StatusBadge kind="dispo" value={c.disponibilidad} /> },
            { header: "Estado", cell: (c) => <Badge tone={c.activo ? "green" : "gray"}>{c.activo ? "Activo" : "Inactivo"}</Badge> },
            { header: "", align: "right", cell: (c) => (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" onClick={() => setViewing(c)}><Eye className="h-4 w-4" /></Button>
                {writable && <Button size="icon" variant="ghost" onClick={() => setEditing(c)}><Pencil className="h-4 w-4" /></Button>}
                {deletable && <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(c)}><Trash2 className="h-4 w-4" /></Button>}
              </div>
            )},
          ]}
        />
      </Card>
      {(creating || editing) && <ConductorForm conductor={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
      {viewing && <ConductorDetail conductor={viewing} onClose={() => setViewing(null)} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar conductor"
        description={`¿Eliminar al conductor "${toDelete?.nombre}"? Se desactivará junto con su usuario de acceso.`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Conductor eliminado"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

function ConductorDetail({ conductor: c, onClose }: { conductor: Conductor; onClose: () => void }) {
  const v = c.vehiculo;
  return (
    <DetailModal
      open
      onClose={onClose}
      title={c.nombre}
      description="Ficha del conductor"
      rows={[
        { label: "Nombre", value: c.nombre },
        { label: "Licencia", value: c.licencia },
        { label: "Usuario", value: c.usuario?.username },
        { label: "Email", value: c.usuario?.email },
        { label: "Disponibilidad", value: <StatusBadge kind="dispo" value={c.disponibilidad} /> },
        { label: "Estado", value: <Badge tone={c.activo ? "green" : "gray"}>{c.activo ? "Activo" : "Inactivo"}</Badge> },
        { label: "Vehículo", value: v ? `${v.placa} · ${v.tipo}` : "Sin vehículo" },
        { label: "Capacidad", value: v ? `${formatNumber(v.capacidad_kg)} kg` : null },
        { label: "Dimensiones (cm)", value: v && v.largo_cm && v.ancho_cm && v.alto_cm ? `${v.largo_cm}×${v.ancho_cm}×${v.alto_cm}` : null, full: true },
      ]}
    />
  );
}

function ConductorForm({ conductor, onClose }: { conductor: Conductor | null; onClose: () => void }) {
  const isEdit = !!conductor;
  const { data: vehiculos } = useVehiculos({ limit: 200 });
  const { data: usuarios } = useUsuarios({ limit: 200 });
  const { data: conductoresAll } = useConductores({ limit: 200 });
  // Usuarios elegibles: rol Conductor, activos y aún sin perfil de conductor.
  const usadosIds = new Set((conductoresAll ?? []).map((c) => c.usuario_id));
  const usuariosDisponibles = (usuarios ?? []).filter(
    (u) => u.rol?.nombre === "Conductor" && u.activo && !usadosIds.has(u.id),
  );
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
            <Field label="Licencia" required><Input value={form.licencia} onChange={(e) => setForm({ ...form, licencia: e.target.value })} placeholder="Q12345678" /></Field>
            <Field label="Usuario vinculado" required hint="Usuario con rol Conductor">
              <Select value={form.usuario_id} onChange={(e) => setForm({ ...form, usuario_id: e.target.value })}>
                <option value="">Seleccionar…</option>
                {usuariosDisponibles.map((u) => <option key={u.id} value={u.id}>{u.username} · {u.email}</option>)}
              </Select>
            </Field>
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
