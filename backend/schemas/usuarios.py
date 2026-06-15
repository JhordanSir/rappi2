from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from schemas.roles import RolResponse


class UsuarioBase(BaseModel):
    username: str
    email: EmailStr
    rol_id: int


class UsuarioCreate(UsuarioBase):
    password: str
    cliente_id: Optional[int] = None


class UsuarioUpdate(BaseModel):
    email: Optional[EmailStr] = None
    rol_id: Optional[int] = None
    activo: Optional[bool] = None
    password: Optional[str] = None


class UsuarioResponse(UsuarioBase):
    id: int
    cliente_id: Optional[int] = None
    activo: bool
    fecha_registro: datetime
    rol: Optional[RolResponse] = None

    model_config = ConfigDict(from_attributes=True)
