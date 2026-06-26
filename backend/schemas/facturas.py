import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

_RUC_RE = re.compile(r"^\d{11}$")


def _validar_ruc(v: Optional[str]) -> Optional[str]:
    """RUC opcional: vacío => None; si viene, exactamente 11 dígitos numéricos."""
    if v is None:
        return v
    v = v.strip()
    if v == "":
        return None
    if not _RUC_RE.match(v):
        raise ValueError("El RUC debe tener exactamente 11 dígitos numéricos")
    return v


class FacturaBase(BaseModel):
    ruc: Optional[str] = None
    monto: Decimal
    url: Optional[str] = None


class FacturaCreate(FacturaBase):
    @field_validator("ruc")
    @classmethod
    def _check_ruc(cls, v: Optional[str]) -> Optional[str]:
        return _validar_ruc(v)


class FacturaUpdate(BaseModel):
    ruc: Optional[str] = None
    monto: Optional[Decimal] = None
    url: Optional[str] = None

    @field_validator("ruc")
    @classmethod
    def _check_ruc(cls, v: Optional[str]) -> Optional[str]:
        return _validar_ruc(v)


class FacturaResponse(FacturaBase):
    id: int
    orden_id: int
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class RucConsultaResponse(BaseModel):
    """Resultado de validar un RUC (formato/dígito + estado en SUNAT si hay proveedor)."""
    ruc: str
    razon_social: Optional[str] = None
    estado: Optional[str] = None
    condicion: Optional[str] = None
    activo: Optional[bool] = None
    verificado_sunat: bool = False
