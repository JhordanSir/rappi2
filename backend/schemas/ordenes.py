from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import EstadoOrden, lat_field, lon_field

NivelServicio = Literal["estandar", "express", "urgente"]


class PaqueteFields(BaseModel):
    """Datos del paquete que alimentan el cálculo de precio (viven por destino)."""
    peso_kg: Optional[float] = None
    largo_cm: Optional[float] = None
    ancho_cm: Optional[float] = None
    alto_cm: Optional[float] = None


class PaqueteFieldsDeprecated(BaseModel):
    """Paquete a nivel de orden: DEPRECATED. El paquete real vive en `destinos[].*`.

    Se mantiene solo por compatibilidad con POST/cotizaciones legacy de un único destino: si
    llegan sin `destinos`, se pliegan a un destino (ver `_normalizar_destinos`). No usar en
    integraciones nuevas.
    """
    peso_kg: Optional[float] = Field(None, deprecated=True, description="DEPRECATED: usa destinos[].peso_kg")
    largo_cm: Optional[float] = Field(None, deprecated=True, description="DEPRECATED: usa destinos[].largo_cm")
    ancho_cm: Optional[float] = Field(None, deprecated=True, description="DEPRECATED: usa destinos[].ancho_cm")
    alto_cm: Optional[float] = Field(None, deprecated=True, description="DEPRECATED: usa destinos[].alto_cm")


class DestinoIn(PaqueteFields):
    # Opcional para permitir cotizar solo con coordenadas; al crear, se exige dirección.
    direccion: Optional[str] = None
    distrito: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    nombre_destinatario: Optional[str] = None


class DestinoUpdate(DestinoIn):
    """Edición parcial de un destino existente (dirección y/o datos del paquete).
    Todos los campos son opcionales: solo se aplica lo enviado."""


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


class OrdenCreate(PaqueteFieldsDeprecated):
    # Opcional: el rol Cliente NO lo envía (el endpoint lo fuerza desde su token);
    # el staff sí debe indicarlo (si falta/es inválido → 400 en create_orden).
    # Con `int` obligatorio, Pydantic respondía 422 a todo cliente antes de llegar
    # al override — el "Nuevo envío" del cliente estaba roto.
    cliente_id: Optional[int] = None
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
    # El paquete NO se edita a nivel de orden: usar PATCH /ordenes/{id}/destinos/{destino_id}.
    nivel_servicio: Optional[NivelServicio] = None
    programado_para: Optional[datetime] = None
    ajuste_monto: Optional[Decimal] = None
    ajuste_motivo: Optional[str] = None


class OrdenResponse(BaseModel):
    # El paquete físico (peso/dimensiones) vive por destino (ver DestinoOut). A nivel de orden
    # solo se expone el AGREGADO derivado `peso_total_kg` (calculado con @hybrid_property sobre
    # los destinos; no persistido). El peso cobrable (volumétrico) se expone en la cotización.
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
    # Agregados derivados de los destinos (@hybrid_property en el modelo Orden).
    peso_total_kg: Optional[Decimal] = None
    volumen_total_cm3: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class CotizarRequest(PaqueteFieldsDeprecated):
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
