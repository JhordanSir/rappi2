from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FacturaBase(BaseModel):
    ruc: Optional[str] = None
    monto: Decimal
    url: Optional[str] = None


class FacturaCreate(FacturaBase):
    pass


class FacturaUpdate(BaseModel):
    ruc: Optional[str] = None
    monto: Optional[Decimal] = None
    url: Optional[str] = None


class FacturaResponse(FacturaBase):
    id: int
    orden_id: int
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)
