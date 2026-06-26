"""Validación de RUC contra SUNAT (o un proveedor de consulta RUC).

Antes de registrar/validar una factura con RUC, el sistema valida:
  1. **Formato + dígito verificador** (módulo 11) — siempre, sin red.
  2. **Estado del contribuyente** (ACTIVO/HABIDO) — si hay proveedor configurado
     (`SUNAT_API_URL`); SUNAT no expone una API pública directa, por eso se consulta
     un proveedor secundario (apis.net.pe, apisperu, etc.).

Si el proveedor no responde, el comportamiento lo decide `SUNAT_FALLO_ABIERTO`
(no bloquear vs. rechazar). Las dos excepciones públicas las traduce la capa API a
códigos HTTP claros (422 RUC inválido/no activo, 502 proveedor caído con fallo cerrado).
"""
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_RUC_RE = re.compile(r"^\d{11}$")
# Pesos del algoritmo módulo 11 para el dígito verificador del RUC (primeros 10 dígitos).
_PESOS = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


class RucInvalido(ValueError):
    """RUC con formato/dígito verificador inválido, o no activo/habido en SUNAT."""


class SunatNoDisponible(RuntimeError):
    """El proveedor de consulta RUC no respondió (timeout o error de red/HTTP)."""


@dataclass
class RucInfo:
    ruc: str
    razon_social: Optional[str] = None
    estado: Optional[str] = None      # p. ej. "ACTIVO"
    condicion: Optional[str] = None   # p. ej. "HABIDO"
    activo: Optional[bool] = None     # None = no se consultó al proveedor
    verificado_sunat: bool = False    # True si la respuesta vino del proveedor


def ruc_checksum_valido(ruc: str) -> bool:
    """Valida formato (11 dígitos) y dígito verificador (módulo 11) del RUC."""
    if not _RUC_RE.match(ruc or ""):
        return False
    suma = sum(int(ruc[i]) * _PESOS[i] for i in range(10))
    resto = suma % 11
    dig = 11 - resto
    if dig == 10:
        dig = 0
    elif dig == 11:
        dig = 1
    return dig == int(ruc[10])


def _extraer(data: Dict[str, Any], *claves: str) -> Optional[str]:
    """Primer valor no vacío entre varias claves posibles (proveedores difieren)."""
    for k in claves:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


async def _consultar_proveedor(ruc: str) -> Dict[str, Any]:
    """Consulta el proveedor de RUC. Lanza SunatNoDisponible ante timeout/error."""
    url = settings.SUNAT_API_URL
    params = None
    if "{ruc}" in url:
        url = url.replace("{ruc}", ruc)
    else:
        params = {"numero": ruc}
    headers = {}
    if settings.SUNAT_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.SUNAT_API_TOKEN}"
    try:
        async with httpx.AsyncClient(timeout=settings.SUNAT_TIMEOUT) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:  # red, status!=2xx, JSON inválido
        raise SunatNoDisponible(str(exc)) from exc


async def validar_ruc(ruc: str) -> RucInfo:
    """Valida un RUC. Lanza RucInvalido si el formato/dígito o el estado son inválidos;
    SunatNoDisponible si el proveedor falla y `SUNAT_FALLO_ABIERTO` es False."""
    ruc = (ruc or "").strip()
    if not ruc_checksum_valido(ruc):
        raise RucInvalido("RUC inválido: formato o dígito verificador incorrecto")

    info = RucInfo(ruc=ruc)
    if not settings.sunat_provider_enabled:
        return info  # solo validación de formato/dígito (sin consulta externa)

    try:
        data = await _consultar_proveedor(ruc)
    except SunatNoDisponible as exc:
        if settings.SUNAT_FALLO_ABIERTO:
            logger.warning("Consulta RUC %s falló (se permite por fallo-abierto): %s", ruc, exc)
            return info
        raise

    info.razon_social = _extraer(data, "razonSocial", "razon_social", "nombre", "name")
    info.estado = _extraer(data, "estado", "estadoContribuyente", "status")
    info.condicion = _extraer(data, "condicion", "condicionDomicilio", "condition")
    info.verificado_sunat = True
    info.activo = bool(info.estado and info.estado.upper().startswith("ACTIVO"))

    if not info.activo:
        raise RucInvalido(
            f"El RUC {ruc} no está ACTIVO en SUNAT"
            + (f" (estado: {info.estado})" if info.estado else "")
        )
    return info
