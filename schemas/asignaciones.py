from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoAsignacion


class AsignacionBase(BaseModel):
    orden_id: int
    conductor_id: int
    vehiculo_placa: str


class AsignacionCreate(AsignacionBase):
    pass


class AsignacionUpdate(BaseModel):
    estado: Optional[EstadoAsignacion] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None


class AsignacionResponse(AsignacionBase):
    id: int
    estado: EstadoAsignacion
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
