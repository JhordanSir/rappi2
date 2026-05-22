from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import TipoEvidencia


class ArchivoRef(BaseModel):
    file_id: str
    filename: str
    content_type: Optional[str] = None
    size: int


class EvidenciaOut(BaseModel):
    id: str
    incidencia_id: int
    urls: List[str] = []
    archivos: List[ArchivoRef] = []
    tipo: TipoEvidencia
    descripcion: Optional[str] = None
    uploaded_by: Optional[int] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
