from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import TipoEvidencia


class ArchivoRef(BaseModel):
    file_id: str
    filename: str
    content_type: Optional[str] = None
    size: int


class EvidenciaIn(BaseModel):
    """Carga de evidencia por enlace externo (ej. S3 ya subido por el cliente)."""

    urls: List[str] = Field(..., min_length=1)
    tipo: TipoEvidencia
    descripcion: Optional[str] = None


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
