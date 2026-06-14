from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoOrden, lat_field, lon_field


class OrdenBase(BaseModel):
    cliente_id: int
    direccion_origen: str
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = lat_field()
    lon_origen: Optional[float] = lon_field()
    direccion_destino: str
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()
    total: Optional[Decimal] = None


class OrdenCreate(OrdenBase):
    pass


class OrdenUpdate(BaseModel):
    estado: Optional[EstadoOrden] = None
    direccion_origen: Optional[str] = None
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = lat_field()
    lon_origen: Optional[float] = lon_field()
    direccion_destino: Optional[str] = None
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()
    total: Optional[Decimal] = None


class OrdenResponse(OrdenBase):
    id: int
    estado: EstadoOrden
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)
