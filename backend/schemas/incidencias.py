from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IncidenciaCreate(BaseModel):
    """Reporte de incidencia. El chofer envía solo tipo (+ nota). La severidad la
    deriva el servidor por tipo; no se acepta del chofer."""
    asignacion_id: int
    tipo: str
    notas: Optional[str] = None


class IncidenciaUpdate(BaseModel):
    """Ajustes que hace el admin (incluida la severidad)."""
    tipo: Optional[str] = None
    severidad: Optional[int] = Field(None, ge=1, le=5)
    notas: Optional[str] = None


class IncidenciaResponse(BaseModel):
    id: int
    asignacion_id: int
    tipo: str
    severidad: int
    origen: str
    notas: Optional[str] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)
