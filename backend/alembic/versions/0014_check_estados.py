"""CHECK constraints para estados que eran texto libre.

Orden y Destino ya tenían CHECK; se añaden los que faltaban para que un bug o una
petición mal formada no pueda insertar estados inválidos que rompan las transiciones:
- asignaciones.estado          ('Asignada','EnCurso','Finalizada','Cancelada')
- vehiculos.estado             ('Operativo','Mantenimiento','Inactivo')
- conductores.disponibilidad   ('Disponible','Ocupado','Inactivo')

Antes de cada constraint se sanean los valores fuera de catálogo (si los hubiera).

Revision ID: 0014_check_estados
Revises: 0013_keycloak
Create Date: 2026-07-02 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0014_check_estados"
down_revision: Union[str, None] = "0013_keycloak"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Saneo: cualquier valor fuera de catálogo pasa a un estado seguro/terminal.
    op.execute(
        "UPDATE asignaciones SET estado = 'Finalizada' "
        "WHERE estado NOT IN ('Asignada','EnCurso','Finalizada','Cancelada')"
    )
    op.execute(
        "UPDATE vehiculos SET estado = 'Inactivo' "
        "WHERE estado NOT IN ('Operativo','Mantenimiento','Inactivo')"
    )
    op.execute(
        "UPDATE conductores SET disponibilidad = 'Inactivo' "
        "WHERE disponibilidad NOT IN ('Disponible','Ocupado','Inactivo')"
    )

    # Nombre corto: la naming convention (ck_%(table)s_%(constraint_name)s) antepone el
    # prefijo sola → resultan ck_asignaciones_asignacion_estado, etc.
    op.create_check_constraint(
        "asignacion_estado",
        "asignaciones",
        "estado IN ('Asignada','EnCurso','Finalizada','Cancelada')",
    )
    op.create_check_constraint(
        "vehiculo_estado",
        "vehiculos",
        "estado IN ('Operativo','Mantenimiento','Inactivo')",
    )
    op.create_check_constraint(
        "conductor_disponibilidad",
        "conductores",
        "disponibilidad IN ('Disponible','Ocupado','Inactivo')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_asignaciones_asignacion_estado", "asignaciones", type_="check")
    op.drop_constraint("ck_vehiculos_vehiculo_estado", "vehiculos", type_="check")
    op.drop_constraint("ck_conductores_conductor_disponibilidad", "conductores", type_="check")
