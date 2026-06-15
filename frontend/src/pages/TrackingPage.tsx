import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Circle, Marker, Popup } from "react-leaflet";
import { Navigation, Gauge, Crosshair, Search } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/Feedback";
import { MapView, type LatLng } from "@/components/map/MapView";
import { pinIcon, liveIcon, COLORS } from "@/components/map/icons";
import { formatNumber, timeAgo } from "@/lib/utils";

interface NearDriver {
  conductor_id: number;
  asignacion_id: number;
  vehiculo_placa: string;
  location: { coordinates: [number, number] };
  speed_kmh?: number | null;
  timestamp: string;
  distance_m: number;
}

export default function TrackingPage() {
  const [point, setPoint] = useState<LatLng>([-16.409, -71.5375]);
  const [radio, setRadio] = useState(5000);
  const [ventana, setVentana] = useState(15);

  const { data, isFetching } = useQuery({
    queryKey: ["conductores-cerca", point, radio, ventana],
    queryFn: () =>
      api
        .get<NearDriver[]>("/tracking/conductores-cerca", {
          params: { lon: point[1], lat: point[0], radio_m: radio, ventana_min: ventana },
        })
        .then((r) => r.data),
    refetchInterval: 10000,
  });

  const drivers = data ?? [];
  const points: LatLng[] = [point, ...drivers.map((d) => [d.location.coordinates[1], d.location.coordinates[0]] as LatLng)];

  return (
    <div>
      <PageHeader title="Tracking en vivo" subtitle="Localiza conductores activos alrededor de un punto en tiempo real" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="overflow-hidden">
            <CardHeader
              title="Mapa operativo"
              subtitle="Haz clic en el mapa para mover el punto de búsqueda"
              action={isFetching ? <Badge tone="blue">Buscando…</Badge> : <Badge tone="green">{drivers.length} en rango</Badge>}
            />
            <MapView points={points} height={460} onClick={setPoint}>
              <Marker position={point} icon={pinIcon("#0d9488")}>
                <Popup>Punto de búsqueda</Popup>
              </Marker>
              <Circle center={point} radius={radio} pathOptions={{ color: "#0d9488", weight: 1, fillOpacity: 0.05 }} />
              {drivers.map((d) => (
                <Marker
                  key={d.conductor_id}
                  position={[d.location.coordinates[1], d.location.coordinates[0]]}
                  icon={liveIcon(COLORS.conductor)}
                >
                  <Popup>
                    Conductor #{d.conductor_id} · {d.vehiculo_placa}
                    <br />
                    {formatNumber(d.distance_m)} m · {timeAgo(d.timestamp)}
                  </Popup>
                </Marker>
              ))}
            </MapView>
          </Card>
        </div>

        <div className="space-y-6">
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
        </div>
      </div>
    </div>
  );
}
