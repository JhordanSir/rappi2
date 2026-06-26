import { useState } from "react";
import { Plus, FileText, ExternalLink } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useFacturas, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Modal } from "@/components/ui/Modal";
import { Field, Input } from "@/components/ui/Field";
import { formatMoney, formatDate } from "@/lib/utils";

export default function FacturasPage() {
  const { can } = useAuth();
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useFacturas({ limit: 200 });
  const writable = can("facturas", "write");

  return (
    <div>
      <PageHeader
        title="Facturas"
        subtitle="Comprobantes emitidos por orden"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nueva factura</Button>}
      />
      <Card>
        <DataTable
          rows={data}
          loading={isLoading}
          rowKey={(f) => f.id}
          columns={[
            { header: "ID", cell: (f) => <span className="font-mono text-xs text-slate-500">#{f.id}</span> },
            { header: "Orden", cell: (f) => <span className="font-mono text-xs">#{f.orden_id}</span> },
            { header: "RUC", cell: (f) => f.ruc || "—" },
            { header: "Monto", align: "right", cell: (f) => <span className="font-semibold">{formatMoney(f.monto)}</span> },
            { header: "Fecha", cell: (f) => <span className="text-slate-500">{formatDate(f.fecha)}</span> },
            { header: "", align: "right", cell: (f) => f.url ? (
              <a href={f.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                <FileText className="h-4 w-4" /> Ver <ExternalLink className="h-3 w-3" />
              </a>
            ) : "—" },
          ]}
        />
      </Card>
      {creating && <FacturaForm onClose={() => setCreating(false)} />}
    </div>
  );
}

function FacturaForm({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ orden_id: "", ruc: "", monto: "", url: "" });
  const m = useApiMutation((body: any) => api.post(`/ordenes/${form.orden_id}/facturas`, body), ["facturas"]);
  const submit = () => {
    if (!form.orden_id || !form.monto) return toast.error("Orden y monto son obligatorios");
    if (form.ruc.trim() && !/^\d{11}$/.test(form.ruc.trim())) return toast.error("El RUC debe tener exactamente 11 dígitos");
    m.mutate(
      { ruc: form.ruc.trim() || null, monto: Number(form.monto), url: form.url || null },
      { onSuccess: () => { toast.success("Factura creada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };
  return (
    <Modal open onClose={onClose} title="Nueva factura" footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Crear</Button></>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Orden ID" required><Input type="number" value={form.orden_id} onChange={(e) => setForm({ ...form, orden_id: e.target.value })} /></Field>
          <Field label="Monto" required><Input type="number" step="0.01" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} /></Field>
        </div>
        <Field label="RUC" hint="11 dígitos"><Input value={form.ruc} inputMode="numeric" maxLength={11} onChange={(e) => setForm({ ...form, ruc: e.target.value.replace(/\D/g, "") })} placeholder="20123456789" /></Field>
        <Field label="URL del comprobante"><Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" /></Field>
      </div>
    </Modal>
  );
}
