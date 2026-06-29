from typing import Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import DisponibilidadConductor
from schemas.vehiculos import VehiculoResponse


class UsuarioRef(BaseModel):
    """Resumen del usuario enlazado a un conductor (para trazabilidad en el panel)."""
    id: int
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ConductorBase(BaseModel):
    nombre: str
    licencia: str
    disponibilidad: DisponibilidadConductor = "Disponible"


class ConductorCreate(ConductorBase):
    usuario_id: int
    vehiculo_placa: Optional[str] = None


class ConductorUpdate(BaseModel):
    nombre: Optional[str] = None
    disponibilidad: Optional[DisponibilidadConductor] = None
    vehiculo_placa: Optional[str] = None
    activo: Optional[bool] = None


class AsignarVehiculoRequest(BaseModel):
    vehiculo_placa: Optional[str] = None


class ConductorResponse(ConductorBase):
    id: int
    usuario_id: int
    vehiculo_placa: Optional[str] = None
    activo: bool
    vehiculo: Optional[VehiculoResponse] = None
    usuario: Optional[UsuarioRef] = None

    model_config = ConfigDict(from_attributes=True)
