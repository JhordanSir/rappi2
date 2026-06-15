"""columnas de fecha a TIMESTAMP WITH TIME ZONE (UTC)

Revision ID: 0002_datetime_timezone
Revises: 0001_initial
Create Date: 2026-05-22 06:10:00.000000

Convierte todas las columnas DateTime del esquema a `timestamptz`, asumiendo
que los valores actualmente almacenados representan UTC. El downgrade revierte
a `timestamp` sin zona (descartando la informacion de zona).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_datetime_timezone"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNAS = [
    ("usuarios", "fecha_registro"),
    ("tokens", "fecha_expiracion"),
    ("clientes", "fecha_registro"),
    ("ordenes", "fecha_creacion"),
    ("pagos", "fecha_pago"),
    ("facturas", "fecha"),
    ("vehiculos", "fecha_mantenimiento"),
    ("asignaciones", "fecha_inicio"),
    ("asignaciones", "fecha_fin"),
    ("incidencias", "fecha"),
    ("paradas", "fecha_paso"),
]


def upgrade() -> None:
    for tabla, columna in COLUMNAS:
        op.execute(
            f"ALTER TABLE {tabla} "
            f"ALTER COLUMN {columna} TYPE TIMESTAMP WITH TIME ZONE "
            f"USING {columna} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for tabla, columna in COLUMNAS:
        op.execute(
            f"ALTER TABLE {tabla} "
            f"ALTER COLUMN {columna} TYPE TIMESTAMP WITHOUT TIME ZONE "
            f"USING {columna} AT TIME ZONE 'UTC'"
        )
