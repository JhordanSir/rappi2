"""Cliente mínimo de la Admin API de Keycloak para gestionar usuarios DESDE la app.

La pantalla "Usuarios" crea/edita usuarios EN Keycloak (el proveedor de identidad
único): crear aquí un usuario local sin su par en Keycloak produciría cuentas
huérfanas que no pueden iniciar sesión.

Autenticación: password grant del admin del realm `master` (client `admin-cli`),
con las credenciales KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD del entorno. El token
se cachea hasta poco antes de expirar. Si Keycloak no está disponible o faltan las
credenciales, cada operación falla con 503 y un mensaje claro (nunca se crea el
usuario local "a medias").
"""
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from core.config import settings

# Roles internos de Keycloak que nunca se tocan al reasignar el rol de la app.
_ROLES_KEYCLOAK = ("offline_access", "uma_authorization")

_TIMEOUT = 10.0
_token_cache: Dict[str, Any] = {"token": None, "expira": 0.0}


def _base() -> str:
    return settings.KEYCLOAK_INTERNAL_URL.rstrip("/")


def _url(path: str) -> str:
    return f"{_base()}/admin/realms/{settings.KEYCLOAK_REALM}{path}"


def _no_disponible(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"La gestión de usuarios en Keycloak no está disponible: {detalle}",
    )


async def _admin_token() -> str:
    """Token del admin del master, cacheado hasta ~10s antes de expirar."""
    now = time.monotonic()
    if _token_cache["token"] and now < _token_cache["expira"]:
        return _token_cache["token"]
    if not settings.KEYCLOAK_ADMIN or not settings.KEYCLOAK_ADMIN_PASSWORD:
        raise _no_disponible("faltan las credenciales de administración (KEYCLOAK_ADMIN)")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_base()}/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": settings.KEYCLOAK_ADMIN,
                    "password": settings.KEYCLOAK_ADMIN_PASSWORD,
                },
            )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _no_disponible(str(exc))
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expira"] = now + max(float(data.get("expires_in", 60)) - 10, 10)
    return _token_cache["token"]


