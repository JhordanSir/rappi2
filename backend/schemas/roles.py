from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PermisoBase(BaseModel):
    recurso: str
    accion: str


class PermisoCreate(PermisoBase):
    pass


class PermisosBulkSet(BaseModel):
    """Reemplaza el conjunto completo de permisos de un rol (multiselección: agrega y
    quita en una sola operación). El backend calcula el diff contra lo existente."""
    permisos: List[PermisoBase] = []


class PermisoResponse(PermisoBase):
    id: int
    rol_id: int

    model_config = ConfigDict(from_attributes=True)


class RolBase(BaseModel):
    nombre: str


class RolCreate(RolBase):
    pass


class RolUpdate(BaseModel):
    nombre: Optional[str] = None


class RolResponse(RolBase):
    id: int
    permisos: List[PermisoResponse] = []

    model_config = ConfigDict(from_attributes=True)
