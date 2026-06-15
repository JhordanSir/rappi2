import { useEffect } from "react";
import type { ReactNode } from "react";
import { MapContainer, TileLayer, useMap, useMapEvents, Marker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { pinIcon } from "./icons";

export type LatLng = [number, number];

function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 14);
    } else {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
    }
  }, [JSON.stringify(points)]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function ClickCapture({ onClick }: { onClick: (p: LatLng) => void }) {
  useMapEvents({
    click(e) {
      onClick([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

export function MapView({
  points = [],
  center = [-16.409, -71.5375],
  zoom = 12,
  height = 380,
  children,
  fit = true,
  onClick,
}: {
  points?: LatLng[];
  center?: LatLng;
  zoom?: number;
  height?: number | string;
  children?: ReactNode;
  fit?: boolean;
  onClick?: (p: LatLng) => void;
}) {
  return (
    <div style={{ height }} className="overflow-hidden rounded-2xl border border-slate-200">
      <MapContainer center={center} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {fit && points.length > 0 && <FitBounds points={points} />}
        {onClick && <ClickCapture onClick={onClick} />}
        {children}
      </MapContainer>
    </div>
  );
}

/** Mapa interactivo para elegir una coordenada (clic en el mapa). */
export function LocationPicker({
  value,
  onChange,
  height = 300,
  color = "#0d9488",
}: {
  value: LatLng | null;
  onChange: (p: LatLng) => void;
  height?: number;
  color?: string;
}) {
  function ClickHandler() {
    useMapEvents({
      click(e) {
        onChange([e.latlng.lat, e.latlng.lng]);
      },
    });
    return null;
  }
  return (
    <div style={{ height }} className="overflow-hidden rounded-xl border border-slate-200">
      <MapContainer center={value ?? [-16.409, -71.5375]} zoom={12} style={{ height: "100%", width: "100%" }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
        <ClickHandler />
        {value && <Marker position={value} icon={pinIcon(color)} />}
      </MapContainer>
    </div>
  );
}
