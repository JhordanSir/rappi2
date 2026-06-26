from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class RegisterRequest(BaseModel):
    # Registro publico: SIEMPRE crea un usuario con rol "Cliente". No se acepta
    # rol_id del cliente para evitar escalada de privilegios (las cuentas de staff
    # se crean desde /api/usuarios por un Admin).
    username: str
    email: EmailStr
    password: str
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    cc_id: Optional[str] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class GoogleLoginRequest(BaseModel):
    # ID token (credential) emitido por Google Identity Services en el frontend.
    credential: str


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
