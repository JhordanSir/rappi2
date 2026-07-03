"""Validación de access tokens emitidos por Keycloak (OIDC).

El frontend autentica contra Keycloak (Authorization Code + PKCE) y envía el access
token (RS256) en `Authorization: Bearer`. Aquí lo validamos contra el JWKS público de
Keycloak: firma, emisor (`iss`), audiencia (`aud`) y expiración. El backend NO firma ni
emite tokens propios.

El JWKS se cachea en memoria y se refresca si aparece un `kid` desconocido (rotación de
llaves) o al expirar el TTL.
"""
import time
from typing import Any, Dict, List, Optional

import httpx
from jose import jwt
from jose.exceptions import JWTError

from core.config import settings

# Roles base de la aplicación. Keycloak puede traer roles propios (offline_access,
# uma_authorization, default-roles-*) que ignoramos. Los roles PERSONALIZADOS creados
# en "Roles & Permisos" (Despachador, Auditor…) también son válidos: los llamadores
# pasan el catálogo vigente de la BD en `validos`.
APP_ROLES = ("Admin", "Conductor", "Cliente")

_JWKS_TTL_SECONDS = 3600
_jwks_cache: Dict[str, Any] = {"fetched_at": 0.0, "keys": {}}


async def _fetch_jwks() -> Dict[str, Dict[str, Any]]:
    """Descarga el JWKS de Keycloak y lo indexa por `kid`."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.keycloak_jwks_url)
        resp.raise_for_status()
        data = resp.json()
    keys = {k["kid"]: k for k in data.get("keys", []) if "kid" in k}
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = time.monotonic()
    return keys


async def _get_signing_key(kid: str) -> Optional[Dict[str, Any]]:
    """Devuelve la JWK para `kid`, refrescando el cache si hace falta."""
    keys = _jwks_cache["keys"]
    fresh = (time.monotonic() - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS
    if keys and fresh and kid in keys:
        return keys[kid]
    # Cache vacío/viejo o kid desconocido (posible rotación): refrescar una vez.
    keys = await _fetch_jwks()
    return keys.get(kid)


async def validate_token(token: str) -> Dict[str, Any]:
    """Valida el access token de Keycloak y devuelve sus claims.

    Lanza `jose.exceptions.JWTError` (o subclase) si el token es inválido, está
    expirado, o tiene firma/emisor/audiencia incorrectos.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise
    kid = header.get("kid")
    if not kid:
        raise JWTError("Token sin 'kid' en la cabecera")

    key = await _get_signing_key(kid)
    if key is None:
        raise JWTError("No se encontró la llave de firma (kid desconocido)")

    audience = settings.KEYCLOAK_AUDIENCE or None
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=settings.keycloak_issuer,
        audience=audience,
        options={
            "verify_aud": bool(audience),
            "verify_signature": True,
            "verify_exp": True,
        },
    )


def roles_de(claims: Dict[str, Any], validos: Optional[set] = None) -> List[str]:
    """Roles de la app presentes en el token (`realm_access.roles`).

    `validos` amplía el catálogo con los roles personalizados de la BD; sin él solo
    se reconocen los roles base (compatibilidad).
    """
    permitidos = set(APP_ROLES) | (validos or set())
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    return [r for r in realm_roles if r in permitidos]


def rol_principal(claims: Dict[str, Any], validos: Optional[set] = None) -> str:
    """Rol efectivo del usuario cuando el token trae varios.

    Precedencia: Admin > rol staff personalizado (≠ Cliente/Conductor) > Conductor >
    Cliente. Sin ningún rol reconocido, por defecto 'Cliente'.
    """
    roles = set(roles_de(claims, validos))
    if "Admin" in roles:
        return "Admin"
    personalizados = sorted(r for r in roles if r not in APP_ROLES)
    if personalizados:
        return personalizados[0]
    if "Conductor" in roles:
        return "Conductor"
    return "Cliente"


def actor_de(claims: Dict[str, Any]) -> Optional[str]:
    """Identificador legible para auditoría (`preferred_username` o `email`)."""
    return claims.get("preferred_username") or claims.get("email")
