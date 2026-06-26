import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ArrowRight, MapPin, Flag, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { reverseGeocode } from "@/lib/geo";
import { useApiMutation, useClientes, useDebouncedValue, usePaginated } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Cotizacion, EstadoOrden, NivelServicio, Orden } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Pagination } from "@/components/ui/Pagination";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select } from "@/components/ui/Field";
import { SearchInput, Toolbar } from "@/components/ui/Toolbar";
import { LocationPicker } from "@/components/map/MapView";
import { formatMoney, formatDate, formatCoord } from "@/lib/utils";

const ESTADOS: EstadoOrden[] = ["Pendiente", "En Proceso", "En Tránsito", "Entregado", "Cancelado"];
const PAGE_SIZE = 20;

export default function OrdenesPage() {
  const navigate = useNavigate();
  const { can, user } = useAuth();
  const [estado, setEstado] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [creating, setCreating] = useState(false);
  // Aislamiento por rol Cliente: si el usuario está vinculado a un cliente, solo ve sus órdenes.
  const scope = user?.cliente_id ?? null;
  const dq = useDebouncedValue(search.trim());

  // Al cambiar filtros o búsqueda volvemos a la primera página.
  useEffect(() => setPage(0), [estado, dq, scope]);

  const { data, isLoading } = usePaginated<Orden>("ordenes", "/ordenes/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(estado ? { estado } : {}),
    ...(scope ? { cliente_id: scope } : {}),
    ...(dq ? { q: dq } : {}),
  });
  const { data: clientes } = useClientes({ limit: 200 }, can("clientes", "read"));

  const clienteName = (id: number) => clientes?.find((c) => c.id === id)?.nombre ?? `#${id}`;
  const rows = data?.items;
  const total = data?.total ?? 0;

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
          footer={<Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />}
          columns={[
            { header: "ID", cell: (o) => <span className="font-mono text-xs font-semibold text-slate-500">#{o.id}</span> },
            { header: "Cliente", cell: (o) => <span className="font-medium text-slate-800">{clienteName(o.cliente_id)}</span> },
            {
              header: "Ruta",
              cell: (o) => (
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <span title={o.direccion_origen} className="max-w-[140px] truncate">{o.direccion_origen}</span>
                  <ArrowRight className="h-3 w-3 shrink-0 text-slate-400" />
                  <span title={o.direccion_destino} className="max-w-[140px] truncate">{o.direccion_destino}</span>
                  {(o.destinos?.length ?? 1) > 1 && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">+{o.destinos!.length - 1}</span>}
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

interface DestForm { direccion: string; nombre: string; punto: [number, number] | null; peso: string; largo: string; ancho: string; alto: string }
const nuevoDest = (): DestForm => ({ direccion: "", nombre: "", punto: null, peso: "", largo: "", ancho: "", alto: "" });

function OrdenForm({ onClose, clientes, lockedClienteId }: { onClose: () => void; clientes: { id: number; nombre: string }[]; lockedClienteId?: number | null }) {
  const [clienteId, setClienteId] = useState(lockedClienteId ? String(lockedClienteId) : "");
  const [dirOrigen, setDirOrigen] = useState("");
  const [origen, setOrigen] = useState<[number, number] | null>(null);
  const [destinos, setDestinos] = useState<DestForm[]>([nuevoDest()]);
  const [nivel, setNivel] = useState<NivelServicio>("estandar");
  const [ajuste, setAjuste] = useState("");
  const [ajusteMotivo, setAjusteMotivo] = useState("");
  const [cot, setCot] = useState<Cotizacion | null>(null);
  const m = useApiMutation((body: any) => api.post("/ordenes/", body), ["ordenes"]);

  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const setDest = (i: number, patch: Partial<DestForm>) => setDestinos((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  const listos = () => destinos.filter((d) => d.punto);

  useEffect(() => {
    if (!origen || listos().length === 0) { setCot(null); return; }
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post<Cotizacion>("/ordenes/cotizar", {
          lat_origen: origen[0], lon_origen: origen[1], nivel_servicio: nivel,
          destinos: listos().map((d) => ({ lat: d.punto![0], lon: d.punto![1], peso_kg: num(d.peso), largo_cm: num(d.largo), ancho_cm: num(d.ancho), alto_cm: num(d.alto) })),
        });
        setCot(data);
      } catch { setCot(null); }
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origen, destinos, nivel]);

  const total = cot ? cot.total + (num(ajuste) ?? 0) : null;

  const submit = () => {
    if (!clienteId) return toast.error("Selecciona un cliente");
    if (!dirOrigen || !origen) return toast.error("Indica y fija el origen");
    const ds = listos();
    if (ds.length === 0) return toast.error("Fija al menos un destino en el mapa");
    if (ds.some((d) => !d.direccion)) return toast.error("Cada destino necesita dirección");
    m.mutate(
      {
        cliente_id: Number(clienteId),
        direccion_origen: dirOrigen, lat_origen: origen[0], lon_origen: origen[1],
        nivel_servicio: nivel,
        ajuste_monto: num(ajuste), ajuste_motivo: ajusteMotivo || null,
        destinos: ds.map((d) => ({ direccion: d.direccion, lat: d.punto![0], lon: d.punto![1], nombre_destinatario: d.nombre || null, peso_kg: num(d.peso), largo_cm: num(d.largo), ancho_cm: num(d.ancho), alto_cm: num(d.alto) })),
      },
      { onSuccess: () => { toast.success("Orden creada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open onClose={onClose} size="xl"
      title="Nueva orden"
      description="Origen + uno o varios destinos. El precio se calcula automáticamente (suma de tramos); puedes aplicar un ajuste."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Crear orden{total != null ? ` · S/ ${total.toFixed(2)}` : ""}</Button></>}
    >
      <div className="space-y-5">
        <Field label="Cliente" required>
          <Select value={clienteId} onChange={(e) => setClienteId(e.target.value)} disabled={!!lockedClienteId}>
            <option value="">Seleccionar…</option>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </Select>
        </Field>

        <div className="rounded-xl border border-slate-200 p-4">
          <p className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-emerald-600"><MapPin className="h-4 w-4" /> Origen (recojo)</p>
          <Field label="Dirección" required><Input value={dirOrigen} onChange={(e) => setDirOrigen(e.target.value)} /></Field>
          <div className="mt-3"><LocationPicker value={origen} onChange={async (p) => { setOrigen(p); if (p) { const dir = await reverseGeocode(p[0], p[1]); if (dir) setDirOrigen(dir); } }} height={200} color="#10b981" /></div>
          <p className="text-center text-xs font-mono text-slate-400">{formatCoord(origen?.[0], origen?.[1])}</p>
        </div>

        {destinos.map((d, i) => (
          <div key={i} className="rounded-xl border border-slate-200 p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-rose-600"><Flag className="h-4 w-4" /> Destino {i + 1}</p>
              {destinos.length > 1 && <button type="button" onClick={() => setDestinos((ds) => ds.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-4 w-4" /></button>}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Dirección" required><Input value={d.direccion} onChange={(e) => setDest(i, { direccion: e.target.value })} /></Field>
              <Field label="Destinatario"><Input value={d.nombre} onChange={(e) => setDest(i, { nombre: e.target.value })} /></Field>
            </div>
            <div className="mt-3"><LocationPicker value={d.punto} onChange={async (p) => { setDest(i, { punto: p }); if (p) { const dir = await reverseGeocode(p[0], p[1]); if (dir) setDest(i, { direccion: dir }); } }} height={200} color="#f43f5e" /></div>
            <div className="mt-3 grid grid-cols-4 gap-2">
              <Field label="Peso kg"><Input type="number" value={d.peso} onChange={(e) => setDest(i, { peso: e.target.value })} /></Field>
              <Field label="Largo"><Input type="number" value={d.largo} onChange={(e) => setDest(i, { largo: e.target.value })} /></Field>
              <Field label="Ancho"><Input type="number" value={d.ancho} onChange={(e) => setDest(i, { ancho: e.target.value })} /></Field>
              <Field label="Alto"><Input type="number" value={d.alto} onChange={(e) => setDest(i, { alto: e.target.value })} /></Field>
            </div>
          </div>
        ))}
        <Button type="button" variant="outline" onClick={() => setDestinos((ds) => [...ds, nuevoDest()])}><Plus className="h-4 w-4" /> Agregar destino</Button>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Nivel de servicio">
            <Select value={nivel} onChange={(e) => setNivel(e.target.value as NivelServicio)}>
              <option value="estandar">Estándar</option><option value="express">Express</option><option value="urgente">Urgente</option>
            </Select>
          </Field>
          <Field label="Ajuste (PEN)" hint="− descuento / + recargo">
            <Input type="number" step="0.01" value={ajuste} onChange={(e) => setAjuste(e.target.value)} placeholder="0.00" />
          </Field>
          <Field label="Motivo del ajuste"><Input value={ajusteMotivo} onChange={(e) => setAjusteMotivo(e.target.value)} placeholder="Cliente frecuente…" /></Field>
        </div>

        {cot && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm">
            <div className="flex justify-between text-slate-600"><span>Precio calculado ({cot.tramos.length} tramo{cot.tramos.length > 1 ? "s" : ""})</span><span>S/ {cot.total.toFixed(2)}</span></div>
            {num(ajuste) != null && <div className="flex justify-between text-slate-600"><span>Ajuste</span><span>{(num(ajuste) ?? 0) >= 0 ? "+" : ""}{(num(ajuste) ?? 0).toFixed(2)}</span></div>}
            <div className="mt-1 flex justify-between border-t border-emerald-200 pt-1 font-semibold text-stone-800"><span>Total</span><span>S/ {(total ?? cot.total).toFixed(2)}</span></div>
          </div>
        )}
      </div>
    </Modal>
  );
}
