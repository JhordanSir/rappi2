import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Marker, Polyline, Popup } from "react-leaflet";
import { ArrowLeft, Play, Camera, AlertTriangle, MapPin, Radio, CheckCircle2, RefreshCw, XCircle, Package } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useSeguimiento } from "@/api/hooks";
import { useGpsTracking } from "@/api/useGpsTracking";
import { MapView, type LatLng } from "@/components/map/MapView";
import { pinIcon, COLORS } from "@/components/map/icons";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageLoader } from "@/components/ui/Feedback";
import type { Asignacion, Conductor } from "@/types";

const TIPOS_INCIDENCIA = ["Retraso por tráfico", "Dirección incorrecta", "Cliente ausente", "Daño en paquete", "Clima adverso", "Otro"];

export default function AsignacionDetalle() {
  const { id } = useParams();
  const asignacionId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const fallarFileRef = useRef<HTMLInputElement>(null);

  const { data: asg, isLoading } = useQuery({
    queryKey: ["asignacion", asignacionId],
    queryFn: async () => (await api.get<Asignacion>(`/asignaciones/${asignacionId}`)).data,
  });
  const { data: me } = useQuery({
    queryKey: ["conductor-me"],
    queryFn: async () => (await api.get<Conductor>("/conductores/me")).data,
  });
  const { data: seg } = useSeguimiento(asg?.orden_id, 0);

  const enCurso = asg?.estado === "EnCurso";
  const [gpsOn, setGpsOn] = useState(false);
  const [showInc, setShowInc] = useState(false);
  // Ocupado POR ACCIÓN ("iniciar", "entregar-{id}", "fallar-{id}", "incidencia"): cada
  // botón muestra su propio estado y las acciones no se bloquean entre sí.
  const [busy, setBusy] = useState<string | null>(null);
  const [inc, setInc] = useState({ tipo: TIPOS_INCIDENCIA[0], notas: "" });
  const [incFile, setIncFile] = useState<File | null>(null);
  // Entrega por destino: id del destino en curso + receptor + foto elegida (con preview:
  // el conductor VE la foto antes de confirmar; nada se envía al elegir el archivo).
  const [entregando, setEntregando] = useState<number | null>(null);
  const [receptor, setReceptor] = useState("");
  const [fotoEntrega, setFotoEntrega] = useState<File | null>(null);
  // No entrega: id del destino + motivo + foto de respaldo.
  const [fallando, setFallando] = useState<number | null>(null);
  const [motivoFallo, setMotivoFallo] = useState("");
  const [fotoFallo, setFotoFallo] = useState<File | null>(null);

  // Miniaturas de las fotos elegidas (se liberan al cambiar/desmontar).
  const previewEntrega = useMemo(() => (fotoEntrega ? URL.createObjectURL(fotoEntrega) : null), [fotoEntrega]);
  const previewFallo = useMemo(() => (fotoFallo ? URL.createObjectURL(fotoFallo) : null), [fotoFallo]);
  useEffect(() => () => { if (previewEntrega) URL.revokeObjectURL(previewEntrega); }, [previewEntrega]);
  useEffect(() => () => { if (previewFallo) URL.revokeObjectURL(previewFallo); }, [previewFallo]);

  const { last, error: gpsError } = useGpsTracking({
    asignacionId,
    conductorId: me?.id ?? 0,
    vehiculoPlaca: me?.vehiculo_placa ?? "",
    enabled: gpsOn && enCurso && !!me,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["asignacion", asignacionId] });
    qc.invalidateQueries({ queryKey: ["mis-asignaciones"] });
    qc.invalidateQueries({ queryKey: ["seguimiento", asg?.orden_id] });
  };

  const iniciar = async () => {
    setBusy("iniciar");
    try {
      await api.patch(`/asignaciones/${asignacionId}/iniciar`);
      toast.success("Entrega iniciada");
      setGpsOn(true);
      refresh();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(null); }
  };

  /** Posición actual (o la última conocida) para adjuntar a la evidencia. */
  const conPosicion = (accion: (lat: number | null, lon: number | null) => void) => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (p) => accion(p.coords.latitude, p.coords.longitude),
        () => accion(last?.lat ?? null, last?.lon ?? null),
        { enableHighAccuracy: true, timeout: 8000 },
      );
    } else accion(last?.lat ?? null, last?.lon ?? null);
  };

  // Confirmación de entrega: se ejecuta SOLO al pulsar "Confirmar entrega" (la foto ya
  // fue elegida y previsualizada — el conductor sabe exactamente qué está enviando).
  const entregarDestino = async (destinoId: number) => {
    if (!receptor.trim()) return toast.error("Indica quién recibió");
    if (!fotoEntrega) return toast.error("Toma la foto de la entrega");
    setBusy(`entregar-${destinoId}`);
    conPosicion(async (lat, lon) => {
      try {
        const fd = new FormData();
        fd.append("receptor", receptor.trim());
        if (lat != null) fd.append("lat", String(lat));
        if (lon != null) fd.append("lon", String(lon));
        fd.append("archivos", fotoEntrega);
        await api.post(`/asignaciones/${asignacionId}/destinos/${destinoId}/entregar`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success("✅ Entrega confirmada: la foto se subió correctamente");
        setEntregando(null);
        setReceptor("");
        setFotoEntrega(null);
        refresh();
      } catch (e) { toast.error(apiError(e)); } finally { setBusy(null); }
    });
  };

  // Confirmación de no entrega: motivo + foto de respaldo obligatoria (incidencia).
  const fallarDestino = async (destinoId: number) => {
    if (!motivoFallo.trim()) return toast.error("Indica el motivo de la no entrega");
    if (!fotoFallo) return toast.error("Toma la foto de respaldo");
    setBusy(`fallar-${destinoId}`);
    conPosicion(async (lat, lon) => {
      try {
        const fd = new FormData();
        fd.append("motivo", motivoFallo.trim());
        if (lat != null) fd.append("lat", String(lat));
        if (lon != null) fd.append("lon", String(lon));
        fd.append("archivos", fotoFallo);
        await api.post(`/asignaciones/${asignacionId}/destinos/${destinoId}/fallar`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success("No entrega registrada con evidencia");
        setFallando(null);
        setMotivoFallo("");
        setFotoFallo(null);
        refresh();
      } catch (e) { toast.error(apiError(e)); } finally { setBusy(null); }
    });
  };

  const reportarIncidencia = async () => {
    setBusy("incidencia");
    try {
      const { data: creada } = await api.post<{ id: number }>("/incidencias/", { asignacion_id: asignacionId, tipo: inc.tipo, notas: inc.notas || null });
      // Evidencia opcional: si el conductor adjuntó una foto, súbela a la incidencia recién creada.
      if (incFile && creada?.id) {
        const fd = new FormData();
        fd.append("tipo", "foto");
        if (inc.notas) fd.append("descripcion", inc.notas);
        fd.append("archivos", incFile);
        await api.post(`/incidencias/${creada.id}/evidencias/upload`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      toast.success("Incidencia reportada");
      setShowInc(false);
      setInc({ tipo: TIPOS_INCIDENCIA[0], notas: "" });
      setIncFile(null);
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(null); }
  };

  if (isLoading || !asg) return <PageLoader />;

  const origen: LatLng | null = seg?.origen.lat != null && seg?.origen.lon != null ? [seg.origen.lat, seg.origen.lon] : null;
  const linea: LatLng[] = (seg?.ruta?.geometria?.coordinates ?? []).map((c: number[]) => [c[1], c[0]] as LatLng);
  const paradasEntrega = (seg?.paradas ?? []).filter((p) => p.destino_id != null).sort((a, b) => a.secuencia - b.secuencia);
  const puntos: LatLng[] = [origen, ...paradasEntrega.filter((p) => p.lat != null).map((p) => [p.lat!, p.lon!] as LatLng), ...linea].filter(Boolean) as LatLng[];
  const pendientes = paradasEntrega.filter((p) => p.estado === "Pendiente").length;

  return (
    <div className="space-y-4 pb-8">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-stone-400 hover:text-stone-200">
        <ArrowLeft className="h-4 w-4" /> Volver
      </button>

      <div className="rounded-2xl border border-stone-700 bg-stone-800 p-4">
        <h1 className="text-lg font-semibold text-stone-100">Run #{asg.id}</h1>
        <p className="mt-1 text-sm text-stone-400">
          {paradasEntrega.length} entrega(s) · {pendientes} pendiente(s)
          {(asg.orden_ids?.length ?? 1) > 1 && ` · ${asg.orden_ids!.length} órdenes`}
        </p>
        {seg && (
          <p className="mt-2 flex items-center gap-1.5 text-sm text-stone-300"><MapPin className="h-4 w-4 text-emerald-400" /> Recojo: {seg.origen.direccion}</p>
        )}
      </div>

      {puntos.length > 0 && (
        <MapView points={puntos} height={300}>
          {linea.length > 1 && <Polyline positions={linea} pathOptions={{ color: COLORS.brand, weight: 4, opacity: 0.8 }} />}
          {origen && <Marker position={origen} icon={pinIcon(COLORS.origen)}><Popup>Recojo</Popup></Marker>}
          {paradasEntrega.map((p) => p.lat != null && (
            <Marker key={p.id} position={[p.lat!, p.lon!]} icon={pinIcon(p.estado === "Visitada" ? COLORS.origen : p.estado === "Omitida" ? "#64748b" : COLORS.destino, String(p.secuencia))}>
              <Popup>{p.direccion} · {p.estado === "Visitada" ? "Entregado" : p.estado === "Omitida" ? "No entregado" : "Pendiente"}</Popup>
            </Marker>
          ))}
        </MapView>
      )}

      {asg.estado === "Asignada" && (
        <Button className="w-full" size="lg" loading={busy === "iniciar"} onClick={iniciar}>
          <Play className="h-5 w-5" /> Iniciar entrega
        </Button>
      )}

      {enCurso && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setGpsOn((v) => !v)}
            className={`flex w-full items-center justify-between rounded-2xl border p-4 ${gpsOn ? "border-emerald-500/50 bg-emerald-500/10" : "border-stone-700 bg-stone-800"}`}
          >
            <span className="flex items-center gap-2 text-stone-100">
              <Radio className={`h-5 w-5 ${gpsOn ? "animate-pulse text-emerald-400" : "text-stone-400"}`} />
              {gpsOn ? "Compartiendo ubicación" : "Compartir mi ubicación"}
            </span>
            {last && <span className="text-xs text-stone-400">{last.lat.toFixed(4)}, {last.lon.toFixed(4)}</span>}
          </button>
          {gpsError && <p className="text-xs text-rose-400">{gpsError}</p>}

          {/* Lista de entregas (destinos) */}
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-200"><Package className="h-4 w-4" /> Entregas</p>
            {paradasEntrega.map((p) => (
              <div key={p.id} className={`rounded-2xl border p-3 ${p.estado === "Visitada" ? "border-emerald-700/40 bg-emerald-900/20" : p.estado === "Omitida" ? "border-stone-600 bg-stone-800/60 opacity-70" : "border-stone-700 bg-stone-800"}`}>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-stone-100">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-stone-700 text-xs font-bold">{p.secuencia}</span>
                    {p.direccion}
                  </span>
                  {p.estado === "Visitada"
                    ? <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="h-5 w-5" /> Entregado</span>
                    : p.estado === "Omitida"
                    ? <span className="flex items-center gap-1 text-xs text-stone-400"><XCircle className="h-5 w-5" /> No entregado</span>
                    : (
                      /* Acción principal prominente y la destructiva apartada: evita
                         toques accidentales en móvil (antes iban pegados con gap-1). */
                      <div className="flex items-center gap-3">
                        <Button size="sm" variant="success" onClick={() => { setEntregando(p.destino_id!); setFallando(null); setReceptor(""); setFotoEntrega(null); }}>
                          <CheckCircle2 className="h-4 w-4" /> Entregar
                        </Button>
                        <span className="h-5 w-px bg-stone-600" aria-hidden />
                        <Button size="sm" variant="ghost" className="text-rose-400" onClick={() => { setFallando(p.destino_id!); setEntregando(null); setMotivoFallo(""); setFotoFallo(null); }}>
                          No entregar
                        </Button>
                      </div>
                    )}
                </div>
                {entregando === p.destino_id && p.estado === "Pendiente" && (
                  <div className="mt-3 space-y-2">
                    <Field label={<span className="text-stone-200">¿Quién recibió?</span>} required>
                      <Input value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre del receptor" />
                    </Field>
                    <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden aria-label="Foto de la entrega"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) setFotoEntrega(f); e.target.value = ""; }} />
                    {!fotoEntrega ? (
                      <Button variant="outline" className="w-full" onClick={() => fileRef.current?.click()}>
                        <Camera className="h-4 w-4" /> Tomar foto de la entrega
                      </Button>
                    ) : (
                      /* Preview: el conductor VE la foto antes de confirmar (certeza de qué sube). */
                      <div className="flex items-center gap-3 rounded-xl border border-stone-600 bg-stone-900/50 p-2">
                        {previewEntrega && <img src={previewEntrega} alt="Foto de la entrega" className="h-16 w-16 rounded-lg object-cover" />}
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" /> Foto lista</p>
                          <p className="truncate text-xs text-stone-400">{fotoEntrega.name}</p>
                        </div>
                        <Button size="sm" variant="ghost" onClick={() => fileRef.current?.click()}>
                          <RefreshCw className="h-3.5 w-3.5" /> Cambiar
                        </Button>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => { setEntregando(null); setFotoEntrega(null); }}>Cancelar</Button>
                      <Button variant="success" className="flex-1" disabled={!fotoEntrega || !receptor.trim()} loading={busy === `entregar-${p.destino_id}`} onClick={() => entregarDestino(p.destino_id!)}>
                        {busy === `entregar-${p.destino_id}` ? "Subiendo foto…" : "Confirmar entrega"}
                      </Button>
                    </div>
                  </div>
                )}
                {fallando === p.destino_id && p.estado === "Pendiente" && (
                  <div className="mt-3 space-y-2">
                    <Field label={<span className="text-stone-200">Motivo de la no entrega</span>} required>
                      <Input value={motivoFallo} onChange={(e) => setMotivoFallo(e.target.value)} placeholder="Cliente ausente, dirección incorrecta…" />
                    </Field>
                    <p className="text-xs text-stone-400">Se registra como incidencia con evidencia: toma una foto de respaldo (ej. puerta cerrada).</p>
                    <input ref={fallarFileRef} type="file" accept="image/*" capture="environment" hidden aria-label="Foto de evidencia de no entrega"
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) setFotoFallo(f); e.target.value = ""; }} />
                    {!fotoFallo ? (
                      <Button variant="outline" className="w-full" onClick={() => fallarFileRef.current?.click()}>
                        <Camera className="h-4 w-4" /> Tomar foto de respaldo
                      </Button>
                    ) : (
                      <div className="flex items-center gap-3 rounded-xl border border-stone-600 bg-stone-900/50 p-2">
                        {previewFallo && <img src={previewFallo} alt="Foto de respaldo" className="h-16 w-16 rounded-lg object-cover" />}
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="h-3.5 w-3.5" /> Foto lista</p>
                          <p className="truncate text-xs text-stone-400">{fotoFallo.name}</p>
                        </div>
                        <Button size="sm" variant="ghost" onClick={() => fallarFileRef.current?.click()}>
                          <RefreshCw className="h-3.5 w-3.5" /> Cambiar
                        </Button>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => { setFallando(null); setFotoFallo(null); }}>Cancelar</Button>
                      <Button variant="danger" className="flex-1" disabled={!fotoFallo || !motivoFallo.trim()} loading={busy === `fallar-${p.destino_id}`} onClick={() => fallarDestino(p.destino_id!)}>
                        {busy === `fallar-${p.destino_id}` ? "Subiendo foto…" : "Confirmar no entrega"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {paradasEntrega.length === 0 && <p className="text-sm text-stone-400">Sin destinos en la ruta.</p>}
          </div>

          <Button variant="outline" className="w-full" onClick={() => setShowInc((v) => !v)}>
            <AlertTriangle className="h-4 w-4" /> Reportar incidencia
          </Button>
          {showInc && (
            <div className="space-y-3 rounded-2xl border border-stone-700 bg-stone-800 p-4">
              <Field label={<span className="text-stone-200">Tipo</span>}>
                <Select value={inc.tipo} onChange={(e) => setInc({ ...inc, tipo: e.target.value })}>
                  {TIPOS_INCIDENCIA.map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label={<span className="text-stone-200">Notas</span>}>
                <Input value={inc.notas} onChange={(e) => setInc({ ...inc, notas: e.target.value })} placeholder="Describe el problema" />
              </Field>
              <Field label={<span className="text-stone-200">Evidencia (opcional)</span>}>
                <input
                  type="file"
                  accept="image/*"
                  aria-label="Adjuntar foto de evidencia"
                  onChange={(e) => setIncFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-stone-300 file:mr-3 file:rounded-lg file:border-0 file:bg-stone-700 file:px-3 file:py-1.5 file:text-stone-100 hover:file:bg-stone-600"
                />
              </Field>
              {incFile && <p className="text-xs text-emerald-400">Foto adjunta: {incFile.name}</p>}
              <p className="text-xs text-stone-400">La gravedad la evalúa la central, no el conductor.</p>
              <Button className="w-full" variant="danger" loading={busy === "incidencia"} onClick={reportarIncidencia}>Reportar</Button>
            </div>
          )}
        </div>
      )}

      {asg.estado === "Finalizada" && (
        <div className="rounded-2xl border border-emerald-700/40 bg-emerald-900/20 p-5 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
          <p className="mt-2 font-semibold text-stone-100">Run completado</p>
        </div>
      )}

      {asg.estado === "Cancelada" && (
        <div className="rounded-2xl border border-stone-600 bg-stone-800/60 p-5 text-center">
          <XCircle className="mx-auto h-12 w-12 text-stone-400" />
          <p className="mt-2 font-semibold text-stone-100">Run cancelado</p>
          <p className="mt-1 text-sm text-stone-400">Esta asignación fue cancelada por la central; no requiere ninguna acción.</p>
        </div>
      )}
    </div>
  );
}
