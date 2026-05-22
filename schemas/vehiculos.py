from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoVehiculo


class VehiculoBase(BaseModel):
    placa: str
    tipo: str
    capacidad_kg: Decimal
    estado: EstadoVehiculo = "Operativo"
    fecha_mantenimiento: Optional[datetime] = None


class VehiculoCreate(VehiculoBase):
    pass


class VehiculoUpdate(BaseModel):
    tipo: Optional[str] = None
    capacidad_kg: Optional[Decimal] = None
    estado: Optional[EstadoVehiculo] = None
    fecha_mantenimiento: Optional[datetime] = None
    activo: Optional[bool] = None


class VehiculoResponse(VehiculoBase):
    activo: bool

    model_config = ConfigDict(from_attributes=True)
