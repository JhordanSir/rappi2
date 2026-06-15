from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PuntoGeo(BaseModel):
    """Direccion con coordenadas (punto de partida o de llegada)."""
    direccion: Optional[str] = None
    distrito: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class PosicionActual(BaseModel):
    lat: float
    lon: float
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    timestamp: datetime


class ParadaSeguimiento(BaseModel):
    id: int
    secuencia: int
    direccion: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    estado: str
    fecha_paso: Optional[datetime] = None


class AsignacionSeguimiento(BaseModel):
    id: int
    estado: str
    conductor_id: int
    conductor_nombre: Optional[str] = None
    vehiculo_placa: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None


class RutaSeguimiento(BaseModel):
    id: int
    distancia_km: Optional[float] = None
    tiempo_estimado_segundos: Optional[float] = None


class OrdenSeguimientoResponse(BaseModel):
    """Vista agregada para la pantalla de trackeo de una orden.

    Combina datos de PostgreSQL (orden, asignacion, ruta, paradas) con MongoDB
    (ultima posicion GPS, estadisticas y geocercas activas).
    """
    orden_id: int
    estado: str
    cliente_id: int
    origen: PuntoGeo
    destino: PuntoGeo
    asignacion: Optional[AsignacionSeguimiento] = None
    posicion_actual: Optional[PosicionActual] = None
    ruta: Optional[RutaSeguimiento] = None
    paradas: List[ParadaSeguimiento] = []
    geocercas: List[Dict[str, Any]] = []
    estadisticas: Optional[Dict[str, Any]] = None
