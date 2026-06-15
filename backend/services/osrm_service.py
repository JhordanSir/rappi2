import httpx

from core.config import settings


class OSRMService:
    """Ruteo por calles usando OSRM (no requiere API key).

    Por defecto usa el servidor demo público; configurable con OSRM_URL para
    apuntar a una instancia propia en producción.
    """

    def __init__(self):
        self.base_url = getattr(settings, "OSRM_URL", "https://router.project-osrm.org") + "/route/v1/driving"

    async def get_route(self, lon_origen: float, lat_origen: float, lon_destino: float, lat_destino: float) -> dict:
        url = f"{self.base_url}/{lon_origen},{lat_origen};{lon_destino},{lat_destino}"
        params = {"overview": "full", "geometries": "geojson"}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise Exception(f"OSRM API Error: {response.text}")
            data = response.json()
            routes = data.get("routes") or []
            if not routes:
                raise Exception("OSRM no devolvió rutas")
            route = routes[0]
            return {
                "geometry": route["geometry"],  # GeoJSON LineString ([lon, lat])
                "distancia_km": route["distance"] / 1000.0,
                "tiempo_segundos": route["duration"],
            }


osrm_service = OSRMService()
