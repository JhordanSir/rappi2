from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import EstadoOrden, lat_field, lon_field

NivelServicio = Literal["estandar", "express", "urgente"]


class PaqueteFields(BaseModel):
    """Datos del paquete que alimentan el cálculo de precio."""
    peso_kg: Optional[float] = None
    largo_cm: Optional[float] = None
    ancho_cm: Optional[float] = None
    alto_cm: Optional[float] = None


class DestinoIn(PaqueteFields):
    # Opcional para permitir cotizar solo con coordenadas; al crear, se exige dirección.
    direccion: Optional[str] = None
    distrito: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    nombre_destinatario: Optional[str] = None


class DestinoOut(PaqueteFields):
    id: int
    secuencia: int
    direccion: str
    distrito: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    nombre_destinatario: Optional[str] = None
    subtotal: Optional[Decimal] = None
    estado: str
    nota: Optional[str] = None
    entrega_receptor: Optional[str] = None
    fecha_entrega: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrdenCreate(PaqueteFields):
    cliente_id: int
    direccion_origen: str
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = lat_field()
    lon_origen: Optional[float] = lon_field()
    # Destinos múltiples (preferido). Si se omite, se usan los campos legacy de un destino.
    destinos: Optional[List[DestinoIn]] = None
    direccion_destino: Optional[str] = None
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None
    # Ajuste manual de precio: solo lo aplica el staff.
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None


class OrdenUpdate(BaseModel):
    estado: Optional[EstadoOrden] = None
    direccion_origen: Optional[str] = None
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = lat_field()
    lon_origen: Optional[float] = lon_field()
    direccion_destino: Optional[str] = None
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()
    peso_kg: Optional[float] = None
    largo_cm: Optional[float] = None
    ancho_cm: Optional[float] = None
    alto_cm: Optional[float] = None
    nivel_servicio: Optional[NivelServicio] = None
    programado_para: Optional[datetime] = None
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None


class OrdenResponse(PaqueteFields):
    id: int
    cliente_id: int
    estado: EstadoOrden
    direccion_origen: str
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = None
    lon_origen: Optional[float] = None
    direccion_destino: str
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = None
    lon_destino: Optional[float] = None
    fecha_creacion: datetime
    total: Optional[Decimal] = None
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None
    ajuste_por: Optional[int] = None
    destinos: List[DestinoOut] = []

    model_config = ConfigDict(from_attributes=True)


class CotizarRequest(PaqueteFields):
    """Cotización sin crear orden. Requiere origen; uno o varios destinos."""
    lat_origen: float = Field(..., ge=-90, le=90)
    lon_origen: float = Field(..., ge=-180, le=180)
    # Destino único (legacy) o varios.
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()
    destinos: Optional[List[DestinoIn]] = None
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None


class TramoCotizado(BaseModel):
    distancia_km: float
    tiempo_min: float
    peso_cobrable_kg: float
    total: float


class CotizacionResponse(BaseModel):
    """Cotización agregada: un tramo por destino y el total (suma de tramos)."""
    tramos: List[TramoCotizado] = []
    distancia_km: float
    tiempo_min: float
    total: float
    moneda: str
