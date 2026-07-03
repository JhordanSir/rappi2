import { useRef, useState } from "react";
import { Plus, TriangleAlert, Trash2, Paperclip, Upload, Download, FileImage } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useIncidencias, useAsignaciones, useEvidencias, useApiMutation, useDebouncedValue } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import type { Incidencia, TipoEvidencia } from "@/types";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable, toggleSort, type SortState } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmModal } from "@/components/ui/Confirm";
import { Toolbar, SearchInput } from "@/components/ui/Toolbar";
import { formatDate } from "@/lib/utils";

function sevTone(s: number) {
  if (s >= 4) return "red";
  if (s === 3) return "amber";
  return "gray";
}

export default function IncidenciasPage() {
  const { can } = useAuth();
  const [search, setSearch] = useState("");
  const [sevMin, setSevMin] = useState("");
  const [origen, setOrigen] = useState("");
  const [creating, setCreating] = useState(false);
  const [evid, setEvid] = useState<Incidencia | null>(null);
  const [detail, setDetail] = useState<Incidencia | null>(null);
  const [toDelete, setToDelete] = useState<Incidencia | null>(null);
  // Búsqueda por tipo server-side (parámetro `tipo`, ilike) + filtros origen/severidad.
  const dq = useDebouncedValue(search.trim());
  const [sort, setSort] = useState<SortState | null>(null);
  const { data, isLoading } = useIncidencias({
    limit: 200,
    ...(sevMin ? { severidad_min: Number(sevMin) } : {}),
    ...(origen ? { origen } : {}),
    ...(dq && !/^#?\d+$/.test(dq) ? { tipo: dq } : {}),
    ...(dq && /^#?\d+$/.test(dq) ? { asignacion_id: Number(dq.replace("#", "")) } : {}),
    ...(sort ? { orden_por: sort.key, dir: sort.dir } : {}),
  });
  const writable = can("incidencias", "write");
  const del = useApiMutation((id: number) => api.delete(`/incidencias/${id}`), ["incidencias"]);
  const setSev = useApiMutation(
    ({ id, severidad }: { id: number; severidad: number }) => api.patch(`/incidencias/${id}`, { severidad }),
    ["incidencias"],
  );

  const rows = data;

  return (
    <div>
      <PageHeader
        title="Incidencias"
        subtitle="Eventos y problemas reportados durante las entregas"
        actions={writable && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> Reportar incidencia</Button>}
      />
      <Toolbar>
        <SearchInput value={search} onChange={setSearch} placeholder="Buscar por tipo o #asignación…" />
        <Select value={sevMin} onChange={(e) => setSevMin(e.target.value)} className="h-10 w-auto">
          <option value="">Toda severidad</option>
          {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>Severidad ≥ {s}</option>)}
        </Select>
        <Select value={origen} onChange={(e) => setOrigen(e.target.value)} className="h-10 w-auto" title="Origen del reporte">
          <option value="">Todo origen</option>
          <option value="chofer">Chofer</option>
          <option value="automatica">Automática</option>
          <option value="admin">Central</option>
        </Select>
      </Toolbar>
      <Card>
        <DataTable
          rows={rows}
          loading={isLoading}
          rowKey={(i) => i.id}
          onRowClick={(i) => setDetail(i)}
          sort={sort}
          onSort={(k) => setSort((s) => toggleSort(s, k))}
          columns={[
            { header: "ID", sortKey: "id", cell: (i) => <span className="font-mono text-xs text-slate-500">#{i.id}</span> },
            { header: "Tipo", sortKey: "tipo", cell: (i) => <span className="inline-flex items-center gap-1.5 font-medium text-slate-800"><TriangleAlert className="h-4 w-4 text-amber-500" /> {i.tipo}</span> },
            { header: "Asignación", sortKey: "asignacion_id", cell: (i) => <span className="font-mono text-xs">#{i.asignacion_id}</span> },
            { header: "Origen", sortKey: "origen", cell: (i) => <Badge tone={i.origen === "automatica" ? "red" : i.origen === "admin" ? "indigo" : "gray"}>{i.origen === "automatica" ? "Automática" : i.origen === "admin" ? "Central" : "Chofer"}</Badge> },
            { header: "Severidad", sortKey: "severidad", cell: (i) => (
              writable ? (
                <Select
                  className="h-8 w-auto"
                  value={String(i.severidad)}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => setSev.mutate({ id: i.id, severidad: Number(e.target.value) }, { onError: (err) => toast.error(apiError(err)) })}
                >
                  {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>Nivel {s}</option>)}
                </Select>
              ) : <Badge tone={sevTone(i.severidad) as any}>Nivel {i.severidad}</Badge>
            ) },
            { header: "Notas", cell: (i) => <span title={i.notas || undefined} className="line-clamp-2 max-w-[260px] text-slate-500">{i.notas || "—"}</span> },
            { header: "Fecha", sortKey: "fecha", cell: (i) => <span className="whitespace-nowrap text-slate-500">{formatDate(i.fecha)}</span> },
            { header: "", align: "right", cell: (i) => (
              <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="outline" onClick={() => setEvid(i)}><Paperclip className="h-3.5 w-3.5" /> Evidencias</Button>
                {can("incidencias", "delete") && <Button size="icon" variant="ghost" className="text-rose-500" onClick={() => setToDelete(i)}><Trash2 className="h-4 w-4" /></Button>}
              </div>
            )},
          ]}
        />
      </Card>
      {creating && <IncidenciaForm onClose={() => setCreating(false)} />}
      {detail && (
        <IncidenciaDetalle
          incidencia={detail}
          onClose={() => setDetail(null)}
          onEvidencias={() => { setEvid(detail); setDetail(null); }}
          writable={writable}
          onSeveridad={(severidad) => setSev.mutate({ id: detail.id, severidad }, {
            onSuccess: () => setDetail((d) => (d ? { ...d, severidad } : d)),
            onError: (err) => toast.error(apiError(err)),
          })}
        />
      )}
      {evid && <EvidenciasModal incidencia={evid} onClose={() => setEvid(null)} writable={can("incidencias", "write")} />}
      <ConfirmModal
        open={!!toDelete}
        title="Eliminar incidencia"
        description={`¿Eliminar la incidencia #${toDelete?.id}?`}
        danger
        confirmLabel="Eliminar"
        loading={del.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success("Incidencia eliminada"); setToDelete(null); }, onError: (e) => toast.error(apiError(e)) })}
      />
    </div>
  );
}

