import hashlib
import logging
from typing import Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.config import settings
from core.mongo import get_database
from services.keycloak import actor_de, validate_token
from services.mongo import auditoria_service

logger = logging.getLogger(__name__)

RUTAS_EXCLUIDAS: Set[str] = {"/", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}


async def _extraer_actor(authorization: Optional[str]) -> Optional[str]:
    """Identidad del actor (username de Keycloak) para auditoría; best-effort.

    Valida el Bearer contra Keycloak. Devuelve None si no hay token o es inválido (el
    control de acceso real lo hace get_current_user en cada endpoint)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = await validate_token(token)
        return actor_de(claims)
    except Exception:
        return None


def _ip_cliente(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # El stream SSE es una conexión persistente: no se audita (no aporta y evita
        # mantener viva la cadena del middleware durante toda la conexión).
        if (
            not settings.AUDIT_ENABLED
            or path in RUTAS_EXCLUIDAS
            or path.startswith("/static")
            or path.startswith("/api/realtime")
        ):
            return await call_next(request)

        actor = await _extraer_actor(request.headers.get("authorization"))
        ip = _ip_cliente(request)
        metodo = request.method

        body = b""
        if metodo in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body = await request.body()
            except Exception:
                body = b""
        payload_hash = hashlib.sha256(body[:1024]).hexdigest() if body else None

        response: Response = await call_next(request)

        try:
            db = get_database()
            await auditoria_service.registrar(
                db,
                actor=actor,
                ruta=path,
                metodo=metodo,
                ip=ip,
                status_code=response.status_code,
                payload_hash=payload_hash,
            )
        except Exception as exc:
            logger.warning("AuditMiddleware no pudo registrar evento: %s", exc)

        return response
