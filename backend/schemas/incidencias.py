from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IncidenciaBase(BaseModel):
    asignacion_id: int
    tipo: str
    severidad: int = Field(..., ge=1, le=5)
    notas: Optional[str] = None
    evidencia_url: Optional[str] = None


class IncidenciaCreate(IncidenciaBase):
    pass


class IncidenciaUpdate(BaseModel):
    tipo: Optional[str] = None
    severidad: Optional[int] = Field(None, ge=1, le=5)
    notas: Optional[str] = None
    evidencia_url: Optional[str] = None


class IncidenciaResponse(IncidenciaBase):
    id: int
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)
