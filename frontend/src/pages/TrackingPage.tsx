import { Fragment, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Circle, Marker, Polyline, Popup } from "react-leaflet";
import { Navigation, Gauge, Crosshair, Search, Truck, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/Feedback";
import { MapView, type LatLng } from "@/components/map/MapView";
import { pinIcon, liveIcon } from "@/components/map/icons";
import { formatNumber, timeAgo } from "@/lib/utils";

interface FlotaRun {
  asignacion_id: number;
  orden_id: number;
  orden_ids: number[];
  conductor_id: number;
  conductor_nombre?: string | null;
  vehiculo_placa: string;
  fecha_inicio?: string | null;
  posicion?: { lon: number; lat: number; speed_kmh?: number | null; timestamp: string } | null;
  ruta_geometria?: { type: string; coordinates: [number, number][] } | null;
}

interface NearDriver {
  conductor_id: number;
  asignacion_id: number;
  vehiculo_placa: string;
  location: { coordinates: [number, number] };
  speed_kmh?: number | null;
  timestamp: string;
  distance_m: number;
}

// Colores rotativos para distinguir las rutas de cada run activo.
const RUN_COLORS = ["#0d9488", "#6366f1", "#d97706", "#e11d48", "#0ea5e9", "#84cc16"];

export default function TrackingPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"flota" | "radio">("flota");

  // Flota activa: cada run EnCurso con su última posición y la geometría de la ruta.
  const { data: flota, isFetching: fetchingFlota } = useQuery({
    queryKey: ["tracking-flota"],
    queryFn: () => api.get<FlotaRun[]>("/tracking/flota").then((r) => r.data),
    refetchInterval: 10000,
  });
  const runs = flota ?? [];

  // Herramienta secundaria: conductores con ping reciente alrededor de un punto ($geoNear).
  const [point, setPoint] = useState<LatLng>([-16.409, -71.5375]);
  const [radio, setRadio] = useState(5000);
  const [ventana, setVentana] = useState(15);
  const { data: near, isFetching: fetchingNear } = useQuery({
    queryKey: ["conductores-cerca", point, radio, ventana],
    queryFn: () =>
      api
        .get<NearDriver[]>("/tracking/conductores-cerca", {
          params: { lon: point[1], lat: point[0], radio_m: radio, ventana_min: ventana },
        })
        .then((r) => r.data),
    refetchInterval: 10000,
    enabled: tab === "radio",
  });
  const drivers = near ?? [];

  // Puntos para encuadrar el mapa: posiciones + rutas (flota) o punto+conductores (radio).
  const points: LatLng[] = [];
  if (tab === "flota") {
    runs.forEach((r) => {
      if (r.posicion) points.push([r.posicion.lat, r.posicion.lon]);
      r.ruta_geometria?.coordinates?.forEach((c) => points.push([c[1], c[0]]));
    });
  } else {
    points.push(point);
    drivers.forEach((d) => points.push([d.location.coordinates[1], d.location.coordinates[0]]));
  }

  return (
    <div>
      <PageHeader
        title="Tracking en vivo"
        subtitle="Entregas en curso sobre el mapa, con su ruta y última posición GPS"
        actions={
          <div className="flex rounded-lg bg-slate-100 p-0.5">
            <Button size="sm" variant={tab === "flota" ? "primary" : "ghost"} onClick={() => setTab("flota")}>
              <Truck className="h-3.5 w-3.5" /> Flota activa
            </Button>
            <Button size="sm" variant={tab === "radio" ? "primary" : "ghost"} onClick={() => setTab("radio")}>
              <Crosshair className="h-3.5 w-3.5" /> Buscar por radio
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="overflow-hidden">
            <CardHeader
              title="Mapa operativo"
              subtitle={tab === "flota" ? "Rutas y posiciones de las entregas en curso (se actualiza solo)" : "Haz clic en el mapa para mover el punto de búsqueda"}
              action={
                tab === "flota" ? (
                  fetchingFlota ? <Badge tone="blue">Actualizando…</Badge> : <Badge tone="green">{runs.length} en curso</Badge>
                ) : fetchingNear ? <Badge tone="blue">Buscando…</Badge> : <Badge tone="green">{drivers.length} en rango</Badge>
              }
            />
            <MapView points={points} height={460} onClick={tab === "radio" ? setPoint : undefined}>
              {tab === "flota" ? (
                <>
                  {runs.map((r, i) => {
                    const color = RUN_COLORS[i % RUN_COLORS.length];
                    const ruta: LatLng[] = (r.ruta_geometria?.coordinates ?? []).map((c) => [c[1], c[0]] as LatLng);
                    return (
                      <Fragment key={r.asignacion_id}>
                        {ruta.length > 1 && <Polyline positions={ruta} pathOptions={{ color, weight: 4, opacity: 0.75 }} />}
                        {r.posicion && (
                          <Marker position={[r.posicion.lat, r.posicion.lon]} icon={liveIcon(color)}>
                            <Popup>
                              <strong>{r.conductor_nombre ?? `Conductor #${r.conductor_id}`}</strong> · {r.vehiculo_placa}
                              <br />
                              Orden #{r.orden_id}
                              {r.orden_ids.length > 1 ? ` (+${r.orden_ids.length - 1})` : ""} ·{" "}
                              {r.posicion.speed_kmh != null ? `${r.posicion.speed_kmh.toFixed(0)} km/h` : "—"}
                              <br />
                              {timeAgo(r.posicion.timestamp)}
                            </Popup>
                          </Marker>
                        )}
                      </Fragment>
                    );
                  })}
                </>
              ) : (
                <>
                  <Marker position={point} icon={pinIcon("#0d9488")}>
                    <Popup>Punto de búsqueda</Popup>
                  </Marker>
                  <Circle center={point} radius={radio} pathOptions={{ color: "#0d9488", weight: 1, fillOpacity: 0.05 }} />
                  {drivers.map((d) => (
                    <Marker
                      key={d.conductor_id}
                      position={[d.location.coordinates[1], d.location.coordinates[0]]}
                      icon={liveIcon()}
                    >
                      <Popup>
                        Conductor #{d.conductor_id} · {d.vehiculo_placa}
                        <br />
                        {formatNumber(d.distance_m)} m · {timeAgo(d.timestamp)}
                      </Popup>
                    </Marker>
                  ))}
                </>
              )}
            </MapView>
          </Card>
        </div>

        <div className="space-y-6">
          {tab === "flota" ? (
            <Card>
              <CardHeader title="Entregas en curso" subtitle="Toca una para abrir su seguimiento" />
              {runs.length === 0 ? (
                <EmptyState
                  icon={<Truck className="h-7 w-7" />}
                  title="No hay entregas en curso"
                  description="Cuando un conductor inicie un run, su ruta y posición aparecerán aquí automáticamente."
                />
              ) : (
                <div className="divide-y divide-slate-100">
                  {runs.map((r, i) => (
                    <button
                      key={r.asignacion_id}
                      onClick={() => navigate(`/ordenes/${r.orden_id}`)}
                      className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="flex h-9 w-9 items-center justify-center rounded-lg text-white"
                          style={{ backgroundColor: RUN_COLORS[i % RUN_COLORS.length] }}
                        >
                          <Navigation className="h-4 w-4" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-800">
                            {r.conductor_nombre ?? `Conductor #${r.conductor_id}`}
                          </p>
                          <p className="text-xs text-slate-500">
                            {r.vehiculo_placa} · Orden #{r.orden_id}
                            {r.orden_ids.length > 1 ? ` +${r.orden_ids.length - 1}` : ""}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        {r.posicion ? (
                          <>
                            <p className="flex items-center justify-end gap-1 text-xs text-slate-500">
                              <Gauge className="h-3 w-3" /> {r.posicion.speed_kmh != null ? `${r.posicion.speed_kmh.toFixed(0)} km/h` : "—"}
                            </p>
                            <p className="text-xs text-slate-400">{timeAgo(r.posicion.timestamp)}</p>
                          </>
                        ) : (
                          <p className="text-xs text-slate-400">Sin GPS aún</p>
                        )}
                      </div>
                      <ExternalLink className="h-4 w-4 shrink-0 text-slate-300" />
                    </button>
                  ))}
                </div>
              )}
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader title="Parámetros de búsqueda" />
                <CardBody className="space-y-4">
                  <Field label="Latitud"><Input type="number" value={point[0]} onChange={(e) => setPoint([Number(e.target.value), point[1]])} /></Field>
                  <Field label="Longitud"><Input type="number" value={point[1]} onChange={(e) => setPoint([point[0], Number(e.target.value)])} /></Field>
                  <Field label={`Radio: ${formatNumber(radio)} m`}>
                    <input type="range" min={500} max={50000} step={500} value={radio} onChange={(e) => setRadio(Number(e.target.value))} className="w-full accent-brand-600" />
                  </Field>
                  <Field label={`Ventana: últimos ${ventana} min`}>
                    <input type="range" min={1} max={60} value={ventana} onChange={(e) => setVentana(Number(e.target.value))} className="w-full accent-brand-600" />
                  </Field>
                  <p className="flex items-center gap-1.5 text-xs text-slate-400"><Crosshair className="h-3.5 w-3.5" /> Usa $geoNear sobre los pings GPS.</p>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Conductores cercanos" />
                {drivers.length === 0 ? (
                  <EmptyState icon={<Search className="h-7 w-7" />} title="Sin conductores en rango" description="Amplía el radio o la ventana de tiempo, o envía pings GPS." />
                ) : (
                  <div className="divide-y divide-slate-100">
                    {drivers.map((d) => (
                      <div key={d.conductor_id} className="flex items-center justify-between gap-3 px-5 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
                            <Navigation className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-800">Conductor #{d.conductor_id}</p>
                            <p className="text-xs text-slate-500">{d.vehiculo_placa} · {timeAgo(d.timestamp)}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-slate-900">{formatNumber(d.distance_m)} m</p>
                          <p className="flex items-center justify-end gap-1 text-xs text-slate-500">
                            <Gauge className="h-3 w-3" /> {d.speed_kmh != null ? `${d.speed_kmh.toFixed(0)} km/h` : "—"}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
