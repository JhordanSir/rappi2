import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common import EstadoVehiculo

# Formato de placa esperado: 3 letras, guion, 3 dígitos (p. ej. AQP-101).
PLACA_RE = re.compile(r"^[A-Z]{3}-\d{3}$")


class VehiculoBase(BaseModel):
    placa: str
    tipo: str
    capacidad_kg: Decimal
    largo_cm: Optional[Decimal] = None
    ancho_cm: Optional[Decimal] = None
    alto_cm: Optional[Decimal] = None
    estado: EstadoVehiculo = "Operativo"
    fecha_mantenimiento: Optional[datetime] = None


class VehiculoCreate(VehiculoBase):
    # Dimensiones útiles de carga obligatorias al dar de alta (para validar el cubicaje en
    # asignaciones). En edición (VehiculoUpdate) siguen siendo opcionales.
    largo_cm: Decimal = Field(gt=0)
    ancho_cm: Decimal = Field(gt=0)
    alto_cm: Decimal = Field(gt=0)

    # El validador va solo en creación (no en VehiculoResponse) para no romper
    # la serialización de placas históricas que no cumplan el formato.
    @field_validator("placa")
    @classmethod
    def _validar_placa(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not PLACA_RE.match(v):
            raise ValueError("La placa debe tener el formato ABC-123 (3 letras, guion, 3 dígitos)")
        return v


class VehiculoUpdate(BaseModel):
    tipo: Optional[str] = None
    capacidad_kg: Optional[Decimal] = None
    largo_cm: Optional[Decimal] = None
    ancho_cm: Optional[Decimal] = None
    alto_cm: Optional[Decimal] = None
    estado: Optional[EstadoVehiculo] = None
    fecha_mantenimiento: Optional[datetime] = None
    activo: Optional[bool] = None


class VehiculoResponse(VehiculoBase):
    activo: bool

    model_config = ConfigDict(from_attributes=True)
