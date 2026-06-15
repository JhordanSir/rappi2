"""coordenadas lat/lon en direcciones + confirmacion de entrega

Revision ID: 0003_add_coordenadas
Revises: 0002_datetime_timezone
Create Date: 2026-06-14 00:00:00.000000

Agrega latitud/longitud a todas las tablas que guardan una direccion:
- ordenes: punto de partida (origen) y punto de llegada (destino)
- clientes_direcciones
- paradas
Ademas agrega los campos de confirmacion de entrega en asignaciones
(coordenadas y receptor). Todas las columnas son Numeric(9,6) nullable, de modo
que las filas existentes y las direcciones aun sin geocodificar quedan en NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_add_coordenadas"
down_revision: Union[str, None] = "0002_datetime_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna) -> todas Numeric(9, 6) nullable
COLUMNAS_COORD = [
    ("ordenes", "lat_origen"),
    ("ordenes", "lon_origen"),
    ("ordenes", "lat_destino"),
    ("ordenes", "lon_destino"),
    ("clientes_direcciones", "lat"),
    ("clientes_direcciones", "lon"),
    ("paradas", "lat"),
    ("paradas", "lon"),
    ("asignaciones", "entrega_lat"),
    ("asignaciones", "entrega_lon"),
]


def upgrade() -> None:
    for tabla, columna in COLUMNAS_COORD:
        op.add_column(tabla, sa.Column(columna, sa.Numeric(9, 6), nullable=True))
    op.add_column("asignaciones", sa.Column("entrega_receptor", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("asignaciones", "entrega_receptor")
    for tabla, columna in reversed(COLUMNAS_COORD):
        op.drop_column(tabla, columna)
