import { useEffect, useState } from "react";
import { Plus, CheckCircle2, Eye } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useApiMutation, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { EstadoPago, Pago } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable, toggleSort, type SortState } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { DetailModal } from "@/components/ui/DetailModal";
import { Field, Input, Select } from "@/components/ui/Field";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { formatMoney, formatDate } from "@/lib/utils";

const ESTADOS: EstadoPago[] = ["Pendiente", "Pagado", "Fallido", "Reembolsado"];
const PAGE_SIZE = 20;

export default function PagosPage() {
  const { can } = useAuth();
  const [estado, setEstado] = useState("");
  const [proveedor, setProveedor] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortState | null>(null);
  const [page, setPage] = useState(0);
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<Pago | null>(null);
  const dq = useDebouncedValue(search.trim());
  useEffect(() => setPage(0), [estado, proveedor, desde, hasta, dq, sort]);
  const { data, isLoading } = usePaginated<Pago>("pagos", "/pagos", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(estado ? { estado } : {}),
    ...(proveedor ? { proveedor } : {}),
    ...(desde ? { desde } : {}),
    // Fin de día inclusivo: "hasta" cubre todo ese día.
    ...(hasta ? { hasta: `${hasta}T23:59:59` } : {}),
    ...(dq ? { q: dq } : {}),
    ...(sort ? { orden_por: sort.key, dir: sort.dir } : {}),
  });
  const rows = data?.items;
  const total = data?.total ?? 0;
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
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por #orden o referencia…" />
        <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="h-10 w-auto">
          <option value="">Todos los estados</option>
          {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
        </Select>
        <Select value={proveedor} onChange={(e) => setProveedor(e.target.value)} className="h-10 w-auto" title="Pasarela de pago">
          <option value="">Toda pasarela</option>
          <option value="mercadopago">MercadoPago</option>
          <option value="manual">Manual (staff)</option>
        </Select>
        <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="h-10 w-auto" title="Pagos desde" />
        <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="h-10 w-auto" title="Pagos hasta" />
      </Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(p) => p.id}
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          sort={sort}
          onSort={(k) => setSort((s) => toggleSort(s, k))}
          columns={[
            { header: "ID", sortKey: "id", cell: (p) => <span className="font-mono text-xs text-slate-500">#{p.id}</span> },
            { header: "Orden", sortKey: "orden_id", cell: (p) => <span className="font-mono text-xs">#{p.orden_id}</span> },
            { header: "Monto", sortKey: "monto", align: "right", cell: (p) => <span className="font-semibold">{formatMoney(p.monto)}</span> },
            { header: "Estado", sortKey: "estado", cell: (p) => <StatusBadge kind="pago" value={p.estado} /> },
            { header: "Referencia", cell: (p) => p.referencia_banco || "—" },
            { header: "Fecha", sortKey: "fecha_pago", cell: (p) => <span className="text-slate-500">{formatDate(p.fecha_pago)}</span> },
            { header: "", align: "right", cell: (p) => (
              <div className="flex items-center justify-end gap-1">
                <Button size="icon" variant="ghost" onClick={() => setViewing(p)}><Eye className="h-4 w-4" /></Button>
                {writable && p.estado === "Pendiente" && (
                  <Button size="sm" variant="success" onClick={() => patch.mutate(p.id, { onSuccess: () => toast.success("Pago confirmado"), onError: (e) => toast.error(apiError(e)) })}>
                    <CheckCircle2 className="h-3.5 w-3.5" /> Confirmar
                  </Button>
                )}
              </div>
            )},
          ]}
        />
      </Card>
      {creating && <PagoForm onClose={() => setCreating(false)} />}
      {viewing && (
        <DetailModal
          open
          onClose={() => setViewing(null)}
          title={`Pago #${viewing.id}`}
          description="Detalle del pago"
          rows={[
            { label: "ID", value: <span className="font-mono">#{viewing.id}</span> },
            { label: "Orden", value: <span className="font-mono">#{viewing.orden_id}</span> },
            { label: "Monto", value: <span className="font-semibold">{formatMoney(viewing.monto)}</span> },
            { label: "Estado", value: <StatusBadge kind="pago" value={viewing.estado} /> },
            { label: "Referencia banco", value: viewing.referencia_banco },
            { label: "Fecha", value: formatDate(viewing.fecha_pago) },
          ]}
        />
      )}
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
