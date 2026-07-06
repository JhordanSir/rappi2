"""Verifica que TODOS los endpoints exigen el token de Keycloak.

Recorre las rutas registradas en la app (por lo que cubre automáticamente los
endpoints que se agreguen a futuro) y comprueba que sin `Authorization` —o con un
token corrupto— responden 401. Ninguna de las dos variantes toca Keycloak: sin
cabecera corta `oauth2_scheme` (auto_error) y con token corrupto falla el parseo
del JWT antes de consultar el JWKS, así que el test es hermético.
"""
import re

import pytest
from fastapi.routing import APIRoute

from api.dependencies import get_current_user
from main import app

# Únicos endpoints sin Bearer por cabecera, cada uno con su razón:
# - "/" y "/health": informativos, para orquestadores; no exponen datos.
# - webhook MercadoPago: lo llama MP (externo), no puede portar token de Keycloak.
# - /realtime/stream: EventSource no envía cabeceras; el token viaja por query y se
#   valida igual (ver test_stream_rechaza_token_invalido).
PUBLICAS = {
    ("GET", "/"),
    ("GET", "/health"),
    ("POST", "/api/pagos/webhook/mercadopago"),
    ("GET", "/api/realtime/stream"),
}


def _api_routes(routes, prefix=""):
    """Aplana el árbol de rutas. Desde FastAPI 0.138 `include_router` ya no copia
    las rutas al app: las envuelve en `_IncludedRouter`, así que hay que descender
    a `original_router.routes` acumulando el prefijo del include."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif type(route).__name__ == "_IncludedRouter":
            ctx = route.include_context
            yield from _api_routes(ctx.included_router.routes, prefix + ctx.prefix)
        # el resto (Route de /docs, /openapi.json, estáticos) no lleva auth propia


def _rutas_protegidas():
    for path, route in _api_routes(app.routes):
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            if (method, path) in PUBLICAS:
                continue
            # Path params con un valor inocuo: la auth corre antes que cualquier
            # validación/consulta, así que no hace falta que el recurso exista.
            yield method, re.sub(r"\{[^}]+\}", "1", path), path


@pytest.fixture
async def sin_override_de_auth():
    """Restaura la autenticación REAL (el conftest la sobreescribe con un admin)."""
    override = app.dependency_overrides.pop(get_current_user, None)
    yield
    if override is not None:
        app.dependency_overrides[get_current_user] = override


def _rutas_o_falla():
    rutas = list(_rutas_protegidas())
    # Salvaguarda contra un pase en vacío: si un cambio de FastAPI vuelve a alterar
    # la estructura de app.routes, este assert delata que no se encontró nada.
    assert len(rutas) > 50, f"Solo se encontraron {len(rutas)} rutas; ¿cambió FastAPI?"
    return rutas


async def test_todos_los_endpoints_rechazan_sin_token(client, sin_override_de_auth):
    fallas = []
    for method, url, path in _rutas_o_falla():
        resp = await client.request(method, url)
        if resp.status_code != 401:
            fallas.append(f"{method} {path} -> {resp.status_code}")
    assert not fallas, "Endpoints accesibles sin token:\n" + "\n".join(fallas)


async def test_todos_los_endpoints_rechazan_token_invalido(client, sin_override_de_auth):
    headers = {"Authorization": "Bearer no-es-un-jwt"}
    fallas = []
    for method, url, path in _rutas_o_falla():
        resp = await client.request(method, url, headers=headers)
        if resp.status_code != 401:
            fallas.append(f"{method} {path} -> {resp.status_code}")
    assert not fallas, "Endpoints accesibles con token inválido:\n" + "\n".join(fallas)


async def test_stream_rechaza_token_invalido(client, sin_override_de_auth):
    resp = await client.get("/api/realtime/stream", params={"token": "no-es-un-jwt"})
    assert resp.status_code == 401
