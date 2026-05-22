from typing import Generic, List, Literal, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

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
