import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

/**
 * Mientras `enabled` es true, observa la ubicación del navegador y emite pings GPS
 * al backend (throttle ~6s). Solo tiene sentido con la asignación EnCurso.
 */
export function useGpsTracking(opts: {
  asignacionId: number;
  conductorId: number;
  vehiculoPlaca: string;
  enabled: boolean;
}) {
  const { asignacionId, conductorId, vehiculoPlaca, enabled } = opts;
  const [last, setLast] = useState<{ lat: number; lon: number; ts: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastSent = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    if (!("geolocation" in navigator)) {
      setError("Geolocalización no disponible en este dispositivo");
      return;
    }
    setError(null);
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude, speed, heading, accuracy } = pos.coords;
        setLast({ lat: latitude, lon: longitude, ts: Date.now() });
        const now = Date.now();
        if (now - lastSent.current < 6000) return; // no saturar: 1 ping cada ~6s
        lastSent.current = now;
        api
          .post("/tracking/ping", {
            asignacion_id: asignacionId,
            conductor_id: conductorId,
            vehiculo_placa: vehiculoPlaca,
            lat: latitude,
            lon: longitude,
            speed_kmh: speed != null ? Math.round(speed * 3.6 * 10) / 10 : null,
            heading: heading ?? null,
            accuracy_m: accuracy ?? null,
          })
          .catch(() => {});
      },
      (err) => setError(err.message),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, [enabled, asignacionId, conductorId, vehiculoPlaca]);

  return { last, error };
}
