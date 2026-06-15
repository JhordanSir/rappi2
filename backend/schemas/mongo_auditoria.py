from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditoriaOut(BaseModel):
    id: str
    usuario_id: Optional[int] = None
    ruta: str
    metodo: str
    ip: Optional[str] = None
    status_code: int
    payload_hash: Optional[str] = None
    timestamp: datetime
