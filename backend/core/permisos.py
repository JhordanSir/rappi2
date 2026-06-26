"""Conjunto de permisos finos (`recurso`, `acción`) por rol — valores **por defecto**.

Con Keycloak como autoridad de identidad, la *asignación* de roles vive en Keycloak
(viene en `realm_access.roles` del token). El *conjunto de capacidades* de cada rol se
**siembra** desde aquí (`scripts/seed_admin.py`) hacia la tabla `permisos`, que es la
fuente **autoritativa en runtime**: `require_permiso` lee esa tabla y un administrador la
edita desde "Roles & Permisos" (multiselección). Editar la tabla cambia la autorización
sin tocar este archivo; este módulo solo define el punto de partida idempotente.

La propiedad de fila (ownership) se impone aparte en cada endpoint (un Cliente solo opera
SUS datos, un Conductor solo SUS asignaciones); estos permisos solo habilitan la capacidad.
"""
from typing import Dict, List, Tuple

# Admin tiene el comodín *:*. Conductor/Cliente heredan exactamente el set base que antes
# se sembraba en la tabla `permisos` (scripts/seed_admin.py).
ROLE_PERMISOS: Dict[str, List[Tuple[str, str]]] = {
    "Admin": [("*", "*")],
    "Conductor": [
        ("tracking", "read"), ("tracking", "write"),
        ("ordenes", "read"),
        ("asignaciones", "read"), ("asignaciones", "write"),
        ("rutas", "read"), ("rutas", "write"),
        ("incidencias", "read"), ("incidencias", "write"),
        ("entregas", "read"), ("entregas", "write"),
        ("conductores", "read"),
        ("calificaciones", "read"),
        ("notificaciones", "read"),
    ],
    "Cliente": [
        ("ordenes", "read"), ("ordenes", "write"),
        ("tracking", "read"),
        ("pagos", "read"), ("pagos", "write"),
        ("clientes", "read"), ("clientes", "write"),
        ("incidencias", "read"), ("incidencias", "write"),
        ("calificaciones", "read"), ("calificaciones", "write"),
        ("facturas", "read"),
        ("notificaciones", "read"),
    ],
}


def permisos_de_rol(rol_nombre: str | None) -> List[Tuple[str, str]]:
    """Lista de pares (recurso, accion) del rol (vacía si el rol es desconocido)."""
    if not rol_nombre:
        return []
    return ROLE_PERMISOS.get(rol_nombre, [])


def tiene_permiso(rol_nombre: str | None, recurso: str, accion: str) -> bool:
    """True si el rol puede ejecutar `recurso:accion` (soporta comodín `*`)."""
    for r, a in permisos_de_rol(rol_nombre):
        if (r == "*" or r == recurso) and (a == "*" or a == accion):
            return True
    return False
