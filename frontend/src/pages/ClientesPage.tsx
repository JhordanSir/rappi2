import { useEffect, useState } from "react";
import { Plus, MapPin, Pencil, Trash2, Eye, Building2, Star } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useApiMutation, useClientes, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Cliente, ClienteDireccion } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { DetailModal } from "@/components/ui/DetailModal";
import { Field, Input } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Pagination } from "@/components/ui/Pagination";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { LocationPicker } from "@/components/map/MapView";
import { formatCoord, formatDate } from "@/lib/utils";

const PAGE_SIZE = 20;

export default function ClientesPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Cliente | null>(null);
  const [creating, setCreating] = useState(false);
  const [direcciones, setDirecciones] = useState<Cliente | null>(null);
  const [viewing, setViewing] = useState<Cliente | null>(null);
  const [toDelete, setToDelete] = useState<Cliente | null>(null);
  const [page, setPage] = useState(0);
  const dq = useDebouncedValue(search.trim());
  useEffect(() => setPage(0), [dq]);
  // Paginación y búsqueda server-side (header X-Total-Count + parámetro q).
  const { data, isLoading } = usePaginated<Cliente>("clientes", "/clientes/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(dq ? { q: dq } : {}),
  });

  // Desactivar un cliente desactiva en cascada su usuario; refrescamos ambas listas (P6).
  const del = useApiMutation((id: number) => api.delete(`/clientes/${id}`), ["clientes", "usuarios"]);

  const rows = data?.items;
  const total = data?.total ?? 0;

  const writable = can("clientes", "write");

  return (
    <div>
      <PageHeader
        title="Clientes"
        subtitle="Gestión de clientes y sus direcciones georreferenciadas"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo cliente</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por nombre o email…" />
      </Toolbar>

      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(c) => c.id}
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          columns={[
            {
              header: "Cliente",
              cell: (c) => (
                <div>
                  <p className="font-medium text-slate-800">{c.nombre}</p>
                  <p className="text-xs text-slate-500">{c.email}</p>
                </div>
              ),
            },
            { header: "Teléfono", cell: (c) => c.telefono || "—" },
            {
              header: "Direcciones",
              cell: (c) => (
                <button
                  onClick={() => setDirecciones(c)}
                  className="inline-flex items-center gap-1 text-brand-600 hover:underline"
                >
                  <MapPin className="h-3.5 w-3.5" /> {c.direcciones.length}
                </button>
              ),
            },
            { header: "Estado", cell: (c) => <Badge tone={c.activo ? "green" : "gray"}>{c.activo ? "Activo" : "Inactivo"}</Badge> },
            { header: "Registro", cell: (c) => <span className="text-slate-500">{formatDate(c.fecha_registro, false)}</span> },
            {
              header: "",
              align: "right",
              cell: (c) => (
                <div className="flex justify-end gap-1">
                  <Button size="icon" variant="ghost" onClick={() => setViewing(c)}>
                    <Eye className="h-4 w-4" />
                  </Button>
                  {writable && (
                    <Button size="icon" variant="ghost" onClick={() => setEditing(c)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                  )}
                  {writable && (
                    <Button size="icon" variant="ghost" onClick={() => setToDelete(c)} className="text-rose-500 hover:bg-rose-50">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>

      {(creating || editing) && (
        <ClienteForm cliente={editing} onClose={() => { setCreating(false); setEditing(null); }} />
      )}
      {direcciones && <DireccionesModal cliente={direcciones} onClose={() => setDirecciones(null)} writable={writable} />}
      {viewing && (
        <DetailModal
          open
          onClose={() => setViewing(null)}
          title={viewing.nombre}
          description="Ficha del cliente"
          rows={[
            { label: "Nombre", value: viewing.nombre },
            { label: "Email", value: viewing.email },
            { label: "Teléfono", value: viewing.telefono },
            { label: "Documento (CC/RUC)", value: viewing.cc_id },
            { label: "Estado", value: <Badge tone={viewing.activo ? "green" : "gray"}>{viewing.activo ? "Activo" : "Inactivo"}</Badge> },
            { label: "Registro", value: formatDate(viewing.fecha_registro, false) },
            { label: "Direcciones", value: `${viewing.direcciones.length}` },
            { label: "Dirección principal", value: viewing.direcciones.find((d) => d.es_principal)?.direccion ?? viewing.direcciones[0]?.direccion, full: true },
          ]}
        />
      )}

      <ConfirmModal
        open={!!toDelete}
        title="Desactivar cliente"
        description={`¿Seguro que deseas desactivar a "${toDelete?.nombre}"? Podrás reactivarlo editándolo.`}
        confirmLabel="Desactivar"
        danger
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() =>
          toDelete &&
          del.mutate(toDelete.id, {
            onSuccess: () => { toast.success("Cliente desactivado"); setToDelete(null); },
            onError: (e) => toast.error(apiError(e)),
          })
        }
      />
    </div>
  );
}

function ClienteForm({ cliente, onClose }: { cliente: Cliente | null; onClose: () => void }) {
  const isEdit = !!cliente;
  const [form, setForm] = useState({
    nombre: cliente?.nombre ?? "",
    email: cliente?.email ?? "",
    telefono: cliente?.telefono ?? "",
    cc_id: cliente?.cc_id ?? "",
  });
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/clientes/${cliente!.id}`, body) : api.post("/clientes/", body)),
    ["clientes"],
  );

  const submit = () => {
    if (!form.nombre.trim()) return toast.error("El nombre es obligatorio");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return toast.error("Ingresa un email válido");
    m.mutate(
      { ...form, nombre: form.nombre.trim(), email: form.email.trim() },
      {
        onSuccess: () => { toast.success(isEdit ? "Cliente actualizado" : "Cliente creado"); onClose(); },
        onError: (e) => toast.error(apiError(e)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? "Editar cliente" : "Nuevo cliente"}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button loading={m.isPending} onClick={submit}>{isEdit ? "Guardar" : "Crear"}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Nombre" required>
          <Input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
        </Field>
        <Field label="Email" required>
          <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Teléfono">
            <Input value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} />
          </Field>
          <Field label="Documento (CC/RUC)">
            <Input value={form.cc_id} onChange={(e) => setForm({ ...form, cc_id: e.target.value })} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

function DireccionesModal({ cliente, onClose, writable }: { cliente: Cliente; onClose: () => void; writable: boolean }) {
  const [adding, setAdding] = useState(false);
  const { data } = useClientes({ limit: 200 });
  const fresh = data?.find((c) => c.id === cliente.id) ?? cliente;
  const delDir = useApiMutation((id: number) => api.delete(`/clientes/${cliente.id}/direcciones/${id}`), ["clientes"]);

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Direcciones de ${cliente.nombre}`}
      description="Cada dirección guarda latitud/longitud para tracking y ruteo."
      footer={writable && <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Agregar dirección</Button>}
    >
      <div className="space-y-3">
        {fresh.direcciones.length === 0 && (
          <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">Sin direcciones registradas</p>
        )}
        {fresh.direcciones.map((d) => (
          <div key={d.id} className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 p-3">
            <div className="flex gap-3">
              <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <Building2 className="h-4 w-4" />
              </div>
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-slate-800">
                  {d.direccion}
                  {d.es_principal && <Badge tone="indigo"><Star className="h-3 w-3" /> Principal</Badge>}
                </p>
                <p className="text-xs text-slate-500">
                  {[d.distrito, d.ciudad, d.pais].filter(Boolean).join(", ") || "—"}
                </p>
                <p className="mt-0.5 text-xs font-mono text-slate-400">{formatCoord(d.lat, d.lon)}</p>
              </div>
            </div>
            {writable && (
              <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => delDir.mutate(d.id, { onSuccess: () => toast.success("Dirección eliminada") })}>
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        ))}
      </div>
      {adding && <DireccionForm clienteId={cliente.id} onClose={() => setAdding(false)} />}
    </Modal>
  );
}

function DireccionForm({ clienteId, onClose }: { clienteId: number; onClose: () => void }) {
  const [form, setForm] = useState<Partial<ClienteDireccion>>({ es_principal: false });
  const [coord, setCoord] = useState<[number, number] | null>(null);
  const m = useApiMutation(
    (body: any) => api.post(`/clientes/${clienteId}/direcciones`, body),
    ["clientes"],
  );

  const submit = () => {
    if (!form.direccion) return toast.error("La dirección es obligatoria");
    m.mutate(
      { ...form, lat: coord?.[0], lon: coord?.[1] },
      {
        onSuccess: () => { toast.success("Dirección agregada"); onClose(); },
        onError: (e) => toast.error(apiError(e)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Agregar dirección"
      description="Haz clic en el mapa para fijar las coordenadas, o déjalas vacías para geocodificar por texto."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button loading={m.isPending} onClick={submit}>Guardar</Button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Dirección" required className="sm:col-span-2">
          <Input value={form.direccion ?? ""} onChange={(e) => setForm({ ...form, direccion: e.target.value })} placeholder="Av. Ejército 1009, Yanahuara" />
        </Field>
        <Field label="Distrito"><Input value={form.distrito ?? ""} onChange={(e) => setForm({ ...form, distrito: e.target.value })} /></Field>
        <Field label="Ciudad"><Input value={form.ciudad ?? ""} onChange={(e) => setForm({ ...form, ciudad: e.target.value })} /></Field>
        <Field label="Latitud"><Input value={coord?.[0] ?? ""} onChange={(e) => setCoord([Number(e.target.value), coord?.[1] ?? 0])} placeholder="-16.4090" /></Field>
        <Field label="Longitud"><Input value={coord?.[1] ?? ""} onChange={(e) => setCoord([coord?.[0] ?? 0, Number(e.target.value)])} placeholder="-71.5375" /></Field>
        <div className="sm:col-span-2">
          <LocationPicker value={coord} onChange={setCoord} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2">
          <input type="checkbox" checked={!!form.es_principal} onChange={(e) => setForm({ ...form, es_principal: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
          Marcar como dirección principal
        </label>
      </div>
    </Modal>
  );
}
