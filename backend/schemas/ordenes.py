from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import EstadoOrden, lat_field, lon_field

NivelServicio = Literal["estandar", "express", "urgente"]


class PaqueteFields(BaseModel):
    """Datos del paquete que alimentan el cálculo de precio."""
    peso_kg: Optional[float] = None
    largo_cm: Optional[float] = None
    ancho_cm: Optional[float] = None
    alto_cm: Optional[float] = None


class OrdenBase(BaseModel):
    cliente_id: int
    direccion_origen: str
    distrito_origen: Optional[str] = None
    lat_origen: Optional[float] = lat_field()
    lon_origen: Optional[float] = lon_field()
    direccion_destino: str
    distrito_destino: Optional[str] = None
    lat_destino: Optional[float] = lat_field()
    lon_destino: Optional[float] = lon_field()


class OrdenCreate(OrdenBase, PaqueteFields):
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None
    # Ajuste manual de precio: solo lo aplica el staff (el servidor lo ignora para clientes).
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None
    # 'total' NO se acepta del cliente: el servidor lo calcula.


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
    # Ajuste de precio (staff): monto + motivo. El total se recalcula en el endpoint.
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None


class OrdenResponse(OrdenBase, PaqueteFields):
    id: int
    estado: EstadoOrden
    fecha_creacion: datetime
    total: Optional[Decimal] = None
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CotizarRequest(PaqueteFields):
    """Cotización sin crear orden. Requiere coordenadas de origen y destino."""
    lat_origen: float = Field(..., ge=-90, le=90)
    lon_origen: float = Field(..., ge=-180, le=180)
    lat_destino: float = Field(..., ge=-90, le=90)
    lon_destino: float = Field(..., ge=-180, le=180)
    nivel_servicio: NivelServicio = "estandar"
    programado_para: Optional[datetime] = None


class CotizacionResponse(BaseModel):
    distancia_km: float
    tiempo_min: float
    peso_cobrable_kg: float
    subtotal: float
    multiplicador_servicio: float
    recargo_horario_pct: float
    total: float
    moneda: str
