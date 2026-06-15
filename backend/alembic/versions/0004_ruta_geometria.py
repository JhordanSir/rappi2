"""geometria (GeoJSON LineString) en rutas_planificadas

Revision ID: 0004_ruta_geometria
Revises: 0003_add_coordenadas
Create Date: 2026-06-15 00:00:00.000000

Guarda la geometría real de la ruta por calles para dibujarla en el frontend sin
depender de un servicio externo en cada vista.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_ruta_geometria"
down_revision: Union[str, None] = "0003_add_coordenadas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rutas_planificadas", sa.Column("geometria", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("rutas_planificadas", "geometria")
