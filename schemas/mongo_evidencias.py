from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import TipoEvidencia


class EvidenciaBase(BaseModel):
    urls: List[str] = Field(..., min_length=1)
    tipo: TipoEvidencia
    descripcion: Optional[str] = None


class EvidenciaIn(EvidenciaBase):
    pass


class EvidenciaOut(EvidenciaBase):
    id: str
    incidencia_id: int
    uploaded_by: Optional[int] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
