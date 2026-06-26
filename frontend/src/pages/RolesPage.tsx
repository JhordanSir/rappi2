import { useState } from "react";
import { Plus, Shield, X, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useRoles, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Rol } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { PageLoader } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Field, Input } from "@/components/ui/Field";

const RECURSOS = ["ordenes", "asignaciones", "rutas", "tracking", "clientes", "conductores", "vehiculos", "pagos", "facturas", "incidencias", "geocercas", "reportes", "usuarios", "roles", "sesiones", "notificaciones", "auditoria"];
const ACCIONES = ["read", "write", "delete"];
// Roles base del RBAC: no se pueden borrar (romperían el sistema de permisos/seed).
const ROLES_SISTEMA = ["Admin", "Conductor", "Cliente"];

export default function RolesPage() {
  const { can } = useAuth();
  const { data, isLoading } = useRoles();
  const [creating, setCreating] = useState(false);
  const [managing, setManaging] = useState<Rol | null>(null);
  const [toDelete, setToDelete] = useState<Rol | null>(null);
  const del = useApiMutation((id: number) => api.delete(`/roles/${id}`), ["roles"]);
  const writable = can("roles", "write");

  if (isLoading) return <PageLoader />;
  const fresh = managing ? data?.find((r) => r.id === managing.id) ?? managing : null;

  return (
    <div>
      <PageHeader
        title="Roles & Permisos"
        subtitle="Control de acceso basado en roles (RBAC) con comodines *"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nuevo rol</Button>}
      />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((r) => (
          <Card key={r.id}>
            <CardBody>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600"><Shield className="h-4 w-4" /></div>
                  <p className="font-semibold text-slate-800">{r.nombre}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <Badge tone="gray">{r.permisos.length} permisos</Badge>
                  {writable && !ROLES_SISTEMA.includes(r.nombre) && (
                    <Button size="icon" variant="ghost" className="text-rose-500" title="Eliminar rol" onClick={() => setToDelete(r)}><Trash2 className="h-4 w-4" /></Button>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {r.permisos.slice(0, 8).map((p) => (
                  <span key={p.id} className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600">{p.recurso}:{p.accion}</span>
                ))}
                {r.permisos.length > 8 && <span className="text-[11px] text-slate-400">+{r.permisos.length - 8}</span>}
                {r.permisos.length === 0 && <span className="text-xs text-slate-400">Sin permisos</span>}
              </div>
              {writable && (
                <Button variant="outline" size="sm" className="mt-4 w-full" onClick={() => setManaging(r)}>Gestionar permisos</Button>
              )}
            </CardBody>
          </Card>
        ))}
      </div>

      {creating && <RolForm onClose={() => setCreating(false)} />}
      {fresh && <PermisosModal rol={fresh} onClose={() => setManaging(null)} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar rol"
        description={`¿Eliminar el rol "${toDelete?.nombre}"? Esta acción no se puede deshacer.`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Rol eliminado"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

function RolForm({ onClose }: { onClose: () => void }) {
  const [nombre, setNombre] = useState("");
  const m = useApiMutation((body: any) => api.post("/roles/", body), ["roles"]);
  return (
    <Modal open onClose={onClose} title="Nuevo rol" footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={() => nombre ? m.mutate({ nombre }, { onSuccess: () => { toast.success("Rol creado"); onClose(); }, onError: (e) => toast.error(apiError(e)) }) : toast.error("Nombre requerido")}>Crear</Button></>}>
      <Field label="Nombre del rol" required><Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Despachador" /></Field>
    </Modal>
  );
}

function PermisosModal({ rol, onClose }: { rol: Rol; onClose: () => void }) {
  const [recurso, setRecurso] = useState(RECURSOS[0]);
  const [accion, setAccion] = useState(ACCIONES[0]);
  const add = useApiMutation((body: any) => api.post(`/roles/${rol.id}/permisos`, body), ["roles"]);
  const remove = useApiMutation((pid: number) => api.delete(`/roles/${rol.id}/permisos/${pid}`), ["roles"]);

  return (
    <Modal open onClose={onClose} size="lg" title={`Permisos · ${rol.nombre}`} description="Otorga permisos por recurso y acción. Usa * como comodín total.">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 p-3">
          <Field label="Recurso" className="flex-1">
            <select className="input-base appearance-none" value={recurso} onChange={(e) => setRecurso(e.target.value)}>
              <option value="*">* (todos)</option>
              {RECURSOS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Acción" className="flex-1">
            <select className="input-base appearance-none" value={accion} onChange={(e) => setAccion(e.target.value)}>
              <option value="*">* (todas)</option>
              {ACCIONES.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>
          <Button onClick={() => add.mutate({ recurso, accion }, { onSuccess: () => toast.success("Permiso agregado"), onError: (e) => toast.error(apiError(e)) })} loading={add.isPending}>
            <Plus className="h-4 w-4" /> Agregar
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          {rol.permisos.length === 0 && <p className="text-sm text-slate-400">Este rol no tiene permisos.</p>}
          {rol.permisos.map((p) => (
            <span key={p.id} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 py-1 pl-2.5 pr-1.5 font-mono text-xs text-slate-700">
              {p.recurso}:{p.accion}
              <button onClick={() => remove.mutate(p.id, { onSuccess: () => toast.success("Permiso quitado") })} className="rounded p-0.5 text-slate-400 hover:bg-rose-100 hover:text-rose-600">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      </div>
    </Modal>
  );
}
