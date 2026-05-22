from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from schemas.common import TipoDestinatario


class NotificacionIn(BaseModel):
    destinatario_tipo: TipoDestinatario
    destinatario_id: int
    tipo: str
    titulo: str
    mensaje: str
    metadata: Dict[str, Any] = {}


class NotificacionOut(NotificacionIn):
    id: str
    leida: bool
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)
