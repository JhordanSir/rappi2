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

    ORS_API_KEY: str = "your_ors_api_key_here"
    GEOCODING_ENABLED: bool = True

    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
