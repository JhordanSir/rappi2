"""dimensiones de carga del vehiculo (cubicaje)

Revision ID: 0012_vehiculo_dimensiones
Revises: 0011_oauth_google
Create Date: 2026-06-26 00:00:00.000000

Añade largo/ancho/alto (cm) al vehiculo para validar si un paquete cabe físicamente
(además del límite de peso).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_vehiculo_dimensiones"
down_revision: Union[str, None] = "0011_oauth_google"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vehiculos", sa.Column("largo_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("vehiculos", sa.Column("ancho_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("vehiculos", sa.Column("alto_cm", sa.Numeric(7, 1), nullable=True))


def downgrade() -> None:
    op.drop_column("vehiculos", "alto_cm")
    op.drop_column("vehiculos", "ancho_cm")
    op.drop_column("vehiculos", "largo_cm")
