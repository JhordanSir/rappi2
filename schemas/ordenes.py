from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoOrden


class OrdenBase(BaseModel):
    cliente_id: int
    direccion_origen: str
    distrito_origen: Optional[str] = None
    direccion_destino: str
    distrito_destino: Optional[str] = None
    total: Optional[Decimal] = None


class OrdenCreate(OrdenBase):
    pass


class OrdenUpdate(BaseModel):
    estado: Optional[EstadoOrden] = None
    direccion_origen: Optional[str] = None
    distrito_origen: Optional[str] = None
    direccion_destino: Optional[str] = None
    distrito_destino: Optional[str] = None
    total: Optional[Decimal] = None


class OrdenResponse(OrdenBase):
    id: int
    estado: EstadoOrden
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)
