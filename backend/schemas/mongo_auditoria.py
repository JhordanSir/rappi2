from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditoriaOut(BaseModel):
    id: str
    # Actor = username de Keycloak (preferred_username) o email; None si anónimo.
    actor: Optional[str] = None
    ruta: str
    metodo: str
    ip: Optional[str] = None
    status_code: int
    payload_hash: Optional[str] = None
    timestamp: datetime
