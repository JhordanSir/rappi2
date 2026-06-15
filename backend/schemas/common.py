from typing import Generic, List, Literal, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


def lat_field(default: Optional[float] = None):
    """Campo de latitud validado (-90..90). Usar en schemas con coordenadas."""
    return Field(default, ge=-90, le=90)


def lon_field(default: Optional[float] = None):
    """Campo de longitud validado (-180..180). Usar en schemas con coordenadas."""
    return Field(default, ge=-180, le=180)

EstadoOrden = Literal["Pendiente", "En Proceso", "En Tránsito", "Entregado", "Cancelado"]
EstadoVehiculo = Literal["Operativo", "Mantenimiento", "Inactivo"]
DisponibilidadConductor = Literal["Disponible", "Ocupado", "Inactivo"]
EstadoAsignacion = Literal["Asignada", "EnCurso", "Finalizada", "Cancelada"]
EstadoParada = Literal["Pendiente", "Visitada", "Omitida"]
EstadoPago = Literal["Pendiente", "Pagado", "Fallido", "Reembolsado"]
TipoGeocerca = Literal["ruta_buffer", "zona_entrega", "prohibida"]
TipoEvidencia = Literal["foto", "video", "audio", "documento"]
TipoDestinatario = Literal["usuario", "cliente"]


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int


class MessageResponse(BaseModel):
    message: str
