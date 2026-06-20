import { useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Marker, Polyline, Popup } from "react-leaflet";
import { ArrowLeft, Play, Flag, Camera, AlertTriangle, MapPin, Radio, CheckCircle2, XCircle, Package } from "lucide-react";
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
  const [busy, setBusy] = useState(false);
  const [inc, setInc] = useState({ tipo: TIPOS_INCIDENCIA[0], notas: "" });
  // Entrega por destino: id del destino en curso + receptor.
  const [entregando, setEntregando] = useState<number | null>(null);
  const [receptor, setReceptor] = useState("");
  // No entrega: id del destino + motivo.
  const [fallando, setFallando] = useState<number | null>(null);
  const [motivoFallo, setMotivoFallo] = useState("");

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
    setBusy(true);
    try {
      await api.patch(`/asignaciones/${asignacionId}/iniciar`);
      toast.success("Entrega iniciada");
      setGpsOn(true);
      refresh();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  // Entrega de un destino: sube la foto (obligatoria) + receptor y marca el destino.
  const entregarDestino = async (destinoId: number, file: File) => {
    if (!receptor.trim()) return toast.error("Indica quién recibió");
    setBusy(true);
    const done = async (lat: number | null, lon: number | null) => {
      try {
        const fd = new FormData();
        fd.append("receptor", receptor.trim());
        if (lat != null) fd.append("lat", String(lat));
        if (lon != null) fd.append("lon", String(lon));
        fd.append("archivos", file);
        await api.post(`/asignaciones/${asignacionId}/destinos/${destinoId}/entregar`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        toast.success("Destino entregado");
        setEntregando(null);
        setReceptor("");
        refresh();
      } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
    };
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (p) => done(p.coords.latitude, p.coords.longitude),
        () => done(last?.lat ?? null, last?.lon ?? null),
        { enableHighAccuracy: true, timeout: 8000 },
      );
    } else done(last?.lat ?? null, last?.lon ?? null);
  };

  const fallarDestino = async (destinoId: number) => {
    if (!motivoFallo.trim()) return toast.error("Indica el motivo de la no entrega");
    setBusy(true);
    try {
      await api.post(`/asignaciones/${asignacionId}/destinos/${destinoId}/fallar`, { motivo: motivoFallo.trim() });
      toast.success("Destino marcado como no entregado");
      setFallando(null);
      setMotivoFallo("");
      refresh();
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const reportarIncidencia = async () => {
    setBusy(true);
    try {
      await api.post("/incidencias/", { asignacion_id: asignacionId, tipo: inc.tipo, notas: inc.notas || null });
      toast.success("Incidencia reportada");
      setShowInc(false);
      setInc({ tipo: TIPOS_INCIDENCIA[0], notas: "" });
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
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
        <Button className="w-full" size="lg" loading={busy} onClick={iniciar}>
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
                      <div className="flex gap-1">
                        <Button size="sm" variant="outline" onClick={() => { setEntregando(p.destino_id!); setFallando(null); setReceptor(""); }}>Entregar</Button>
                        <Button size="sm" variant="ghost" className="text-rose-400" onClick={() => { setFallando(p.destino_id!); setEntregando(null); setMotivoFallo(""); }}>No entregar</Button>
                      </div>
                    )}
                </div>
                {entregando === p.destino_id && p.estado === "Pendiente" && (
                  <div className="mt-3 space-y-2">
                    <Field label={<span className="text-stone-200">¿Quién recibió?</span>} required>
                      <Input value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre del receptor" />
                    </Field>
                    <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden
                      onChange={(e) => e.target.files?.[0] && entregarDestino(p.destino_id!, e.target.files[0])} />
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => setEntregando(null)}>Cancelar</Button>
                      <Button variant="success" className="flex-1" loading={busy} onClick={() => fileRef.current?.click()}>
                        <Camera className="h-4 w-4" /> Foto y entregar
                      </Button>
                    </div>
                  </div>
                )}
                {fallando === p.destino_id && p.estado === "Pendiente" && (
                  <div className="mt-3 space-y-2">
                    <Field label={<span className="text-stone-200">Motivo de la no entrega</span>} required>
                      <Input value={motivoFallo} onChange={(e) => setMotivoFallo(e.target.value)} placeholder="Cliente ausente, dirección incorrecta…" />
                    </Field>
                    <div className="flex gap-2">
                      <Button variant="outline" className="flex-1" onClick={() => setFallando(null)}>Cancelar</Button>
                      <Button variant="danger" className="flex-1" loading={busy} onClick={() => fallarDestino(p.destino_id!)}>Confirmar no entrega</Button>
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
              <p className="text-xs text-stone-400">La gravedad la evalúa la central, no el conductor.</p>
              <Button className="w-full" variant="danger" loading={busy} onClick={reportarIncidencia}>Reportar</Button>
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
    </div>
  );
}
