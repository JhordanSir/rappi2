export type LatLng = [number, number];

const OSRM = "https://router.project-osrm.org/route/v1/driving";

/**
 * Obtiene la geometría real de la ruta por calles entre dos puntos usando OSRM
 * (servicio público, sin API key). Devuelve la polilínea como [lat, lon][] lista
 * para Leaflet, o null si falla (el llamador puede caer a una línea recta).
 *
 * Los puntos de entrada y salida usan el orden [lat, lon].
 */
export async function fetchRoadRoute(origin: LatLng, dest: LatLng): Promise<LatLng[] | null> {
  const url = `${OSRM}/${origin[1]},${origin[0]};${dest[1]},${dest[0]}?overview=full&geometries=geojson`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const coords: number[][] | undefined = data?.routes?.[0]?.geometry?.coordinates;
    if (!coords || coords.length < 2) return null;
    return coords.map((c) => [c[1], c[0]] as LatLng);
  } catch {
    return null;
  }
}
