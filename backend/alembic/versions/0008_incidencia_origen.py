"""origen de incidencia (chofer / automatica / admin)

Revision ID: 0008_incidencia_origen
Revises: 0007_tarifa_y_precio
Create Date: 2026-06-19 11:00:00.000000

Fase 3/4: el chofer ya no fija la severidad (la deriva el sistema o la ajusta el admin),
y el sistema crea incidencias automáticas (p.ej. desvío de ruta). 'origen' distingue
el reporte del chofer, las automáticas y las creadas por el admin.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_incidencia_origen"
down_revision: Union[str, None] = "0007_tarifa_y_precio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("incidencias", sa.Column("origen", sa.String(length=20), server_default="chofer", nullable=False))
    op.create_check_constraint(
        "ck_incidencias_incidencia_origen", "incidencias", "origen IN ('chofer','automatica','admin')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_incidencias_incidencia_origen", "incidencias", type_="check")
    op.drop_column("incidencias", "origen")