const ORIGEN_LABEL: Record<Incidencia["origen"], string> = {
  automatica: "Automática (sistema)",
  admin: "Central (administración)",
  chofer: "Chofer",
};

function IncidenciaDetalle({
  incidencia,
  onClose,
  onEvidencias,
  writable,
  onSeveridad,
}: {
  incidencia: Incidencia;
  onClose: () => void;
  onEvidencias: () => void;
  writable: boolean;
  onSeveridad: (severidad: number) => void;
}) {
  const i = incidencia;
  return (
    <Modal
      open
      onClose={onClose}
      title={`Incidencia #${i.id}`}
      description={`Reportada el ${formatDate(i.fecha)}`}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cerrar</Button>
          <Button onClick={onEvidencias}><Paperclip className="h-4 w-4" /> Ver evidencias</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Tipo</div>
            <div className="mt-0.5 inline-flex items-center gap-1.5 font-medium text-slate-800">
              <TriangleAlert className="h-4 w-4 text-amber-500" /> {i.tipo}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Asignación</div>
            <div className="mt-0.5 font-mono text-slate-700">#{i.asignacion_id}</div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Origen</div>
            <div className="mt-1">
              <Badge tone={i.origen === "automatica" ? "red" : i.origen === "admin" ? "indigo" : "gray"}>{ORIGEN_LABEL[i.origen]}</Badge>
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Severidad</div>
            <div className="mt-1">
              {writable ? (
                <Select className="h-8 w-auto" value={String(i.severidad)} onChange={(e) => onSeveridad(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>Nivel {s}</option>)}
                </Select>
              ) : <Badge tone={sevTone(i.severidad) as any}>Nivel {i.severidad}</Badge>}
            </div>
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Notas</div>
          <p className="mt-1 whitespace-pre-wrap rounded-xl bg-sillar-50 p-3 text-sm text-slate-700">{i.notas || "Sin notas."}</p>
        </div>
      </div>
    </Modal>
  );
}

