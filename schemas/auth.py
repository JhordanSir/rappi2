from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    rol_id: Optional[int] = None
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    cc_id: Optional[str] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenInfo(BaseModel):
    id: int
    usuario_id: int
    fecha_expiracion: datetime
    revocado: bool

    model_config = ConfigDict(from_attributes=True)
