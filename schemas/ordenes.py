from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

class Coordenada(BaseModel):
    lat: float
    lon: float

class OrdenBase(BaseModel):
    cliente_id: int
    origen: Coordenada
    destino: Coordenada
    origen_texto: str
    destino_texto: str

class OrdenCreate(OrdenBase):
    pass

class OrdenUpdate(BaseModel):
    estado: Optional[str] = None
    origen_texto: Optional[str] = None
    destino_texto: Optional[str] = None

class OrdenResponse(BaseModel):
    id: int
    cliente_id: int
    estado: str
    origen_texto: str
    destino_texto: str
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)

class AsignacionBase(BaseModel):
    orden_id: int
    conductor_id: int
    vehiculo_id: int

class AsignacionCreate(AsignacionBase):
    pass

class AsignacionResponse(AsignacionBase):
    id: int
    estado: str
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
