from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Rappi2"
    DATABASE_URL: str
    MONGO_URL: str
    MONGO_DB: str = "rappi2_mongo"
    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ORS_API_KEY: str = "your_ors_api_key_here"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
