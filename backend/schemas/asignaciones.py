from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoAsignacion, TipoEvidencia, lat_field, lon_field


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


class FinalizarAsignacionRequest(BaseModel):
    """Datos opcionales de confirmacion de entrega al finalizar la asignacion."""
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    receptor: Optional[str] = None
    nota: Optional[str] = None


class AsignacionResponse(AsignacionBase):
    id: int
    estado: EstadoAsignacion
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    entrega_lat: Optional[float] = None
    entrega_lon: Optional[float] = None
    entrega_receptor: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ArchivoEntregaRef(BaseModel):
    file_id: str
    filename: str
    content_type: Optional[str] = None
    size: int


class EntregaOut(BaseModel):
    id: str
    asignacion_id: int
    tipo: TipoEvidencia
    descripcion: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    receptor: Optional[str] = None
    archivos: List[ArchivoEntregaRef] = []
    uploaded_by: Optional[int] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