async def _req(metodo: str, path: str, json: Any = None, params: dict | None = None) -> httpx.Response:
    token = await _admin_token()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await client.request(
                metodo, _url(path), json=json, params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        raise _no_disponible(str(exc))


async def buscar_por_username(username: str) -> Optional[dict]:
    resp = await _req("GET", "/users", params={"username": username, "exact": "true"})
    resp.raise_for_status()
    usuarios = resp.json()
    return usuarios[0] if usuarios else None


async def buscar_por_email(email: str) -> Optional[dict]:
    resp = await _req("GET", "/users", params={"email": email, "exact": "true"})
    resp.raise_for_status()
    usuarios = resp.json()
    return usuarios[0] if usuarios else None


async def reset_password(sub: str, password: str, temporal: bool = False) -> None:
    resp = await _req(
        "PUT", f"/users/{sub}/reset-password",
        json={"type": "password", "value": password, "temporary": temporal},
    )
    if resp.status_code >= 400:
        raise _no_disponible(f"no se pudo establecer la contraseña ({resp.status_code})")


async def actualizar(sub: str, email: str | None = None, enabled: bool | None = None) -> None:
    """Actualización parcial del usuario (Keycloak solo toca los campos enviados)."""
    body: dict = {}
    if email is not None:
        body["email"] = email
        body["emailVerified"] = True
    if enabled is not None:
        body["enabled"] = enabled
    if not body:
        return
    resp = await _req("PUT", f"/users/{sub}", json=body)
    if resp.status_code == 409:
        raise HTTPException(status_code=409, detail="Ese email ya está en uso en Keycloak")
    if resp.status_code >= 400:
        raise _no_disponible(f"no se pudo actualizar el usuario ({resp.status_code})")


def _es_rol_de_app(nombre: str | None) -> bool:
    """Roles gestionados por la app (base o personalizados) vs. los internos de
    Keycloak (offline_access, uma_authorization, default-roles-*)."""
    if not nombre:
        return False
    return nombre not in _ROLES_KEYCLOAK and not nombre.startswith("default-roles")


async def asegurar_rol_realm(nombre: str, descripcion: str | None = None) -> dict:
    """Garantiza que el realm-role exista en Keycloak (lo crea si falta) y devuelve su
    representación. Así los roles PERSONALIZADOS creados en la app son asignables."""
    resp = await _req("GET", f"/roles/{nombre}")
    if resp.status_code == 404:
        crear = await _req(
            "POST", "/roles",
            json={"name": nombre, "description": descripcion or f"Rol {nombre} (creado desde Rappi2)"},
        )
        if crear.status_code >= 400 and crear.status_code != 409:
            raise _no_disponible(f"no se pudo crear el rol '{nombre}' en el realm ({crear.status_code})")
        resp = await _req("GET", f"/roles/{nombre}")
    if resp.status_code >= 400:
        raise _no_disponible(f"no se pudo obtener el rol '{nombre}' del realm ({resp.status_code})")
    return resp.json()


async def renombrar_rol_realm(viejo: str, nuevo: str) -> None:
    """Renombra un realm-role migrando a sus miembros: crea el nuevo, se lo asigna a
    todos los usuarios que tenían el viejo, les quita el viejo y lo borra. Sin esto,
    renombrar un rol en uso degradaría a sus usuarios en el próximo login (el token
    traería un nombre que ya no existe en el catálogo)."""
    rep_nuevo = await asegurar_rol_realm(nuevo)
    check = await _req("GET", f"/roles/{viejo}")
    if check.status_code >= 400:  # el viejo no existe en el realm: nada que migrar
        return
    rep_viejo = check.json()
    miembros = await _req("GET", f"/roles/{viejo}/users", params={"max": 1000})
    for m in (miembros.json() if miembros.status_code < 400 else []):
        await _req("POST", f"/users/{m['id']}/role-mappings/realm", json=[rep_nuevo])
        await _req("DELETE", f"/users/{m['id']}/role-mappings/realm", json=[rep_viejo])
    await eliminar_rol_realm(viejo)


async def eliminar_rol_realm(nombre: str) -> None:
    """Borra el realm-role (best-effort: al eliminar un rol de la app no debe fallar
    por el estado de Keycloak)."""
    try:
        await _req("DELETE", f"/roles/{nombre}")
    except HTTPException:
        pass


async def asignar_rol(sub: str, rol: str) -> None:
    """Deja al usuario exactamente con el realm-role `rol` de la app (quita los demás
    roles de la app; los internos de Keycloak no se tocan). Crea el rol si falta."""
    rep = await asegurar_rol_realm(rol)

    actuales = await _req("GET", f"/users/{sub}/role-mappings/realm")
    actuales.raise_for_status()
    quitar = [r for r in actuales.json() if _es_rol_de_app(r.get("name")) and r.get("name") != rol]
    if quitar:
        await _req("DELETE", f"/users/{sub}/role-mappings/realm", json=quitar)
    resp = await _req("POST", f"/users/{sub}/role-mappings/realm", json=[rep])
    if resp.status_code >= 400:
        raise _no_disponible(f"no se pudo asignar el rol ({resp.status_code})")


async def crear_usuario(username: str, email: str, password: str, rol: str) -> str:
    """Crea el usuario en Keycloak (con contraseña y rol) y devuelve su `sub`.

    Se envía un perfil completo (first/lastName) y sin requiredActions: si el perfil
    queda incompleto, Keycloak deja pendiente VERIFY_PROFILE y el login falla con
    "Account is not fully set up".
    """
    resp = await _req(
        "POST", "/users",
        json={
            "username": username,
            "email": email,
            "firstName": username.capitalize(),
            "lastName": "Rappi2",
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
        },
    )
    if resp.status_code == 409:
        raise HTTPException(status_code=409, detail="El username o email ya existe en Keycloak")
    if resp.status_code >= 400:
        raise _no_disponible(f"no se pudo crear el usuario ({resp.status_code}: {resp.text[:200]})")
    # El id (sub) viene en la cabecera Location: .../users/{sub}
    sub = resp.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    if not sub:
        creado = await buscar_por_username(username)
        sub = (creado or {}).get("id", "")
    if not sub:
        raise _no_disponible("Keycloak no devolvió el id del usuario creado")
    # Si la contraseña o el rol fallan, deshacer el usuario recién creado: sin esto
    # quedaba una cuenta huérfana en Keycloak (sin rol ni espejo local).
    try:
        await reset_password(sub, password)
        await asignar_rol(sub, rol)
    except HTTPException:
        await eliminar(sub)
        raise
    return sub


async def eliminar(sub: str) -> None:
    """Borra el usuario en Keycloak (solo para deshacer una creación a medias)."""
    try:
        await _req("DELETE", f"/users/{sub}")
    except HTTPException:  # best-effort: no ocultar el error original del llamador
        pass
