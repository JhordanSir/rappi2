import httpx

from core.config import settings


class OSRMService:
    """Ruteo por calles usando OSRM (no requiere API key).

    Por defecto usa el servidor demo público; configurable con OSRM_URL para
    apuntar a una instancia propia en producción.
    """

    def __init__(self):
        root = getattr(settings, "OSRM_URL", "https://router.project-osrm.org")
        self.base_url = root + "/route/v1/driving"
        self.trip_url = root + "/trip/v1/driving"

    async def optimize_trip(self, puntos: list[tuple[float, float]], roundtrip: bool = False) -> dict:
        """Optimiza el orden de visita de varios puntos (OSRM trip service).

        puntos = lista de (lon, lat); el primero se fija como origen (source=first).
        Devuelve el orden óptimo (índices del input), la geometría por calles y métricas.
        """
        if len(puntos) < 2:
            raise Exception("Se requieren al menos 2 puntos para optimizar")
        coords = ";".join(f"{lon},{lat}" for lon, lat in puntos)
        url = f"{self.trip_url}/{coords}"
        params = {
            "source": "first",
            "roundtrip": "true" if roundtrip else "false",
            "overview": "full",
            "geometries": "geojson",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise Exception(f"OSRM Trip Error: {response.text}")
            data = response.json()
            trips = data.get("trips") or []
            waypoints = data.get("waypoints") or []
            if not trips or not waypoints:
                raise Exception("OSRM no devolvió un trip")
            trip = trips[0]
            # waypoint_index = posición del punto i dentro del recorrido óptimo.
            # Invertimos para obtener: orden_optimo[posición] = índice del input original.
            orden_optimo = [0] * len(waypoints)
            for input_idx, wp in enumerate(waypoints):
                orden_optimo[wp["waypoint_index"]] = input_idx
            return {
                "orden": orden_optimo,
                "geometry": trip["geometry"],
                "distancia_km": trip["distance"] / 1000.0,
                "tiempo_segundos": trip["duration"],
            }

    async def get_route_multi(self, puntos: list[tuple[float, float]]) -> dict:
        """Geometría/métricas por calles a lo largo de varios puntos en el orden dado.
        puntos = lista de (lon, lat)."""
        if len(puntos) < 2:
            raise Exception("Se requieren al menos 2 puntos")
        coords = ";".join(f"{lon},{lat}" for lon, lat in puntos)
        url = f"{self.base_url}/{coords}"
        params = {"overview": "full", "geometries": "geojson"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                raise Exception(f"OSRM API Error: {response.text}")
            routes = (response.json().get("routes") or [])
            if not routes:
                raise Exception("OSRM no devolvió rutas")
            route = routes[0]
            return {
                "geometry": route["geometry"],
                "distancia_km": route["distance"] / 1000.0,
                "tiempo_segundos": route["duration"],
            }

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
