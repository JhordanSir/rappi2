import { useState } from "react";
import { Plus, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { usePagos, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { EstadoPago } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select } from "@/components/ui/Field";
import { Toolbar } from "@/components/ui/Toolbar";
import { formatMoney, formatDate } from "@/lib/utils";

const ESTADOS: EstadoPago[] = ["Pendiente", "Pagado", "Fallido", "Reembolsado"];

export default function PagosPage() {
  const { can } = useAuth();
  const [estado, setEstado] = useState("");
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = usePagos({ limit: 200, ...(estado ? { estado } : {}) });
  const writable = can("pagos", "write");
  const patch = useApiMutation((id: number) => api.patch(`/pagos/${id}`, { estado: "Pagado" }), ["pagos"]);

  return (
    <div>
      <PageHeader
        title="Pagos"
        subtitle="Cobros asociados a las órdenes"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Registrar pago</Button>}
      />
      <Toolbar>
        <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="h-10 w-auto">
          <option value="">Todos los estados</option>
          {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
        </Select>
      </Toolbar>
      <Card>
        <DataTable
          rows={data}
          loading={isLoading}
          rowKey={(p) => p.id}
          columns={[
            { header: "ID", cell: (p) => <span className="font-mono text-xs text-slate-500">#{p.id}</span> },
            { header: "Orden", cell: (p) => <span className="font-mono text-xs">#{p.orden_id}</span> },
            { header: "Monto", align: "right", cell: (p) => <span className="font-semibold">{formatMoney(p.monto)}</span> },
            { header: "Estado", cell: (p) => <StatusBadge kind="pago" value={p.estado} /> },
            { header: "Referencia", cell: (p) => p.referencia_banco || "—" },
            { header: "Fecha", cell: (p) => <span className="text-slate-500">{formatDate(p.fecha_pago)}</span> },
            { header: "", align: "right", cell: (p) => writable && p.estado === "Pendiente" && (
              <Button size="sm" variant="success" onClick={() => patch.mutate(p.id, { onSuccess: () => toast.success("Pago confirmado"), onError: (e) => toast.error(apiError(e)) })}>
                <CheckCircle2 className="h-3.5 w-3.5" /> Confirmar
              </Button>
            )},
          ]}
        />
      </Card>
      {creating && <PagoForm onClose={() => setCreating(false)} />}
    </div>
  );
}

function PagoForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ orden_id: "", monto: "", estado: "Pendiente", referencia_banco: "" });
  const m = useApiMutation((body: any) => api.post(`/ordenes/${form.orden_id}/pagos`, body), ["pagos"]);
  const submit = () => {
    if (!form.orden_id || !form.monto) return toast.error("Orden y monto son obligatorios");
    m.mutate(
      { monto: Number(form.monto), estado: form.estado, referencia_banco: form.referencia_banco || null },
      { onSuccess: () => { toast.success("Pago registrado"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };
  return (
    <Modal open onClose={onClose} title="Registrar pago" footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Registrar</Button></>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Orden ID" required><Input type="number" value={form.orden_id} onChange={(e) => setForm({ ...form, orden_id: e.target.value })} /></Field>
          <Field label="Monto" required><Input type="number" step="0.01" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Estado">
            <Select value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value })}>
              {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
            </Select>
          </Field>
          <Field label="Referencia banco"><Input value={form.referencia_banco} onChange={(e) => setForm({ ...form, referencia_banco: e.target.value })} /></Field>
        </div>
      </div>
    </Modal>
  );
}
