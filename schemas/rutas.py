from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import EstadoParada


class ParadaBase(BaseModel):
    orden_id: Optional[int] = None
    direccion: str
    distrito: Optional[str] = None
    secuencia: int
    estado: EstadoParada = "Pendiente"


class ParadaCreate(ParadaBase):
    pass


class ParadaUpdate(BaseModel):
    estado: Optional[EstadoParada] = None
    fecha_paso: Optional[datetime] = None
    direccion: Optional[str] = None
    distrito: Optional[str] = None


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


class PlanificarRutaRequest(BaseModel):
    orden_id: int
    origen_lon: float = Field(..., ge=-180, le=180)
    origen_lat: float = Field(..., ge=-90, le=90)
    destino_lon: float = Field(..., ge=-180, le=180)
    destino_lat: float = Field(..., ge=-90, le=90)
    generar_geocerca: bool = True
    tolerancia_metros: int = Field(50, ge=1, le=5000)
