from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import EstadoParada, lat_field, lon_field


class ParadaBase(BaseModel):
    orden_id: Optional[int] = None
    direccion: str
    distrito: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    secuencia: int
    estado: EstadoParada = "Pendiente"


class ParadaCreate(ParadaBase):
    pass


class ParadaUpdate(BaseModel):
    estado: Optional[EstadoParada] = None
    fecha_paso: Optional[datetime] = None
    direccion: Optional[str] = None
    distrito: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()


class ParadaVisitarRequest(BaseModel):
    """Coordenadas reales del momento en que se visita la parada (opcionales)."""
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()


class ParadaResponse(ParadaBase):
    id: int
    ruta_id: int
    fecha_paso: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RutaBase(BaseModel):
    orden_id: int
    distancia_km: Optional[Decimal] = None
    tiempo_estimado: Optional[timedelta] = None


class RutaCreate(RutaBase):
    paradas: List[ParadaCreate] = []


class RutaUpdate(BaseModel):
    distancia_km: Optional[Decimal] = None
    tiempo_estimado: Optional[timedelta] = None


class RutaResponse(RutaBase):
    id: int
    paradas: List[ParadaResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ReordenarRutaRequest(BaseModel):
    """Nuevo orden manual de las paradas (lista de parada_id en el orden deseado)."""
    parada_ids: List[int]


class PlanificarRutaRequest(BaseModel):
    orden_id: int
    # Coordenadas opcionales: si se omiten se toman de la orden (lat/lon origen y destino).
    origen_lon: Optional[float] = lon_field()
    origen_lat: Optional[float] = lat_field()
    destino_lon: Optional[float] = lon_field()
    destino_lat: Optional[float] = lat_field()
    generar_geocerca: bool = True
    tolerancia_metros: int = Field(50, ge=1, le=5000)
