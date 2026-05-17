from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

class VehiculoBase(BaseModel):
    placa: str
    tipo: str
    capacidad_kg: Decimal
    estado: Optional[str] = "Operativo"
    is_active: Optional[bool] = True

class VehiculoCreate(VehiculoBase):
    pass

class VehiculoResponse(VehiculoBase):
    id: int
    fecha_mantenimiento: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ConductorBase(BaseModel):
    nombre: str
    licencia: str
    disponibilidad: Optional[str] = "Disponible"
    is_active: Optional[bool] = True

class ConductorCreate(ConductorBase):
    usuario_id: int

class ConductorResponse(ConductorBase):
    id: int
    usuario_id: int

    model_config = ConfigDict(from_attributes=True)
