from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class ClienteDireccionBase(BaseModel):
    direccion_texto: str
    ciudad: Optional[str] = None
    estado: Optional[str] = None
    cp: Optional[str] = None
    es_principal: bool = False
    
class ClienteDireccionCreate(ClienteDireccionBase):
    latitud: float = Field(..., description="Latitud (escala -90 a 90)")
    longitud: float = Field(..., description="Longitud (escala -180 a 180)")

class ClienteDireccionResponse(ClienteDireccionBase):
    id: int
    geom_geojson: Optional[dict] = None
    
    class Config:
        from_attributes = True

class ClienteBase(BaseModel):
    nombre: str
    email: EmailStr
    telefono: Optional[str] = None
    atencion_nam: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    atencion_nam: Optional[str] = None

class ClienteResponse(ClienteBase):
    id: int
    is_active: bool
    created_at: datetime
    direcciones: List[ClienteDireccionResponse] = []
    
    class Config:
        from_attributes = True
