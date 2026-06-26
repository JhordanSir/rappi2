from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_user
from models.usuarios import Usuario
from services.geocoding import direccion_desde_coords

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    _: Usuario = Depends(get_current_user),
):
    """Geocodificacion inversa: convierte un punto (lat/lon) en una direccion
    legible para autocompletar formularios al tocar el mapa. Devuelve
    {"direccion": <texto|null>}."""
    direccion = await direccion_desde_coords(lat, lon)
    return {"direccion": direccion}
