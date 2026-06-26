import httpx
from core.config import settings

class ORSService:
    def __init__(self):
        self.api_key = getattr(settings, "ORS_API_KEY", "dummy_key")
        self.base_url = "https://api.openrouteservice.org/v2/directions/driving-car"
        self.geocode_url = "https://api.openrouteservice.org/geocode/search"
        self.reverse_url = "https://api.openrouteservice.org/geocode/reverse"

    async def get_route(self, lon_origen: float, lat_origen: float, lon_destino: float, lat_destino: float):
        """
        Llama a OpenRouteService y retorna la ruta.
        """
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        body = {
            "coordinates": [[lon_origen, lat_origen], [lon_destino, lat_destino]],
            "format": "geojson"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, json=body, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # Extraemos info
                feature = data["features"][0]
                geometry = feature["geometry"] # tipo LineString y coordinates
                properties = feature["properties"]
                distancia_km = properties["summary"]["distance"] / 1000.0 # m a km
                tiempo_segundos = properties["summary"]["duration"]

                return {
                    "geometry": geometry,
                    "distancia_km": distancia_km,
                    "tiempo_segundos": tiempo_segundos
                }
            else:
                raise Exception(f"ORS API Error: {response.text}")

    async def geocode(self, texto: str) -> tuple[float, float] | None:
        """
        Geocodifica una direccion de texto a coordenadas usando ORS.

        Retorna (lon, lat) del primer resultado, o None si no hay coincidencias.
        Lanza Exception si la API responde con error.
        """
        if not texto or not texto.strip():
            return None

        params = {"api_key": self.api_key, "text": texto, "size": 1}

        async with httpx.AsyncClient() as client:
            response = await client.get(self.geocode_url, params=params)
            if response.status_code != 200:
                raise Exception(f"ORS Geocode Error: {response.text}")
            data = response.json()
            features = data.get("features") or []
            if not features:
                return None
            lon, lat = features[0]["geometry"]["coordinates"][:2]
            return float(lon), float(lat)

    async def reverse_geocode(self, lat: float, lon: float) -> str | None:
        """Geocodificacion inversa: coordenadas -> direccion legible (label).

        Retorna el texto de la primera coincidencia, o None si no hay resultados.
        Lanza Exception si la API responde con error.
        """
        params = {"api_key": self.api_key, "point.lat": lat, "point.lon": lon, "size": 1}

        async with httpx.AsyncClient() as client:
            response = await client.get(self.reverse_url, params=params)
            if response.status_code != 200:
                raise Exception(f"ORS Reverse Error: {response.text}")
            data = response.json()
            features = data.get("features") or []
            if not features:
                return None
            return features[0].get("properties", {}).get("label")

ors_service = ORSService()
