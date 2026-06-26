import { useState } from "react";
import { Plus, FileText, ExternalLink, Pencil, Trash2, BadgeCheck, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useFacturas, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Factura, RucConsulta } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Modal } from "@/components/ui/Modal";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Field, Input } from "@/components/ui/Field";
import { formatMoney, formatDate } from "@/lib/utils";

export default function FacturasPage() {
  const { can } = useAuth();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Factura | null>(null);
  const [toDelete, setToDelete] = useState<Factura | null>(null);
  const { data, isLoading } = useFacturas({ limit: 200 });
  const writable = can("facturas", "write");
  const del = useApiMutation((id: number) => api.delete(`/facturas/${id}`), ["facturas"]);

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
            {
              header: "",
              align: "right",
              cell: (f) => (
                <div className="flex items-center justify-end gap-1">
                  {f.url && (
                    <a href={f.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
                      <FileText className="h-4 w-4" /> Ver <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  {writable && (
                    <>
                      <Button size="icon" variant="ghost" title="Editar factura" onClick={() => setEditing(f)}><Pencil className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" className="text-rose-500" title="Eliminar factura" onClick={() => setToDelete(f)}><Trash2 className="h-4 w-4" /></Button>
                    </>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>
      {(creating || editing) && <FacturaForm factura={editing} onClose={() => { setCreating(false); setEditing(null); }} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar factura"
        description={`¿Eliminar la factura #${toDelete?.id} de la orden #${toDelete?.orden_id}?`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Factura eliminada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

function FacturaForm({ factura, onClose }: { factura: Factura | null; onClose: () => void }) {
  const isEdit = !!factura;
  const [form, setForm] = useState({
    orden_id: factura ? String(factura.orden_id) : "",
    ruc: factura?.ruc ?? "",
    monto: factura ? String(factura.monto) : "",
    url: factura?.url ?? "",
  });
  const [rucInfo, setRucInfo] = useState<RucConsulta | null>(null);
  const [rucChecking, setRucChecking] = useState(false);
  const m = useApiMutation(
    (body: any) => (isEdit ? api.patch(`/facturas/${factura!.id}`, body) : api.post(`/ordenes/${form.orden_id}/facturas`, body)),
    ["facturas"],
  );

  // Consulta el RUC contra SUNAT (formato/dígito + estado) antes de emitir.
  const validarRuc = async () => {
    const ruc = form.ruc.trim();
    if (!/^\d{11}$/.test(ruc)) return toast.error("El RUC debe tener exactamente 11 dígitos");
    setRucChecking(true);
    setRucInfo(null);
    try {
      const { data } = await api.get<RucConsulta>(`/facturas/validar-ruc/${ruc}`);
      setRucInfo(data);
      toast.success(data.verificado_sunat ? `RUC activo: ${data.razon_social ?? "—"}` : "RUC con formato válido");
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setRucChecking(false);
    }
  };

  const submit = () => {
    if (!form.orden_id || !form.monto) return toast.error("Orden y monto son obligatorios");
    if (form.ruc.trim() && !/^\d{11}$/.test(form.ruc.trim())) return toast.error("El RUC debe tener exactamente 11 dígitos");
    m.mutate(
      { ruc: form.ruc.trim() || null, monto: Number(form.monto), url: form.url || null },
      { onSuccess: () => { toast.success(isEdit ? "Factura actualizada" : "Factura creada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };
  return (
    <Modal open onClose={onClose} title={isEdit ? `Editar factura #${factura!.id}` : "Nueva factura"} footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>{isEdit ? "Guardar" : "Crear"}</Button></>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Orden ID" required><Input type="number" value={form.orden_id} disabled={isEdit} onChange={(e) => setForm({ ...form, orden_id: e.target.value })} /></Field>
          <Field label="Monto" required><Input type="number" step="0.01" value={form.monto} onChange={(e) => setForm({ ...form, monto: e.target.value })} /></Field>
        </div>
        <Field label="RUC" hint="11 dígitos · se valida con SUNAT al emitir">
          <div className="flex items-center gap-2">
            <Input
              value={form.ruc}
              inputMode="numeric"
              maxLength={11}
              onChange={(e) => { setForm({ ...form, ruc: e.target.value.replace(/\D/g, "") }); setRucInfo(null); }}
              placeholder="20123456789"
            />
            <Button type="button" variant="outline" loading={rucChecking} disabled={!form.ruc} onClick={validarRuc}>
              Validar
            </Button>
          </div>
        </Field>
        {rucInfo && (
          <div className={`flex items-start gap-2 rounded-lg border p-2.5 text-xs ${rucInfo.verificado_sunat && rucInfo.activo === false ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
            {rucInfo.verificado_sunat && rucInfo.activo === false ? <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /> : <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0" />}
            <div>
              {rucInfo.verificado_sunat ? (
                <>
                  <p className="font-semibold">{rucInfo.razon_social ?? "RUC válido"}</p>
                  <p>Estado: {rucInfo.estado ?? "—"} · Condición: {rucInfo.condicion ?? "—"}</p>
                </>
              ) : (
                <p>Formato y dígito verificador correctos (sin consulta a SUNAT configurada).</p>
              )}
            </div>
          </div>
        )}
        <Field label="URL del comprobante"><Input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…" /></Field>
      </div>
    </Modal>
  );
}
