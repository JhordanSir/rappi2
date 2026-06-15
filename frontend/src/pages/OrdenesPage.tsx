import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ArrowRight, MapPin } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useOrdenes, useClientes, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { EstadoOrden, Orden } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select } from "@/components/ui/Field";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { LocationPicker } from "@/components/map/MapView";
import { formatMoney, formatDate, formatCoord } from "@/lib/utils";

const ESTADOS: EstadoOrden[] = ["Pendiente", "En Proceso", "En Tránsito", "Entregado", "Cancelado"];

export default function OrdenesPage() {
  const navigate = useNavigate();
  const { can, user } = useAuth();
  const [estado, setEstado] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  // Aislamiento por rol Cliente: si el usuario está vinculado a un cliente, solo ve sus órdenes.
  const scope = user?.cliente_id ?? null;
  const { data, isLoading } = useOrdenes({ limit: 200, ...(estado ? { estado } : {}), ...(scope ? { cliente_id: scope } : {}) });
  const { data: clientes } = useClientes({ limit: 200 }, can("clientes", "read"));

  const clienteName = (id: number) => clientes?.find((c) => c.id === id)?.nombre ?? `#${id}`;

  const rows = useMemo(() => {
    const q = search.toLowerCase();
    return (data ?? []).filter(
      (o) => !q || o.direccion_origen.toLowerCase().includes(q) || o.direccion_destino.toLowerCase().includes(q) || String(o.id).includes(q),
    );
  }, [data, search]);

  return (
    <div>
      <PageHeader
        title={scope ? "Mis órdenes" : "Órdenes"}
        subtitle={scope ? "Tus pedidos de envío y su seguimiento" : "Pedidos de envío con origen y destino georreferenciados"}
        actions={can("ordenes", "write") && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nueva orden</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por ID o dirección…" />
        <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="h-10 w-auto">
          <option value="">Todos los estados</option>
          {ESTADOS.map((e) => <option key={e} value={e}>{e}</option>)}
        </Select>
      </Toolbar>

      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(o) => o.id}
          onRowClick={(o) => navigate(`/ordenes/${o.id}`)}
          columns={[
            { header: "ID", cell: (o) => <span className="font-mono text-xs font-semibold text-slate-500">#{o.id}</span> },
            { header: "Cliente", cell: (o) => <span className="font-medium text-slate-800">{clienteName(o.cliente_id)}</span> },
            {
              header: "Ruta",
              cell: (o) => (
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <span className="max-w-[140px] truncate">{o.direccion_origen}</span>
                  <ArrowRight className="h-3 w-3 shrink-0 text-slate-400" />
                  <span className="max-w-[140px] truncate">{o.direccion_destino}</span>
                </div>
              ),
            },
            { header: "Estado", cell: (o) => <StatusBadge kind="orden" value={o.estado} /> },
            { header: "Total", align: "right", cell: (o) => formatMoney(o.total) },
            { header: "Creada", cell: (o) => <span className="text-slate-500">{formatDate(o.fecha_creacion, false)}</span> },
          ]}
        />
      </Card>

      {creating && <OrdenForm onClose={() => setCreating(false)} clientes={clientes ?? []} lockedClienteId={scope} />}
    </div>
  );
}

function OrdenForm({ onClose, clientes, lockedClienteId }: { onClose: () => void; clientes: { id: number; nombre: string }[]; lockedClienteId?: number | null }) {
  const [form, setForm] = useState({
    cliente_id: lockedClienteId ? String(lockedClienteId) : "",
    direccion_origen: "",
    distrito_origen: "",
    direccion_destino: "",
    distrito_destino: "",
    total: "",
  });
  const [origen, setOrigen] = useState<[number, number] | null>(null);
  const [destino, setDestino] = useState<[number, number] | null>(null);
  const m = useApiMutation((body: any) => api.post("/ordenes/", body), ["ordenes"]);

  const submit = () => {
    if (!form.cliente_id) return toast.error("Selecciona un cliente");
    if (!form.direccion_origen || !form.direccion_destino) return toast.error("Origen y destino son obligatorios");
    m.mutate(
      {
        cliente_id: Number(form.cliente_id),
        direccion_origen: form.direccion_origen,
        distrito_origen: form.distrito_origen || null,
        direccion_destino: form.direccion_destino,
        distrito_destino: form.distrito_destino || null,
        total: form.total ? Number(form.total) : null,
        lat_origen: origen?.[0],
        lon_origen: origen?.[1],
        lat_destino: destino?.[0],
        lon_destino: destino?.[1],
      },
      {
        onSuccess: () => { toast.success("Orden creada"); onClose(); },
        onError: (e) => toast.error(apiError(e)),
      },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title="Nueva orden"
      description="Define el punto de partida y el de llegada. Marca las coordenadas en el mapa o déjalas para geocodificar."
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button loading={m.isPending} onClick={submit}>Crear orden</Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Cliente" required>
            <Select value={form.cliente_id} onChange={(e) => setForm({ ...form, cliente_id: e.target.value })} disabled={!!lockedClienteId}>
              <option value="">Seleccionar…</option>
              {lockedClienteId && !clientes.some((c) => c.id === lockedClienteId) && (
                <option value={lockedClienteId}>Mi cuenta (#{lockedClienteId})</option>
              )}
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </Select>
          </Field>
          <Field label="Total (PEN)">
            <Input type="number" step="0.01" value={form.total} onChange={(e) => setForm({ ...form, total: e.target.value })} placeholder="150.00" />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PointBlock
            color="#10b981"
            label="Punto de partida"
            tone="text-emerald-600"
            direccion={form.direccion_origen}
            distrito={form.distrito_origen}
            coord={origen}
            onDir={(v) => setForm({ ...form, direccion_origen: v })}
            onDist={(v) => setForm({ ...form, distrito_origen: v })}
            onCoord={setOrigen}
          />
          <PointBlock
            color="#f43f5e"
            label="Punto de llegada"
            tone="text-rose-600"
            direccion={form.direccion_destino}
            distrito={form.distrito_destino}
            coord={destino}
            onDir={(v) => setForm({ ...form, direccion_destino: v })}
            onDist={(v) => setForm({ ...form, distrito_destino: v })}
            onCoord={setDestino}
          />
        </div>
      </div>
    </Modal>
  );
}

function PointBlock({
  color, label, tone, direccion, distrito, coord, onDir, onDist, onCoord,
}: {
  color: string; label: string; tone: string;
  direccion: string; distrito: string; coord: [number, number] | null;
  onDir: (v: string) => void; onDist: (v: string) => void; onCoord: (p: [number, number]) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <p className={`mb-3 flex items-center gap-1.5 text-sm font-semibold ${tone}`}><MapPin className="h-4 w-4" /> {label}</p>
      <div className="space-y-3">
        <Field label="Dirección" required><Input value={direccion} onChange={(e) => onDir(e.target.value)} /></Field>
        <Field label="Distrito"><Input value={distrito} onChange={(e) => onDist(e.target.value)} /></Field>
        <LocationPicker value={coord} onChange={onCoord} height={220} color={color} />
        <p className="text-center text-xs font-mono text-slate-400">{formatCoord(coord?.[0], coord?.[1])}</p>
      </div>
    </div>
  );
}
