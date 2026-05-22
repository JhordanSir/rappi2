from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import EstadoPago


class PagoBase(BaseModel):
    monto: Decimal
    estado: EstadoPago = "Pendiente"
    referencia_banco: Optional[str] = None


class PagoCreate(PagoBase):
    pass


class PagoUpdate(BaseModel):
    estado: Optional[EstadoPago] = None
    referencia_banco: Optional[str] = None


class PagoResponse(PagoBase):
    id: int
    orden_id: int
    fecha_pago: datetime

    model_config = ConfigDict(from_attributes=True)
