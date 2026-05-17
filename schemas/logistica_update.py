from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class VehiculoUpdate(BaseModel):
    estado: Optional[str] = None
    capacidad_kg: Optional[Decimal] = None
    # No permitimos actualizar la placa (unique) ni el ID

class ConductorUpdate(BaseModel):
    disponibilidad: Optional[str] = None
    nombre: Optional[str] = None
    # No permitimos actualizar la licencia (unique), el usuario_id ni el ID
