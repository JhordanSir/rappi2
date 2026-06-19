import { useParams, useNavigate } from "react-router-dom";
import { Marker, Polyline, Popup } from "react-leaflet";
import { ArrowLeft, Truck, Star } from "lucide-react";
import { useSeguimiento } from "@/api/hooks";
import { MapView, type LatLng } from "@/components/map/MapView";
import { pinIcon, liveIcon, COLORS } from "@/components/map/icons";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageLoader } from "@/components/ui/Feedback";
import { formatDate, humanDuration } from "@/lib/utils";

export default function SeguimientoCliente() {
  const { id } = useParams();
  const navigate = useNavigate();
  const ordenId = Number(id);
  // Refresca cada 8s; además el SSE invalida ["seguimiento"] en tiempo real.
  const { data: s, isLoading } = useSeguimiento(ordenId || undefined, 8000);

  if (isLoading || !s) return <PageLoader />;

  const origen: LatLng | null = s.origen.lat != null && s.origen.lon != null ? [s.origen.lat, s.origen.lon] : null;
  const destino: LatLng | null = s.destino.lat != null && s.destino.lon != null ? [s.destino.lat, s.destino.lon] : null;
  const pos: LatLng | null = s.posicion_actual ? [s.posicion_actual.lat, s.posicion_actual.lon] : null;
  const linea: LatLng[] = (s.ruta?.geometria?.coordinates ?? []).map((c: number[]) => [c[1], c[0]] as LatLng);
  const puntos: LatLng[] = [origen, destino, pos, ...linea].filter(Boolean) as LatLng[];

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700">
        <ArrowLeft className="h-4 w-4" /> Volver
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-stone-800">Pedido #{s.orden_id}</h1>
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge kind="orden" value={s.estado} />
            {s.asignacion && (
              <span className="flex items-center gap-1 text-sm text-stone-500">
                <Truck className="h-4 w-4" /> {s.asignacion.conductor_nombre ?? "Conductor"} · {s.asignacion.vehiculo_placa ?? "—"}
              </span>
            )}
          </div>
        </div>
        {s.estado === "Entregado" && (
          <Button onClick={() => navigate(`/orden/${s.orden_id}/calificar`)}>
            <Star className="h-4 w-4" /> Calificar
          </Button>
        )}
      </div>

      <MapView points={puntos} height={400}>
        {linea.length > 1 && <Polyline positions={linea} pathOptions={{ color: COLORS.brand, weight: 4, opacity: 0.7 }} />}
        {origen && <Marker position={origen} icon={pinIcon(COLORS.origen)}><Popup>Origen</Popup></Marker>}
        {destino && <Marker position={destino} icon={pinIcon(COLORS.destino)}><Popup>Destino</Popup></Marker>}
        {pos && <Marker position={pos} icon={liveIcon(COLORS.live)}><Popup>Tu conductor está aquí</Popup></Marker>}
      </MapView>

      {s.posicion_actual && (
        <p className="text-xs text-stone-400">
          Última posición {formatDate(s.posicion_actual.timestamp)}
          {s.estadisticas?.duracion_segundos != null && ` · en ruta ${humanDuration(s.estadisticas.duracion_segundos)}`}
        </p>
      )}

      {s.paradas.length > 0 && (
        <div className="rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
          <p className="mb-2 text-sm font-semibold text-stone-700">Progreso</p>
          <ol className="space-y-2">
            {s.paradas.map((p) => (
              <li key={p.id} className="flex items-center gap-2 text-sm">
                <span className={`h-2.5 w-2.5 rounded-full ${p.estado === "Visitada" ? "bg-emerald-500" : "bg-stone-300"}`} />
                <span className="text-stone-600">{p.direccion}</span>
                <StatusBadge kind="parada" value={p.estado} />
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
