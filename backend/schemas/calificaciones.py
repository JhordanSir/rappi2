from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CalificacionCreate(BaseModel):
    puntaje: int = Field(..., ge=1, le=5)
    comentario: Optional[str] = None


class CalificacionResponse(BaseModel):
    id: int
    orden_id: int
    conductor_id: Optional[int] = None
    cliente_id: int
    puntaje: int
    comentario: Optional[str] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class ConductorRating(BaseModel):
    conductor_id: int
    promedio: Optional[float] = None
    total: int = 0
