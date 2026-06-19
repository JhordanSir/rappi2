"""Cliente mínimo de MercadoPago Checkout Pro (vía REST con httpx).

Solo se usa cuando hay credenciales (settings.mp_enabled). El endpoint de checkout
decide entre la pasarela real y el modo simulado.
"""
import logging

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_API = "https://api.mercadopago.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}", "Content-Type": "application/json"}


async def crear_preferencia(orden_id: int, monto: float, descripcion: str) -> dict:
    """Crea una preferencia de pago y devuelve {init_point, preference_id}."""
    back = f"{settings.FRONTEND_BASE_URL}/pago"
    body = {
        "items": [
            {
                "title": descripcion,
                "quantity": 1,
                "currency_id": settings.MONEDA,
                "unit_price": round(float(monto), 2),
            }
        ],
        "external_reference": str(orden_id),
        "back_urls": {
            "success": f"{back}/exito?orden={orden_id}",
            "failure": f"{back}/fallo?orden={orden_id}",
            "pending": f"{back}/pendiente?orden={orden_id}",
        },
        "auto_return": "approved",
        "notification_url": f"{settings.PUBLIC_BASE_URL}/api/pagos/webhook/mercadopago",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{_API}/checkout/preferences", json=body, headers=_headers())
        r.raise_for_status()
        data = r.json()
    return {
        "preference_id": data.get("id"),
        "init_point": data.get("init_point") or data.get("sandbox_init_point"),
    }


async def obtener_pago(payment_id: str) -> dict:
    """Consulta el estado de un pago en MercadoPago."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{_API}/v1/payments/{payment_id}", headers=_headers())
        r.raise_for_status()
        return r.json()
