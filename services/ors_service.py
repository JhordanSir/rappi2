import httpx
from core.config import settings

class ORSService:
    def __init__(self):
        self.api_key = getattr(settings, "ORS_API_KEY", "dummy_key")
        self.base_url = "https://api.openrouteservice.org/v2/directions/driving-car"

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

ors_service = ORSService()
