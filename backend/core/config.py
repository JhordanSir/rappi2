import json
from typing import Annotated, List

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Rappi2"
    DATABASE_URL: str
    MONGO_URL: str
    MONGO_DB: str = "rappi2_mongo"

    # --- Autenticación: Keycloak (OIDC) ---
    # El backend ya NO emite ni firma tokens propios: valida los access tokens (RS256)
    # emitidos por Keycloak contra su JWKS. PUBLIC_URL es la URL que ve el navegador y
    # con la que se firma el `iss` del token; INTERNAL_URL es cómo alcanza el backend a
    # Keycloak dentro de la red (Docker) para descargar el JWKS. En dev suelen diferir
    # (localhost:8080 vs keycloak:8080); en un host único pueden ser iguales.
    KEYCLOAK_PUBLIC_URL: str = "http://localhost:8080"
    KEYCLOAK_INTERNAL_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "rappi2"
    KEYCLOAK_CLIENT_ID: str = "rappi2-frontend"
    # Audiencia esperada en el token (la añade el mapper del cliente en Keycloak).
    KEYCLOAK_AUDIENCE: str = "rappi2-backend"

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

    # --- Validación de RUC (SUNAT) ---
    # Antes de registrar/validar una factura con RUC, se valida formato + dígito
    # verificador y, si hay proveedor configurado, se consulta su estado (ACTIVO/HABIDO).
    # SUNAT no expone una API pública directa: se usa un proveedor de "consulta RUC"
    # (p. ej. apis.net.pe, apisperu). Si SUNAT_API_URL está vacío, solo se valida el
    # formato/dígito verificador (sin consulta externa).
    SUNAT_ENABLED: bool = True
    SUNAT_API_URL: str = ""          # admite placeholder {ruc}; si no, se añade ?numero=
    SUNAT_API_TOKEN: str = ""        # se envía como Bearer si está presente
    SUNAT_TIMEOUT: float = 6.0
    # Si el proveedor no responde: True = no bloquear la factura (registra advertencia);
    # False = rechazar (502). El formato/dígito verificador siempre se exige.
    SUNAT_FALLO_ABIERTO: bool = True

    # Base pública del backend (para notification_url del webhook) y del frontend
    # (para las back_urls de retorno tras pagar).
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # NoDecode evita que pydantic-settings haga json.loads() sobre el valor del entorno
    # antes de validarlo; así `_split_origins` recibe el texto crudo y aceptamos tanto
    # JSON (["a","b"]) como coma-separado (a,b) o un solo origen (https://app...).
    CORS_ORIGINS: Annotated[List[str], NoDecode] = ["*"]

    @property
    def mp_enabled(self) -> bool:
        return bool(self.MP_ACCESS_TOKEN)

    @property
    def sunat_provider_enabled(self) -> bool:
        """True si hay un proveedor de consulta RUC configurado (consulta externa)."""
        return self.SUNAT_ENABLED and bool(self.SUNAT_API_URL)

    @property
    def keycloak_issuer(self) -> str:
        """Emisor esperado del token (`iss`), tal como lo firma Keycloak para el navegador."""
        return f"{self.KEYCLOAK_PUBLIC_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_url(self) -> str:
        """URL del JWKS, alcanzable desde el backend (red interna)."""
        return (
            f"{self.KEYCLOAK_INTERNAL_URL.rstrip('/')}"
            f"/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"
        )

    @property
    def keycloak_authorization_url(self) -> str:
        """Endpoint de autorización (público) para la integración OAuth de /docs."""
        return f"{self.keycloak_issuer}/protocol/openid-connect/auth"

    @property
    def keycloak_token_url(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/token"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):  # formato JSON: ["https://a","https://b"]
                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
