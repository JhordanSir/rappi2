from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PermisoBase(BaseModel):
    recurso: str
    accion: str


class PermisoCreate(PermisoBase):
    pass


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
