from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import TipoGeocerca


class GPSPingIn(BaseModel):
    asignacion_id: int
    conductor_id: int
    vehiculo_placa: str
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    speed_kmh: Optional[float] = None
    heading: Optional[float] = Field(None, ge=0, le=360)
    accuracy_m: Optional[float] = None
    timestamp: Optional[datetime] = None


class GPSPingOut(BaseModel):
    id: str
    asignacion_id: int
    conductor_id: int
    vehiculo_placa: str
    location: Dict[str, Any]
    speed_kmh: Optional[float] = None
    heading: Optional[float] = None
    accuracy_m: Optional[float] = None
    timestamp: datetime

    model_config = ConfigDict(arbitrary_types_allowed=True)


class GeocercaIn(BaseModel):
    ruta_id: Optional[int] = None
    orden_id: Optional[int] = None
    tipo: TipoGeocerca
    coordinates: List[List[List[float]]] = Field(..., description="Polygon coordinates [[[lon,lat],...]]")
    tolerance_m: Optional[int] = None
    activa: bool = True


class GeocercaUpdate(BaseModel):
    tipo: Optional[TipoGeocerca] = None
    coordinates: Optional[List[List[List[float]]]] = None
    tolerance_m: Optional[int] = None
    activa: Optional[bool] = None


class GeocercaOut(BaseModel):
    id: str
    ruta_id: Optional[int] = None
    orden_id: Optional[int] = None
    tipo: TipoGeocerca
    geometry: Dict[str, Any]
    tolerance_m: Optional[int] = None
    activa: bool
    created_at: datetime
