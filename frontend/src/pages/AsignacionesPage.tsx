import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Play, CheckCircle2, Trash2, ExternalLink, Camera, RotateCcw } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useAsignaciones, useOrdenes, useConductores, useVehiculos, useApiMutation, usePruebasEntrega } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Asignacion } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Toolbar, SearchInput } from "@/components/ui/Toolbar";
import { formatDate } from "@/lib/utils";

export default function AsignacionesPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const [creating, setCreating] = useState(false);
  const [finalizing, setFinalizing] = useState<Asignacion | null>(null);
  const [toDelete, setToDelete] = useState<Asignacion | null>(null);
  const [viewing, setViewing] = useState<Asignacion | null>(null);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useAsignaciones({ limit: 200 });
  const { data: conductores } = useConductores({ limit: 200 });
  const writable = can("asignaciones", "write");

  const condName = (id: number) => conductores?.find((c) => c.id === id)?.nombre ?? `#${id}`;
  const iniciar = useApiMutation((id: number) => api.patch(`/asignaciones/${id}/iniciar`), ["asignaciones", "ordenes"]);
  const reabrir = useApiMutation((id: number) => api.patch(`/asignaciones/${id}/reabrir`), ["asignaciones", "ordenes"]);
  const del = useApiMutation((id: number) => api.delete(`/asignaciones/${id}`), ["asignaciones"]);

  const rows = useMemo(
    () => (data ?? []).filter((a) => !search || String(a.orden_id).includes(search) || a.vehiculo_placa.toLowerCase().includes(search.toLowerCase())),
    [data, search],
  );

  return (
    <div>
      <PageHeader
        title="Asignaciones"
        subtitle="Asigna órdenes a conductores y vehículos, e impulsa el flujo de entrega"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Nueva asignación</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por orden o placa…" />
      </Toolbar>

      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(a) => a.id}
          columns={[
            { header: "ID", cell: (a) => <span className="font-mono text-xs text-slate-500">#{a.id}</span> },
            {
              header: "Órdenes",
              cell: (a) => (
                <span className="inline-flex items-center gap-1.5">
                  <button onClick={() => navigate(`/ordenes/${a.orden_id}`)} className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
                    #{a.orden_id} <ExternalLink className="h-3 w-3" />
                  </button>
                  {(a.orden_ids?.length ?? 1) > 1 && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">+{a.orden_ids!.length - 1}</span>}
                </span>
              ),
            },
            { header: "Conductor", cell: (a) => condName(a.conductor_id) },
            { header: "Vehículo", cell: (a) => <span className="font-mono text-xs">{a.vehiculo_placa}</span> },
            { header: "Estado", cell: (a) => <StatusBadge kind="asignacion" value={a.estado} /> },
            { header: "Inicio", cell: (a) => <span className="text-slate-500">{a.fecha_inicio ? formatDate(a.fecha_inicio) : "—"}</span> },
            {
              header: "",
              align: "right",
              cell: (a) => (
                <div className="flex justify-end gap-1">
                  {(a.estado === "EnCurso" || a.estado === "Finalizada") && (
                    <Button size="sm" variant="ghost" onClick={() => setViewing(a)} title="Ver evidencia de entrega">
                      <Camera className="h-3.5 w-3.5" /> Evidencia
                    </Button>
                  )}
                  {writable && a.estado === "Asignada" && (
                    <Button size="sm" variant="secondary" onClick={() => iniciar.mutate(a.id, { onSuccess: () => toast.success("Asignación iniciada"), onError: (e) => toast.error(apiError(e)) })}>
                      <Play className="h-3.5 w-3.5" /> Iniciar
                    </Button>
                  )}
                  {writable && a.estado === "EnCurso" && (
                    <Button size="sm" variant="outline" onClick={() => setFinalizing(a)} title="Cierre forzado (excepción)">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Cerrar
                    </Button>
                  )}
                  {writable && a.estado === "Finalizada" && (
                    <Button size="sm" variant="ghost" title="Reabrir: vuelve a EnCurso (corrige un cierre por error)" onClick={() => reabrir.mutate(a.id, { onSuccess: () => toast.success("Asignación reabierta"), onError: (e) => toast.error(apiError(e)) })}>
                      <RotateCcw className="h-3.5 w-3.5" /> Reabrir
                    </Button>
                  )}
                  {writable && a.estado !== "EnCurso" && (
                    <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(a)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Card>

      {creating && <AsignacionForm onClose={() => setCreating(false)} />}
      {finalizing && <FinalizarModal asignacion={finalizing} onClose={() => setFinalizing(null)} />}
      {viewing && <EvidenciaModal asignacion={viewing} onClose={() => setViewing(null)} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar asignación"
        description={`¿Eliminar la asignación #${toDelete?.id}?`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Asignación eliminada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

type Sugerencia = { conductor_id: number; nombre: string; vehiculo_placa: string | null; distancia_km: number | null; rating: number | null; total_calificaciones: number; capacidad_kg: number | null; peso_requerido_kg: number; suficiente: boolean; cabe: boolean; restringido_plaqueo: boolean };

function AsignacionForm({ onClose }: { onClose: () => void }) {
  const { data: ordenes } = useOrdenes({ estado: "Pendiente", limit: 200 });
  const { data: conductores } = useConductores({ disponibilidad: "Disponible", limit: 200 });
  const { data: vehiculos } = useVehiculos({ estado: "Operativo", limit: 200 });
  const [ordenIds, setOrdenIds] = useState<number[]>([]);
  const [form, setForm] = useState({ conductor_id: "", vehiculo_placa: "" });
  const [sugerencias, setSugerencias] = useState<Sugerencia[] | null>(null);
  const [loadingSug, setLoadingSug] = useState(false);
  const m = useApiMutation((body: any) => api.post("/asignaciones/", body), ["asignaciones", "ordenes", "conductores"]);

  const toggleOrden = (id: number) =>
    setOrdenIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));

  const sugerir = async () => {
    if (ordenIds.length === 0) return toast.error("Selecciona al menos una orden");
    setLoadingSug(true);
    try {
      const { data } = await api.get<Sugerencia[]>("/asignaciones/sugerencia", { params: { orden_ids: ordenIds } });
      setSugerencias(data);
      if (data.length === 0) toast("No hay conductores disponibles ahora", { icon: "ℹ️" });
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoadingSug(false);
    }
  };

  const elegir = (s: Sugerencia) =>
    setForm({ ...form, conductor_id: String(s.conductor_id), vehiculo_placa: s.vehiculo_placa ?? "" });

  const submit = () => {
    if (ordenIds.length === 0 || !form.conductor_id || !form.vehiculo_placa) return toast.error("Completa todos los campos");
    m.mutate(
      { orden_ids: ordenIds, conductor_id: Number(form.conductor_id), vehiculo_placa: form.vehiculo_placa },
      { onSuccess: () => { toast.success("Asignación creada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Nueva asignación"
      description="Agrupa una o varias órdenes pendientes en la ruta de un conductor."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Asignar {ordenIds.length > 1 ? `(${ordenIds.length})` : ""}</Button></>}
    >
      <div className="space-y-4">
        <Field label="Órdenes pendientes (puedes elegir varias)" required>
          <div className="max-h-48 space-y-1 overflow-y-auto rounded-xl border border-slate-200 p-2">
            {ordenes?.length === 0 && <p className="p-2 text-sm text-slate-400">No hay órdenes pendientes.</p>}
            {ordenes?.map((o) => (
              <label key={o.id} className={`flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${ordenIds.includes(o.id) ? "bg-brand-50 text-brand-800" : "hover:bg-slate-50"}`}>
                <input type="checkbox" checked={ordenIds.includes(o.id)} onChange={() => { toggleOrden(o.id); setSugerencias(null); }} />
                <span className="font-medium">#{o.id}</span>
                <span title={o.direccion_destino} className="truncate text-slate-500">{o.direccion_destino}{(o.destinos?.length ?? 0) > 1 ? ` (+${o.destinos!.length - 1})` : ""}</span>
              </label>
            ))}
          </div>
        </Field>

        {/* Asignación híbrida: el sistema sugiere y el despachador confirma. */}
        <div className="rounded-xl border border-brand-200 bg-brand-50/50 p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-brand-800">Sugerencia automática</p>
            <Button size="sm" variant="outline" loading={loadingSug} disabled={ordenIds.length === 0} onClick={sugerir}>
              Sugerir conductor
            </Button>
          </div>
          {sugerencias && sugerencias.length > 0 && (
            <>
              {sugerencias[0].peso_requerido_kg > 0 && (
                <p className="mt-2 text-xs text-slate-500">Peso a transportar: <strong>{sugerencias[0].peso_requerido_kg} kg</strong></p>
              )}
              <ul className="mt-2 space-y-1.5">
                {sugerencias.map((s) => (
                  <li key={s.conductor_id}>
                    <button
                      type="button"
                      onClick={() => elegir(s)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition ${
                        String(s.conductor_id) === form.conductor_id ? "border-brand-500 bg-white ring-1 ring-brand-300" : "border-slate-200 bg-white hover:bg-slate-50"
                      } ${!s.suficiente || !s.cabe ? "opacity-70" : ""}`}
                    >
                      <span className="font-medium text-slate-700">
                        {s.nombre} <span className="font-mono text-xs text-slate-400">{s.vehiculo_placa}</span>
                        {!s.suficiente && <span className="ml-1.5 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-600">capacidad insuficiente</span>}
                        {!s.cabe && <span className="ml-1.5 rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-600" title="El paquete más grande no cabe en las dimensiones del vehículo">no cabe (dimensiones)</span>}
                        {s.restringido_plaqueo && <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700" title="Restringido por plaqueo ese día: la ruta rebordeará el centro histórico, o se bloqueará si el recojo/entrega está dentro.">plaqueo (centro histórico)</span>}
                      </span>
                      <span className="text-xs text-slate-500">
                        {s.capacidad_kg != null && `${s.capacidad_kg} kg · `}
                        {s.distancia_km != null ? `${s.distancia_km} km` : "sin ubic."}
                        {s.rating != null && ` · ★ ${s.rating}`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <Field label="Conductor disponible" required>
          <Select value={form.conductor_id} onChange={(e) => setForm({ ...form, conductor_id: e.target.value })}>
            <option value="">Seleccionar…</option>
            {conductores?.map((c) => <option key={c.id} value={c.id}>{c.nombre} {c.vehiculo_placa ? `· ${c.vehiculo_placa}` : ""}</option>)}
          </Select>
        </Field>
        <Field label="Vehículo operativo" required>
          <Select value={form.vehiculo_placa} onChange={(e) => setForm({ ...form, vehiculo_placa: e.target.value })}>
            <option value="">Seleccionar…</option>
            {vehiculos?.map((v) => <option key={v.placa} value={v.placa}>{v.placa} · {v.tipo}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

function EvidenciaModal({ asignacion, onClose }: { asignacion: Asignacion; onClose: () => void }) {
  const { data: entregas, isLoading } = usePruebasEntrega(asignacion.id);
  const abrir = async (fileId: string) => {
    try {
      const res = await api.get(`/asignaciones/prueba-entrega/archivos/${fileId}`, { responseType: "blob" });
      window.open(URL.createObjectURL(res.data as Blob), "_blank");
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Evidencia de entrega · Asignación #${asignacion.id}`}
      description="Fotos/firmas capturadas por el conductor al entregar (para auditoría y disputas)."
      footer={<Button variant="outline" onClick={onClose}>Cerrar</Button>}
    >
      {isLoading ? (
        <p className="text-sm text-slate-500">Cargando evidencia…</p>
      ) : !entregas || entregas.length === 0 ? (
        <p className="text-sm text-slate-500">Esta asignación aún no tiene evidencia de entrega.</p>
      ) : (
        <div className="space-y-4">
          {entregas.map((ev) => (
            <div key={ev.id} className="rounded-xl border border-slate-200 p-3">
              <div className="mb-2 text-xs text-slate-500">
                {ev.receptor ? <>Recibió <span className="font-medium text-slate-700">{ev.receptor}</span> · </> : null}
                {formatDate(ev.timestamp)}
                {ev.descripcion ? ` · ${ev.descripcion}` : ""}
              </div>
              <div className="flex flex-wrap gap-2">
                {ev.archivos.map((a) => (
                  <button
                    key={a.file_id}
                    onClick={() => abrir(a.file_id)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 hover:bg-slate-200"
                  >
                    <Camera className="h-3.5 w-3.5" /> {a.filename}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

function FinalizarModal({ asignacion, onClose }: { asignacion: Asignacion; onClose: () => void }) {
  const [receptor, setReceptor] = useState("");
  const [motivo, setMotivo] = useState("");
  const m = useApiMutation(
    (body: any) => api.patch(`/asignaciones/${asignacion.id}/finalizar`, body),
    ["asignaciones", "ordenes"],
  );
  const submit = () => {
    if (!motivo.trim()) return toast.error("El cierre forzado requiere un motivo");
    m.mutate(
      { receptor: receptor || null, nota: motivo.trim() },
      { onSuccess: () => { toast.success("Run cerrado"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Cierre forzado del run"
      description="Excepción: cierra el run sin la prueba del conductor. El motivo queda registrado como incidencia para auditoría. Lo normal es que el conductor cierre cada destino con foto."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button variant="success" loading={m.isPending} onClick={submit}>Forzar cierre</Button></>}
    >
      <div className="space-y-4">
        <Field label="Motivo del cierre forzado" required>
          <Textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: entrega confirmada por teléfono con el cliente." />
        </Field>
        <Field label="Recibido por (opcional)"><Input value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre de quien recibió" /></Field>
      </div>
    </Modal>
  );
}
