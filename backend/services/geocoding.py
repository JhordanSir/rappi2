import logging
from typing import Optional, Tuple

from core.config import settings
from services.ors_service import ors_service

logger = logging.getLogger(__name__)


async def resolver_coords(
    direccion: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Resuelve la latitud/longitud de una direccion de forma hibrida.

    - Si llegan ``lat`` y ``lon`` se devuelven tal cual (no se geocodifica).
    - Si faltan y hay texto de direccion, se intenta geocodificar con ORS.
    - Ante cualquier fallo (ORS caido, sin API key, geocoding deshabilitado o
      sin resultados) devuelve las coords originales sin lanzar excepcion, para
      no bloquear la creacion/actualizacion del recurso.

    Retorna una tupla ``(lat, lon)``.
    """
    if lat is not None and lon is not None:
        return lat, lon
    if not getattr(settings, "GEOCODING_ENABLED", True):
        return lat, lon
    if not direccion or not direccion.strip():
        return lat, lon

    try:
        result = await ors_service.geocode(direccion)
    except Exception as exc:  # resiliencia: nunca bloquear por geocodificacion
        logger.warning("Geocodificacion fallida para %r: %s", direccion, exc)
        return lat, lon

    if result is None:
        return lat, lon

    geo_lon, geo_lat = result
    return geo_lat, geo_lon


async def direccion_desde_coords(lat: float, lon: float) -> Optional[str]:
    """Geocodificacion inversa resiliente: coordenadas -> direccion legible.

    Devuelve None (sin lanzar) si el geocoding esta deshabilitado o ORS falla, para
    no romper la UI; el usuario siempre puede escribir la direccion a mano.
    """
    if not getattr(settings, "GEOCODING_ENABLED", True):
        return None
    try:
        return await ors_service.reverse_geocode(lat, lon)
    except Exception as exc:
        logger.warning("Geocodificacion inversa fallida para (%s, %s): %s", lat, lon, exc)
        return None
