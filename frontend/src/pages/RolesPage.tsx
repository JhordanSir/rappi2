import { useMemo, useState } from "react";
import { Plus, Shield, Trash2 } from "lucide-react";
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

// Filas/columnas de la matriz (con comodín * al inicio).
const RECURSOS_ROWS = ["*", ...RECURSOS];
const ACCIONES_COLS = ["*", ...ACCIONES];

function PermisosModal({ rol, onClose }: { rol: Rol; onClose: () => void }) {
  // Selección como conjunto "recurso:accion"; se inicializa con los permisos actuales y
  // se guarda TODO de una sola vez (multiselección) vía PUT (el backend calcula el diff).
  const inicial = useMemo(() => new Set(rol.permisos.map((p) => `${p.recurso}:${p.accion}`)), [rol]);
  const [sel, setSel] = useState<Set<string>>(inicial);
  const save = useApiMutation((body: any) => api.put(`/roles/${rol.id}/permisos`, body), ["roles"]);

  const toggle = (recurso: string, accion: string) => {
    const key = `${recurso}:${accion}`;
    setSel((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const onSave = () => {
    const permisos = Array.from(sel).map((s) => {
      const [recurso, accion] = s.split(":");
      return { recurso, accion };
    });
    save.mutate(
      { permisos },
      { onSuccess: () => { toast.success("Permisos actualizados"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Permisos · ${rol.nombre}`}
      description="Marca todos los permisos del rol y guarda una sola vez. Usa la fila/columna * como comodín."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button loading={save.isPending} onClick={onSave}>Guardar permisos ({sel.size})</Button>
        </>
      }
    >
      <div className="max-h-[60vh] overflow-auto rounded-xl border border-slate-200">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50">
            <tr>
              <th className="p-2 text-left font-medium text-slate-500">Recurso</th>
              {ACCIONES_COLS.map((a) => (
                <th key={a} className="p-2 text-center font-mono text-xs text-slate-500">{a}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RECURSOS_ROWS.map((r) => (
              <tr key={r} className="border-t border-slate-100 hover:bg-slate-50/60">
                <td className="p-2 font-mono text-xs text-slate-700">{r}</td>
                {ACCIONES_COLS.map((a) => {
                  const checked = sel.has(`${r}:${a}`);
                  return (
                    <td key={a} className="p-2 text-center">
                      <input
                        type="checkbox"
                        className="h-4 w-4 cursor-pointer accent-brand-600"
                        checked={checked}
                        onChange={() => toggle(r, a)}
                        aria-label={`${r}:${a}`}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
