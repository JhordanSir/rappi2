from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoAsignacion, TipoEvidencia, lat_field, lon_field


class AsignacionBase(BaseModel):
    orden_id: int
    conductor_id: int
    vehiculo_placa: str


class AsignacionCreate(BaseModel):
    # Una orden (legacy) o varias agrupadas en la misma ruta del conductor.
    orden_id: Optional[int] = None
    orden_ids: Optional[List[int]] = None
    conductor_id: int
    vehiculo_placa: str


class EntregarDestinoRequest(BaseModel):
    receptor: str
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()


class FallarDestinoRequest(BaseModel):
    """El conductor marca un destino como no entregado, con el motivo."""
    motivo: str


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
    orden_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


class SugerenciaConductor(BaseModel):
    """Candidato sugerido para asignar una orden (conductor disponible más cercano)."""
    conductor_id: int
    nombre: str
    vehiculo_placa: Optional[str] = None
    distancia_km: Optional[float] = None
    rating: Optional[float] = None
    total_calificaciones: int = 0
    capacidad_kg: Optional[float] = None
    peso_requerido_kg: float = 0
    suficiente: bool = True


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
