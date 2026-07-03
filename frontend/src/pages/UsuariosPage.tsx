import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2, Eye, RotateCcw } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useRoles, useApiMutation, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Usuario } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { DetailModal } from "@/components/ui/DetailModal";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Pagination } from "@/components/ui/Pagination";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { formatDate, initials } from "@/lib/utils";

const PAGE_SIZE = 20;

export default function UsuariosPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [estado, setEstado] = useState<"todos" | "activos" | "inactivos">("todos");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Usuario | null>(null);
  const [viewing, setViewing] = useState<Usuario | null>(null);
  const [toDelete, setToDelete] = useState<Usuario | null>(null);
  const [page, setPage] = useState(0);
  const dq = useDebouncedValue(search.trim());
  // Al cambiar filtros o búsqueda volvemos a la primera página.
  useEffect(() => setPage(0), [dq, estado]);
  // Paginación y búsqueda server-side (header X-Total-Count + parámetro q).
  const { data, isLoading } = usePaginated<Usuario>("usuarios", "/usuarios/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(dq ? { q: dq } : {}),
    ...(estado !== "todos" ? { activo: estado === "activos" } : {}),
  });
  const { data: roles } = useRoles();
  const writable = can("usuarios", "write");
  // Invalida tambien conductores/clientes: (des)activar un usuario (des)activa en cascada sus fichas (P6).
  const del = useApiMutation((id: number) => api.delete(`/usuarios/${id}`), ["usuarios", "conductores", "clientes"]);
  const reactivar = useApiMutation((id: number) => api.patch(`/usuarios/${id}`, { activo: true }), ["usuarios", "conductores", "clientes"]);

  const rows = data?.items;
  const total = data?.total ?? 0;
  const rolName = (id: number) => roles?.find((r) => r.id === id)?.nombre ?? `#${id}`;

  return (
    <div>
      <PageHeader
        title="Usuarios"
        subtitle="Cuentas de acceso y su rol asignado"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo usuario</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por usuario o email…" />
        <Select value={estado} onChange={(e) => setEstado(e.target.value as "todos" | "activos" | "inactivos")} className="h-10 w-44">
          <option value="todos">Todos los estados</option>
          <option value="activos">Solo activos</option>
          <option value="inactivos">Solo inactivos</option>
        </Select>
      </Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(u) => u.id}
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          columns={[
            { header: "Usuario", cell: (u) => (
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">{initials(u.username)}</div>
                <div>
                  <p className="font-medium text-slate-800">{u.username}</p>
                  <p className="text-xs text-slate-500">{u.email}</p>
                </div>
              </div>
            )},
            { header: "Rol", cell: (u) => <Badge tone="indigo">{u.rol?.nombre ?? rolName(u.rol_id)}</Badge> },
            { header: "Estado", cell: (u) => <Badge tone={u.activo ? "green" : "gray"}>{u.activo ? "Activo" : "Inactivo"}</Badge> },
            { header: "Registro", cell: (u) => <span className="text-slate-500">{formatDate(u.fecha_registro, false)}</span> },
            { header: "", align: "right", cell: (u) => (
              <div className="flex justify-end gap-1">
                <Button size="icon" variant="ghost" onClick={() => setViewing(u)}><Eye className="h-4 w-4" /></Button>
                {writable && <Button size="icon" variant="ghost" onClick={() => setEditing(u)}><Pencil className="h-4 w-4" /></Button>}
                {writable && (u.activo ? (
                  <Button size="icon" variant="ghost" className="text-rose-500" title="Desactivar" onClick={() => setToDelete(u)}><Trash2 className="h-4 w-4" /></Button>
                ) : (
                  <Button
                    size="icon"
                    variant="ghost"
                    className="text-emerald-600"
                    title="Reactivar"
                    loading={reactivar.isPending && reactivar.variables === u.id}
                    onClick={() => reactivar.mutate(u.id, { onSuccess: () => toast.success("Usuario reactivado"), onError: (e) => toast.error(apiError(e)) })}
                  >
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                ))}
              </div>
            )},
          ]}
        />
      </Card>
      {(creating || editing) && <UsuarioForm usuario={editing} roles={roles ?? []} onClose={() => { setCreating(false); setEditing(null); }} />}
      {viewing && (
        <DetailModal
          open
          onClose={() => setViewing(null)}
          title={viewing.username}
          description="Ficha del usuario"
          rows={[
            { label: "Usuario", value: viewing.username },
            { label: "Email", value: viewing.email },
            { label: "Rol", value: <Badge tone="indigo">{viewing.rol?.nombre ?? rolName(viewing.rol_id)}</Badge> },
            { label: "Estado", value: <Badge tone={viewing.activo ? "green" : "gray"}>{viewing.activo ? "Activo" : "Inactivo"}</Badge> },
            { label: "Registro", value: formatDate(viewing.fecha_registro, false) },
            { label: "Cliente vinculado", value: viewing.cliente_id ? `#${viewing.cliente_id}` : null },
          ]}
        />
      )}
      <ConfirmModal
        open={!!toDelete}
        title="Desactivar usuario"
        description={`¿Desactivar a "${toDelete?.username}"?`}
        danger
        confirmLabel="Desactivar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Usuario desactivado"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

