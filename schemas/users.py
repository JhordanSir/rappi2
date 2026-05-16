from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UsuarioBase(BaseModel):
    username: str
    email: EmailStr

class UsuarioCreate(UsuarioBase):
    password: str
    rol_id: Optional[int] = 1

class UsuarioResponse(UsuarioBase):
    id: int
    rol_id: Optional[int]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True
