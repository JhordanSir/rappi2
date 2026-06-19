from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class TarifaConfigUpdate(BaseModel):
    """Campos editables de la tarifa. Todos opcionales: se actualiza solo lo enviado."""
    moneda: Optional[str] = None
    tarifa_base: Optional[Decimal] = None
    precio_km: Optional[Decimal] = None
    precio_min: Optional[Decimal] = None
    precio_kg: Optional[Decimal] = None
    factor_volumetrico: Optional[int] = None
    minimo: Optional[Decimal] = None
    mult_estandar: Optional[Decimal] = None
    mult_express: Optional[Decimal] = None
    mult_urgente: Optional[Decimal] = None
    recargo_nocturno_pct: Optional[Decimal] = None
    nocturno_desde: Optional[int] = None
    nocturno_hasta: Optional[int] = None
    recargo_pico_pct: Optional[Decimal] = None
    pico_ventanas: Optional[List[List[int]]] = None
    recargo_finde_pct: Optional[Decimal] = None


class TarifaConfigResponse(BaseModel):
    id: int
    moneda: str
    tarifa_base: Decimal
    precio_km: Decimal
    precio_min: Decimal
    precio_kg: Decimal
    factor_volumetrico: int
    minimo: Decimal
    mult_estandar: Decimal
    mult_express: Decimal
    mult_urgente: Decimal
    recargo_nocturno_pct: Decimal
    nocturno_desde: int
    nocturno_hasta: int
    recargo_pico_pct: Decimal
    pico_ventanas: List[List[int]]
    recargo_finde_pct: Decimal
    actualizado_en: datetime

    model_config = ConfigDict(from_attributes=True)
