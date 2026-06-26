"""Verificación de ID tokens de Google (Sign in with Google).

El frontend obtiene un ID token (credential) mediante Google Identity Services y lo
envía al backend. Aquí lo validamos contra los certificados de Google (firma, emisor,
audiencia == GOOGLE_CLIENT_ID y expiración) y devolvemos el payload (idinfo).
"""
from typing import Any, Dict

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from core.config import settings

# Emisores válidos para los ID tokens de Google.
_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def verify_google_id_token(credential: str) -> Dict[str, Any]:
    """Valida el ID token de Google y devuelve su payload.

    Lanza ValueError si el token es inválido, expiró, tiene una audiencia/emisor
    incorrectos o si Google OAuth no está configurado.

    Nota: hace una llamada de red (síncrona) para obtener los certificados de Google;
    invócalo desde código async con run_in_threadpool / asyncio.to_thread.
    """
    if not settings.google_enabled:
        raise ValueError("Google OAuth no está configurado (GOOGLE_CLIENT_ID vacío)")

    idinfo = google_id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )

    if idinfo.get("iss") not in _ISSUERS:
        raise ValueError("Emisor del token inválido")

    return idinfo