function IncidenciaForm({ onClose }: { onClose: () => void }) {
  const { data: asignaciones } = useAsignaciones({ limit: 200 });
  const [form, setForm] = useState({ asignacion_id: "", tipo: "", notas: "" });
  const m = useApiMutation((body: any) => api.post("/incidencias/", body), ["incidencias"]);

  const submit = () => {
    if (!form.asignacion_id || !form.tipo) return toast.error("Asignación y tipo son obligatorios");
    m.mutate(
      { asignacion_id: Number(form.asignacion_id), tipo: form.tipo, notas: form.notas || null },
      { onSuccess: () => { toast.success("Incidencia registrada"); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Reportar incidencia"
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Registrar</Button></>}
    >
      <div className="space-y-4">
        <Field label="Asignación" required>
          <Select value={form.asignacion_id} onChange={(e) => setForm({ ...form, asignacion_id: e.target.value })}>
            <option value="">Seleccionar…</option>
            {asignaciones?.map((a) => <option key={a.id} value={a.id}>#{a.id} · Orden #{a.orden_id} · {a.estado}</option>)}
          </Select>
        </Field>
        <Field label="Tipo" required><Input value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })} placeholder="Retraso, Daño…" /></Field>
        <Field label="Notas"><Textarea value={form.notas} onChange={(e) => setForm({ ...form, notas: e.target.value })} placeholder="Describe el problema…" /></Field>
        <p className="text-xs text-slate-400">La severidad se asigna automáticamente por tipo y puede ajustarse en la lista.</p>
      </div>
    </Modal>
  );
}

async function descargarArchivo(fileId: string, filename: string) {
  try {
    const res = await api.get(`/incidencias/evidencias/archivos/${fileId}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    toast.error(apiError(e));
  }
}

function EvidenciasModal({ incidencia, onClose, writable }: { incidencia: Incidencia; onClose: () => void; writable: boolean }) {
  const { data, isLoading } = useEvidencias(incidencia.id);
  const [tipo, setTipo] = useState<TipoEvidencia>("foto");
  const [descripcion, setDescripcion] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const m = useApiMutation((fd: FormData) => api.post(`/incidencias/${incidencia.id}/evidencias/upload`, fd), ["evidencias"]);

  const subir = () => {
    if (files.length === 0) return toast.error("Selecciona al menos un archivo");
    const fd = new FormData();
    fd.append("tipo", tipo);
    if (descripcion) fd.append("descripcion", descripcion);
    files.forEach((f) => fd.append("archivos", f));
    m.mutate(fd, {
      onSuccess: () => { toast.success("Evidencia subida"); setFiles([]); setDescripcion(""); if (inputRef.current) inputRef.current.value = ""; },
      onError: (e) => toast.error(apiError(e)),
    });
  };

  return (
    <Modal open onClose={onClose} size="lg" title={`Evidencias · Incidencia #${incidencia.id}`} description="Fotos, videos o documentos almacenados en GridFS.">
      <div className="space-y-4">
        {writable && (
          <div className="rounded-xl border border-sillar-300 bg-sillar-50 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Tipo">
                <Select value={tipo} onChange={(e) => setTipo(e.target.value as TipoEvidencia)}>
                  {(["foto", "video", "audio", "documento"] as TipoEvidencia[]).map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label="Descripción"><Input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></Field>
            </div>
            <input ref={inputRef} type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} className="mt-3 block w-full text-sm text-stone-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-700" />
            <div className="mt-3 flex justify-end">
              <Button size="sm" loading={m.isPending} onClick={subir}><Upload className="h-4 w-4" /> Subir {files.length > 0 ? `(${files.length})` : ""}</Button>
            </div>
          </div>
        )}

        <div className="space-y-2">
          {isLoading && <p className="text-center text-sm text-stone-400">Cargando…</p>}
          {data?.length === 0 && <p className="rounded-xl bg-sillar-50 py-6 text-center text-sm text-stone-400">Sin evidencias aún</p>}
          {data?.map((ev) => (
            <div key={ev.id} className="rounded-xl border border-sillar-200 p-3">
              <div className="mb-2 flex items-center gap-2">
                <Badge tone="indigo">{ev.tipo}</Badge>
                {ev.descripcion && <span className="text-sm text-stone-600">{ev.descripcion}</span>}
                <span className="ml-auto text-xs text-stone-400">{formatDate(ev.timestamp)}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {ev.archivos.map((a) => (
                  <button key={a.file_id} onClick={() => descargarArchivo(a.file_id, a.filename)} className="inline-flex items-center gap-1.5 rounded-lg bg-sillar-100 px-2.5 py-1.5 text-xs text-stone-700 hover:bg-sillar-200">
                    <FileImage className="h-3.5 w-3.5 text-stone-400" /> {a.filename} <Download className="h-3 w-3" />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
