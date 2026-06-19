import { useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Marker, Polyline, Popup } from "react-leaflet";
import { ArrowLeft, Play, Flag, Camera, AlertTriangle, MapPin, Radio, CheckCircle2 } from "lucide-react";
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
  const [receptor, setReceptor] = useState("");
  const [showFin, setShowFin] = useState(false);
  const [showInc, setShowInc] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pruebaSubida, setPruebaSubida] = useState(false);
  const [inc, setInc] = useState({ tipo: TIPOS_INCIDENCIA[0], notas: "" });

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

  const subirPrueba = async (file: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("tipo", "foto");
      if (last) { fd.append("lat", String(last.lat)); fd.append("lon", String(last.lon)); }
      fd.append("archivos", file);
      await api.post(`/asignaciones/${asignacionId}/prueba-entrega`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setPruebaSubida(true);
      toast.success("Prueba de entrega subida");
    } catch (e) { toast.error(apiError(e)); } finally { setBusy(false); }
  };

  const finalizar = () => {
    if (!receptor.trim()) return toast.error("Indica quién recibió la entrega");
    if (!pruebaSubida) return toast.error("Sube la prueba de entrega (foto) antes de finalizar");
    setBusy(true);
    const done = async (lat: number | null, lon: number | null) => {
      try {
        await api.patch(`/asignaciones/${asignacionId}/finalizar`, { receptor: receptor || null, lat, lon });
        toast.success("¡Entrega completada!");
        refresh();
        navigate("/");
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
  const destino: LatLng | null = seg?.destino.lat != null && seg?.destino.lon != null ? [seg.destino.lat, seg.destino.lon] : null;
  const linea: LatLng[] = (seg?.ruta?.geometria?.coordinates ?? []).map((c: number[]) => [c[1], c[0]] as LatLng);
  const puntos: LatLng[] = [origen, destino, ...linea].filter(Boolean) as LatLng[];

  return (
    <div className="space-y-4 pb-8">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-stone-400 hover:text-stone-200">
        <ArrowLeft className="h-4 w-4" /> Volver
      </button>

      <div className="rounded-2xl border border-stone-700 bg-stone-800 p-4">
        <h1 className="text-lg font-semibold text-stone-100">Pedido #{asg.orden_id}</h1>
        {seg && (
          <div className="mt-2 space-y-1 text-sm text-stone-300">
            <p className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-emerald-400" /> {seg.origen.direccion}</p>
            <p className="flex items-center gap-1.5"><Flag className="h-4 w-4 text-rose-400" /> {seg.destino.direccion}</p>
          </div>
        )}
      </div>

      {puntos.length > 0 && (
        <MapView points={puntos} height={300}>
          {linea.length > 1 && <Polyline positions={linea} pathOptions={{ color: COLORS.brand, weight: 4, opacity: 0.8 }} />}
          {origen && <Marker position={origen} icon={pinIcon(COLORS.origen)}><Popup>Recojo</Popup></Marker>}
          {destino && <Marker position={destino} icon={pinIcon(COLORS.destino)}><Popup>Entrega</Popup></Marker>}
        </MapView>
      )}

      {/* Acciones según estado */}
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

          <div className="grid grid-cols-2 gap-2">
            <Button variant={pruebaSubida ? "success" : "outline"} loading={busy} onClick={() => fileRef.current?.click()}>
              <Camera className="h-4 w-4" /> {pruebaSubida ? "Prueba subida ✓" : "Prueba de entrega"}
            </Button>
            <Button variant="outline" onClick={() => setShowInc((v) => !v)}>
              <AlertTriangle className="h-4 w-4" /> Incidencia
            </Button>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => e.target.files?.[0] && subirPrueba(e.target.files[0])}
          />

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

          {!showFin ? (
            <Button className="w-full" size="lg" variant="success" onClick={() => setShowFin(true)}>
              <CheckCircle2 className="h-5 w-5" /> Finalizar entrega
            </Button>
          ) : (
            <div className="space-y-3 rounded-2xl border border-emerald-700/40 bg-emerald-900/20 p-4">
              <Field label={<span className="text-stone-200">¿Quién recibió?</span>} required>
                <Input value={receptor} onChange={(e) => setReceptor(e.target.value)} placeholder="Nombre del receptor" />
              </Field>
              {!pruebaSubida && (
                <p className="text-xs text-amber-400">Falta subir la foto de prueba de entrega.</p>
              )}
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setShowFin(false)}>Cancelar</Button>
                <Button variant="success" className="flex-1" loading={busy} onClick={finalizar}>Confirmar entrega</Button>
              </div>
            </div>
          )}
        </div>
      )}

      {asg.estado === "Finalizada" && (
        <div className="rounded-2xl border border-emerald-700/40 bg-emerald-900/20 p-5 text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-400" />
          <p className="mt-2 font-semibold text-stone-100">Entrega completada</p>
          {asg.entrega_receptor && <p className="text-sm text-stone-400">Recibió: {asg.entrega_receptor}</p>}
        </div>
      )}
    </div>
  );
}
