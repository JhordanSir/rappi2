from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from schemas.common import lat_field, lon_field


class ClienteDireccionBase(BaseModel):
    direccion: str
    distrito: Optional[str] = None
    ciudad: Optional[str] = None
    estado: Optional[str] = None
    pais: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    es_principal: bool = False


class ClienteDireccionCreate(ClienteDireccionBase):
    pass


class ClienteDireccionUpdate(BaseModel):
    direccion: Optional[str] = None
    distrito: Optional[str] = None
    ciudad: Optional[str] = None
    estado: Optional[str] = None
    pais: Optional[str] = None
    lat: Optional[float] = lat_field()
    lon: Optional[float] = lon_field()
    es_principal: Optional[bool] = None


class ClienteDireccionResponse(ClienteDireccionBase):
    id: int
    cliente_id: int

    model_config = ConfigDict(from_attributes=True)


class ClienteBase(BaseModel):
    nombre: str
    email: EmailStr
    telefono: Optional[str] = None
    cc_id: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    cc_id: Optional[str] = None
    activo: Optional[bool] = None


class ClienteResponse(ClienteBase):
    id: int
    activo: bool
    fecha_registro: datetime
    direcciones: List[ClienteDireccionResponse] = []

    model_config = ConfigDict(from_attributes=True)
