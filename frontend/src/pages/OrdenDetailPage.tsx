import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Marker, Polygon, Polyline, Popup } from "react-leaflet";
import {
  ArrowLeft, Route as RouteIcon, Gauge, Clock, Flag, Truck, User, Navigation, RefreshCw, TriangleAlert, Camera, MapPin, Plus, Trash2,
} from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useOrden, useSeguimiento, usePings, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import { PageLoader } from "@/components/ui/Feedback";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { Field, Input } from "@/components/ui/Field";
import { MapView, LocationPicker, type LatLng } from "@/components/map/MapView";
import { pinIcon, liveIcon, COLORS } from "@/components/map/icons";
import { formatCoord, formatDate, formatMoney, humanDuration, timeAgo, pointInPolygon } from "@/lib/utils";
import { fetchRoadRoute } from "@/lib/routing";

export default function OrdenDetailPage() {
  const { id } = useParams();
  const ordenId = Number(id);
  const navigate = useNavigate();
  const { can } = useAuth();
  const { data: orden, isLoading } = useOrden(ordenId);
  const { data: seg, refetch, isFetching } = useSeguimiento(ordenId, 8000);
  const { data: pings } = usePings(seg?.asignacion?.id, { limit: 500 });

  // Geometría real por calles: preferimos la que el backend ya guardó (autónoma);
  // si no existe, la pedimos a OSRM desde el navegador como respaldo.
  const geomCoords = seg?.ruta?.geometria?.coordinates;
  const roadFromDb: LatLng[] | null =
    geomCoords && geomCoords.length > 1 ? geomCoords.map((c) => [c[1], c[0]] as LatLng) : null;

  const oLat = seg?.origen?.lat ?? null;
  const oLon = seg?.origen?.lon ?? null;
  const dLat = seg?.destino?.lat ?? null;
  const dLon = seg?.destino?.lon ?? null;
  const { data: roadFetched } = useQuery({
    queryKey: ["road-route", oLat, oLon, dLat, dLon],
    queryFn: () => fetchRoadRoute([oLat!, oLon!], [dLat!, dLon!]),
    enabled: !roadFromDb && oLat != null && oLon != null && dLat != null && dLon != null,
    staleTime: Infinity,
  });
  const roadRoute = roadFromDb ?? roadFetched ?? null;

  const planificar = useApiMutation(
    () => api.post("/rutas/planificar", { orden_id: ordenId, generar_geocerca: true, tolerancia_metros: 60 }),
    [],
  );
  const optimizar = useApiMutation(
    (rutaId: number) => api.post(`/rutas/${rutaId}/optimizar`),
    [],
  );
  const qc = useQueryClient();
  const delDestino = useApiMutation((destinoId: number) => api.delete(`/ordenes/${ordenId}/destinos/${destinoId}`), []);
  const [addDest, setAddDest] = useState(false);
  const refreshOrden = () => { qc.invalidateQueries({ queryKey: ["orden", ordenId] }); refetch(); };

  if (isLoading || !orden) return <PageLoader />;

  const editable = (orden.estado === "Pendiente de Pago" || orden.estado === "Pendiente") && can("ordenes", "write");

  // Una orden entregada o cancelada ya no se (re)planifica.
  const terminal = orden.estado === "Entregado" || orden.estado === "Cancelado";

  const origen = seg?.origen;
  const destino = seg?.destino;
  const pos = seg?.posicion_actual;
  const paradas = seg?.paradas ?? [];

  const points: LatLng[] = [];
  if (origen?.lat != null) points.push([origen.lat, origen.lon!]);
  if (destino?.lat != null) points.push([destino.lat, destino.lon!]);
  if (pos) points.push([pos.lat, pos.lon]);
  paradas.forEach((p) => p.lat != null && points.push([p.lat, p.lon!]));

  const geocercaPolys = (seg?.geocercas ?? [])
    .filter((g) => g.geometry?.type === "Polygon")
    .map((g) => (g.geometry.coordinates as number[][][])[0]?.map((c) => [c[1], c[0]] as LatLng) ?? []);

  const routeLine: LatLng[] =
    origen?.lat != null && destino?.lat != null ? [[origen.lat, origen.lon!], [destino.lat, destino.lon!]] : [];

  // Recorrido real del conductor (pings en orden cronológico)
  const trail: LatLng[] = (pings ?? [])
    .slice()
    .reverse()
    .map((p) => [p.location.coordinates[1], p.location.coordinates[0]] as LatLng);
  trail.forEach((t) => points.push(t));

  // Alerta de salida de geocerca: posición en vivo fuera de todos los corredores activos
  const fueraDeRuta =
    !!pos &&
    geocercaPolys.length > 0 &&
    !geocercaPolys.some((poly) => poly.length >= 3 && pointInPolygon([pos.lat, pos.lon], poly));

  const doPlanificar = () =>
    planificar.mutate(undefined, {
      onSuccess: () => { toast.success("Ruta planificada"); refetch(); },
      onError: (e) => toast.error(apiError(e)),
    });

  const entregas = seg?.entregas ?? [];
  const abrirArchivo = async (fileId: string) => {
    try {
      const res = await api.get(`/asignaciones/prueba-entrega/archivos/${fileId}`, { responseType: "blob" });
      window.open(URL.createObjectURL(res.data as Blob), "_blank");
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/ordenes")}><ArrowLeft className="h-5 w-5" /></Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">Orden #{orden.id}</h1>
              <StatusBadge kind="orden" value={orden.estado} />
            </div>
            <p className="text-sm text-slate-500">Creada {formatDate(orden.fecha_creacion)} · {formatMoney(orden.total)}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()} loading={isFetching}>
            <RefreshCw className="h-4 w-4" /> Actualizar
          </Button>
          {can("rutas", "write") && !terminal && (
            <Button onClick={doPlanificar} loading={planificar.isPending}>
              <RouteIcon className="h-4 w-4" /> {seg?.ruta ? "Replanificar ruta" : "Planificar ruta"}
            </Button>
          )}
          {can("rutas", "write") && !terminal && seg?.ruta && (seg.paradas?.length ?? 0) > 2 && (
            <Button
              variant="outline"
              loading={optimizar.isPending}
              onClick={() =>
                optimizar.mutate(seg.ruta!.id, {
                  onSuccess: () => { toast.success("Ruta optimizada"); refetch(); },
                  onError: (e) => toast.error(apiError(e)),
                })
              }
            >
              <RouteIcon className="h-4 w-4" /> Optimizar
            </Button>
          )}
        </div>
      </div>

      {fueraDeRuta && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <TriangleAlert className="h-5 w-5 shrink-0" />
          <span><strong>Fuera de ruta:</strong> la posición del conductor está fuera de las geocercas activas de esta orden.</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Mapa */}
        <div className="lg:col-span-2">
          <Card className="overflow-hidden">
            <CardHeader
              title="Mapa de seguimiento"
              subtitle={pos ? `Última posición ${timeAgo(pos.timestamp)}` : "Sin posición GPS reciente"}
              action={pos && <Badge tone="indigo"><Navigation className="h-3 w-3" /> En vivo</Badge>}
            />
            <MapView points={points} height={460}>
              {geocercaPolys.map((poly, i) =>
                poly.length > 0 ? (
                  <Polygon key={i} positions={poly} pathOptions={{ color: "#6366f1", weight: 1.5, fillOpacity: 0.08 }} />
                ) : null,
              )}
              {roadRoute && roadRoute.length > 1 ? (
                <Polyline positions={roadRoute} pathOptions={{ color: "#0d9488", weight: 4, opacity: 0.9 }} />
              ) : routeLine.length === 2 ? (
                <Polyline positions={routeLine} pathOptions={{ color: "#0d9488", weight: 3, dashArray: "6 8", opacity: 0.4 }} />
              ) : null}
              {trail.length > 1 && (
                <Polyline positions={trail} pathOptions={{ color: "#d97706", weight: 4, opacity: 0.9 }} />
              )}
              {origen?.lat != null && (
                <Marker position={[origen.lat, origen.lon!]} icon={pinIcon(COLORS.origen)}>
                  <Popup>Origen: {origen.direccion}</Popup>
                </Marker>
              )}
              {destino?.lat != null && (
                <Marker position={[destino.lat, destino.lon!]} icon={pinIcon(COLORS.destino)}>
                  <Popup>Destino: {destino.direccion}</Popup>
                </Marker>
              )}
              {paradas.map((p) =>
                p.lat != null ? (
                  <Marker key={p.id} position={[p.lat, p.lon!]} icon={pinIcon(p.estado === "Visitada" ? COLORS.origen : p.estado === "Omitida" ? "#64748b" : COLORS.parada, String(p.secuencia))}>
                    <Popup>{p.direccion} · {p.estado === "Visitada" ? "Entregado" : p.estado === "Omitida" ? "No entregado" : "Pendiente"}</Popup>
                  </Marker>
                ) : null,
              )}
              {pos && (
                <Marker position={[pos.lat, pos.lon]} icon={liveIcon()}>
                  <Popup>
                    Conductor · {pos.speed_kmh != null ? `${pos.speed_kmh.toFixed(0)} km/h` : "—"}
                    <br />
                    {timeAgo(pos.timestamp)}
                  </Popup>
                </Marker>
              )}
            </MapView>
            <div className="flex flex-wrap items-center gap-4 border-t border-sillar-100 px-5 py-3 text-xs text-stone-500">
              <LegendItem color="#0d9488" label="Ruta por calles" />
              <LegendItem color="#d97706" label="Recorrido GPS" />
              <LegendItem color="#10b981" label="Origen" dot />
              <LegendItem color="#f43f5e" label="Destino" dot />
            </div>
          </Card>

          {seg?.estadisticas && (seg.estadisticas.pings ?? 0) > 0 && (
            <div className="mt-4 grid grid-cols-3 gap-4">
              <MiniStat icon={<Gauge className="h-4 w-4" />} label="Distancia GPS" value={`${(seg.estadisticas.distancia_total_km ?? 0).toFixed(2)} km`} />
              <MiniStat icon={<Clock className="h-4 w-4" />} label="Duración" value={humanDuration(seg.estadisticas.duracion_segundos)} />
              <MiniStat icon={<Navigation className="h-4 w-4" />} label="Vel. promedio" value={`${(seg.estadisticas.velocidad_promedio_kmh ?? 0).toFixed(0)} km/h`} />
            </div>
          )}
        </div>

        {/* Panel lateral */}
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Trayecto"
              subtitle={`Recojo · ${(orden.destinos?.length ?? 1)} destino(s)`}
              action={editable && <Button size="sm" variant="outline" onClick={() => setAddDest(true)}><Plus className="h-3.5 w-3.5" /> Destino</Button>}
            />
            <CardBody className="space-y-3">
              <PointRow color="bg-emerald-500" label="Origen" dir={origen?.direccion ?? orden.direccion_origen} sub={origen?.distrito} coord={formatCoord(origen?.lat ?? orden.lat_origen, origen?.lon ?? orden.lon_origen)} />
              {(orden.destinos ?? []).map((d) => (
                <div key={d.id} className="flex gap-3">
                  <div className="mt-1 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-rose-500 text-[8px] font-bold text-white ring-4 ring-slate-100">{d.secuencia}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-slate-800">{d.direccion}</p>
                      <div className="flex items-center gap-1.5">
                        <StatusBadge kind="parada" value={d.estado === "Entregado" ? "Visitada" : d.estado === "Fallida" ? "Omitida" : "Pendiente"} />
                        {editable && (orden.destinos?.length ?? 1) > 1 && (
                          <button onClick={() => delDestino.mutate(d.id, { onSuccess: () => { toast.success("Destino eliminado"); refreshOrden(); }, onError: (e) => toast.error(apiError(e)) })} className="text-slate-300 hover:text-rose-500"><Trash2 className="h-3.5 w-3.5" /></button>
                        )}
                      </div>
                    </div>
                    {d.nombre_destinatario && <p className="text-xs text-slate-500">Para: {d.nombre_destinatario}</p>}
                    <p className="text-xs text-slate-400">
                      {d.subtotal != null && `${formatMoney(d.subtotal)} · `}
                      {d.estado === "Entregado" && d.entrega_receptor ? `Recibió ${d.entrega_receptor}` : d.estado === "Fallida" ? (d.nota || "No entregado") : "Pendiente"}
                    </p>
                  </div>
                </div>
              ))}
            </CardBody>
          </Card>

          {orden.ajuste_monto != null && (
            <Card>
              <CardHeader title="Precio" />
              <CardBody className="space-y-1 text-sm">
                <div className="flex justify-between text-slate-500"><span>Base</span><span>{formatMoney(Number(orden.total ?? 0) - Number(orden.ajuste_monto))}</span></div>
                <div className="flex justify-between text-slate-500"><span>Ajuste{orden.ajuste_por ? ` · usuario #${orden.ajuste_por}` : ""}</span><span className={Number(orden.ajuste_monto) < 0 ? "text-emerald-600" : "text-rose-600"}>{Number(orden.ajuste_monto) >= 0 ? "+" : ""}{formatMoney(orden.ajuste_monto)}</span></div>
                <div className="flex justify-between border-t border-slate-100 pt-1 font-semibold text-slate-800"><span>Total</span><span>{formatMoney(orden.total)}</span></div>
                {orden.ajuste_motivo && <p className="pt-1 text-xs text-slate-400">Motivo: {orden.ajuste_motivo}</p>}
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader title="Asignación" />
            <CardBody>
              {seg?.asignacion ? (
                <div className="space-y-2 text-sm">
                  <Row icon={<User className="h-4 w-4" />} label="Conductor" value={seg.asignacion.conductor_nombre ?? `#${seg.asignacion.conductor_id}`} />
                  <Row icon={<Truck className="h-4 w-4" />} label="Vehículo" value={seg.asignacion.vehiculo_placa ?? "—"} />
                  <Row icon={<Flag className="h-4 w-4" />} label="Estado" value={<StatusBadge kind="asignacion" value={seg.asignacion.estado} />} />
                  {seg.asignacion.fecha_inicio && <Row icon={<Clock className="h-4 w-4" />} label="Inicio" value={formatDate(seg.asignacion.fecha_inicio)} />}
                </div>
              ) : (
                <p className="text-sm text-slate-400">Esta orden aún no tiene conductor asignado.</p>
              )}
            </CardBody>
          </Card>

          {entregas.length > 0 && (
            <Card>
              <CardHeader title="Evidencia de entrega" subtitle="Prueba capturada por el conductor al entregar" />
              <CardBody className="space-y-4">
                {entregas.map((ev) => (
                  <div key={ev.id} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1.5 font-medium text-slate-700"><User className="h-4 w-4" /> {ev.receptor || "Receptor no indicado"}</span>
                      <span className="text-xs text-slate-400">{timeAgo(ev.timestamp)}</span>
                    </div>
                    {(ev.lat != null && ev.lon != null) && (
                      <p className="flex items-center gap-1.5 font-mono text-xs text-slate-400"><MapPin className="h-3.5 w-3.5" /> {formatCoord(ev.lat, ev.lon)}</p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {ev.archivos.map((a) => (
                        <button key={a.file_id} onClick={() => abrirArchivo(a.file_id)} className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 hover:bg-slate-200">
                          <Camera className="h-3.5 w-3.5 text-slate-400" /> Ver {a.filename}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </CardBody>
            </Card>
          )}

          {seg?.ruta && (
            <Card>
              <CardHeader title="Ruta planificada" subtitle={`${(seg.ruta.distancia_km ?? 0).toFixed(1)} km · ${humanDuration(seg.ruta.tiempo_estimado_segundos)}`} />
              <CardBody className="space-y-3">
                {paradas.length === 0 && <p className="text-sm text-slate-400">Sin paradas registradas.</p>}
                {paradas.map((p) => (
                  <div key={p.id} className="flex items-center gap-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-50 text-xs font-bold text-indigo-600">{p.secuencia}</div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-700">{p.direccion}</p>
                      <p className="text-xs text-slate-400">{p.fecha_paso ? `Visitada ${timeAgo(p.fecha_paso)}` : "Pendiente"}</p>
                    </div>
                    <StatusBadge kind="parada" value={p.estado} />
                  </div>
                ))}
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      {addDest && <AddDestinoModal ordenId={ordenId} onClose={() => setAddDest(false)} onDone={refreshOrden} />}
    </div>
  );
}

function AddDestinoModal({ ordenId, onClose, onDone }: { ordenId: number; onClose: () => void; onDone: () => void }) {
  const [direccion, setDireccion] = useState("");
  const [nombre, setNombre] = useState("");
  const [punto, setPunto] = useState<LatLng | null>(null);
  const [peso, setPeso] = useState("");
  const m = useApiMutation((body: any) => api.post(`/ordenes/${ordenId}/destinos`, body), []);
  const submit = () => {
    if (!direccion) return toast.error("Indica la dirección del destino");
    if (!punto) return toast.error("Fija el punto en el mapa");
    m.mutate(
      { direccion, nombre_destinatario: nombre || null, lat: punto[0], lon: punto[1], peso_kg: peso ? Number(peso) : null },
      { onSuccess: () => { toast.success("Destino agregado"); onDone(); onClose(); }, onError: (e) => toast.error(apiError(e)) },
    );
  };
  return (
    <Modal open onClose={onClose} title="Agregar destino" description="Recalcula el precio y la ruta de la orden."
      footer={<><Button variant="outline" onClick={onClose}>Cancelar</Button><Button loading={m.isPending} onClick={submit}>Agregar</Button></>}>
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Dirección" required><Input value={direccion} onChange={(e) => setDireccion(e.target.value)} /></Field>
          <Field label="Destinatario"><Input value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field>
        </div>
        <Field label="Peso (kg)"><Input type="number" value={peso} onChange={(e) => setPeso(e.target.value)} className="w-32" /></Field>
        <LocationPicker value={punto} onChange={setPunto} height={220} color="#f43f5e" />
      </div>
    </Modal>
  );
}

function LegendItem({ color, label, dot }: { color: string; label: string; dot?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={dot ? "h-2.5 w-2.5 rounded-full" : "h-1 w-5 rounded-full"}
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function MiniStat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600">{icon}</div>
      <div>
        <p className="text-sm font-bold text-slate-900">{value}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}

function PointRow({ color, label, dir, sub, coord }: { color: string; label: string; dir: string; sub?: string | null; coord: string }) {
  return (
    <div className="flex gap-3">
      <div className={`mt-1 h-3.5 w-3.5 shrink-0 rounded-full ring-4 ring-slate-100 ${color}`} />
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
        <p className="text-sm font-medium text-slate-800">{dir}</p>
        {sub && <p className="text-xs text-slate-500">{sub}</p>}
        <p className="mt-0.5 font-mono text-xs text-slate-400">{coord}</p>
      </div>
    </div>
  );
}

function Row({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-slate-500">{icon} {label}</span>
      <span className="font-medium text-slate-800">{value}</span>
    </div>
  );
}