function UsuarioForm({ usuario, roles, onClose }: { usuario: Usuario | null; roles: { id: number; nombre: string }[]; onClose: () => void }) {
  const isEdit = !!usuario;
  const [form, setForm] = useState({
    username: usuario?.username ?? "",
    email: usuario?.email ?? "",
    password: "",
    rol_id: usuario?.rol_id ? String(usuario.rol_id) : "",
    activo: usuario?.activo ?? true,
  });
  // Crear/editar un usuario puede crear o migrar su ficha Cliente/Conductor (P3, P4),
  // por eso invalidamos también esas listas.
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/usuarios/${usuario!.id}`, body) : api.post("/usuarios/", body)),
    ["usuarios", "conductores", "clientes"],
  );
  const submit = () => {
    if (!form.rol_id) return toast.error("Selecciona un rol");
    const body: any = isEdit
      ? { email: form.email, rol_id: Number(form.rol_id), activo: form.activo, ...(form.password ? { password: form.password } : {}) }
      : { username: form.username, email: form.email, password: form.password, rol_id: Number(form.rol_id) };
    if (!isEdit && (!form.username || !form.email || !form.password)) return toast.error("Usuario, email y contraseña son obligatorios");
    m.mutate(body, { onSuccess: () => { toast.success(isEdit ? "Usuario actualizado" : "Usuario creado"); onClose(); }, onError: (e) => toast.error(apiError(e)) });
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={isEdit ? "Editar usuario" : "Nuevo usuario"}
      description={isEdit
        ? "Los cambios (email, rol, contraseña, estado) se sincronizan con Keycloak."
        : "La cuenta se crea en Keycloak (proveedor de identidad): podrá iniciar sesión de inmediato."}
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>{isEdit ? "Guardar" : "Crear"}</Button></>}>
      <div className="space-y-4">
        {!isEdit && <Field label="Usuario" required><Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>}
        <Field label="Email" required><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label={isEdit ? "Nueva contraseña" : "Contraseña"} required={!isEdit}>
            <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={isEdit ? "Dejar vacío para mantener" : ""} />
          </Field>
          <Field label="Rol" required>
            <Select value={form.rol_id} onChange={(e) => setForm({ ...form, rol_id: e.target.value })}>
              <option value="">Seleccionar…</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
            </Select>
          </Field>
        </div>
        {isEdit && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={form.activo} onChange={(e) => setForm({ ...form, activo: e.target.checked })} className="h-4 w-4 rounded border-slate-300" />
            Usuario activo
          </label>
        )}
      </div>
    </Modal>
  );
}
