"""Máquina de estados de órdenes y asignaciones: transiciones legales centralizadas.

Única fuente de verdad para los cambios de estado hechos A MANO vía los endpoints
genéricos (PATCH /ordenes/{id}, PATCH /asignaciones/{id}). Los flujos operativos
(crear asignación, iniciar, entregar/fallar destinos, cierre forzado, reabrir) avanzan
el estado con sus propias guardas explícitas y NO pasan por aquí: los estados de avance
("En Proceso", "En Tránsito", "Entregado", "EnCurso", "Finalizada") solo se alcanzan por
esos endpoints dedicados, nunca editando el campo directamente.
"""
from fastapi import HTTPException, status

# Desde el PATCH genérico de órdenes solo se permite liberar un pago pendiente o
# cancelar. "Entregado"/"Cancelado" son terminales (solo /asignaciones/{id}/reabrir
# los revive, con sus propias validaciones).
TRANSICIONES_ORDEN: dict[str, set[str]] = {
    "Pendiente de Pago": {"Pendiente", "Cancelado"},
    "Pendiente": {"Cancelado"},
    "En Proceso": {"Cancelado"},
    "En Tránsito": {"Cancelado"},
    "Entregado": set(),
    "Cancelado": set(),
}

# Desde el PATCH genérico de asignaciones solo se puede cancelar una aún no iniciada.
# EnCurso se cierra entregando/fallando destinos o con el cierre forzado; Finalizada
# solo se reabre con /reabrir.
TRANSICIONES_ASIGNACION: dict[str, set[str]] = {
    "Asignada": {"Cancelada"},
    "EnCurso": set(),
    "Finalizada": set(),
    "Cancelada": set(),
}


def validar_transicion(entidad: str, actual: str, nuevo: str, mapa: dict[str, set[str]]) -> None:
    """Lanza 409 si el cambio de estado `actual` → `nuevo` no está permitido a mano."""
    if nuevo == actual:
        return
    permitidas = mapa.get(actual, set())
    if nuevo not in permitidas:
        detalle = ", ".join(sorted(permitidas)) if permitidas else "ninguna (estado terminal o de flujo)"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transición ilegal de {entidad}: '{actual}' → '{nuevo}'. "
                f"Permitidas a mano desde '{actual}': {detalle}."
            ),
        )
