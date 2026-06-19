from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Rappi2"
    DATABASE_URL: str
    MONGO_URL: str
    MONGO_DB: str = "rappi2_mongo"

    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AUDIT_ENABLED: bool = True

    # Redis: backplane pub/sub para los eventos de tiempo real (SSE) entre workers.
    REDIS_URL: str = "redis://redis:6379/0"

    # Retención de pings GPS: TTL en la colección gps_tracking para que no crezca
    # sin límite en producción (0 = sin expiración, conservar todo).
    GPS_TRACKING_RETENCION_DIAS: int = 30

    ORS_API_KEY: str = "your_ors_api_key_here"
    GEOCODING_ENABLED: bool = True

    # Ruteo por calles (OSRM, sin API key) y autogeneración de rutas al crear órdenes
    OSRM_URL: str = "https://router.project-osrm.org"
    RUTA_AUTOGENERAR: bool = True

    # MercadoPago (Checkout Pro, sandbox). Si MP_ACCESS_TOKEN está vacío, el checkout
    # opera en "modo simulado" (confirma el pago localmente) para poder probar el flujo
    # sin llaves; al cargar las llaves de prueba, se activa la pasarela real.
    MP_ACCESS_TOKEN: str = ""
    MP_PUBLIC_KEY: str = ""
    MP_WEBHOOK_SECRET: str = ""
    MONEDA: str = "PEN"
    # Base pública del backend (para notification_url del webhook) y del frontend
    # (para las back_urls de retorno tras pagar).
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    CORS_ORIGINS: List[str] = ["*"]

    @property
    def mp_enabled(self) -> bool:
        return bool(self.MP_ACCESS_TOKEN)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
