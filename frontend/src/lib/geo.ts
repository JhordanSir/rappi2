import { api } from "@/lib/api";

/**
 * Geocodificación inversa: convierte un punto (lat/lon) en una dirección legible
 * para autocompletar los formularios al tocar el mapa. Devuelve null si no se pudo.
 */
export async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
  try {
    const { data } = await api.get<{ direccion: string | null }>("/geo/reverse", {
      params: { lat, lon },
    });
    return data.direccion;
  } catch {
    return null;
  }
}
