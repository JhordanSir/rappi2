"""nota en destino (observación de entrega o motivo de fallo)

Revision ID: 0010_destino_nota
Revises: 0009_multidestino
Create Date: 2026-06-19 13:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_destino_nota"
down_revision: Union[str, None] = "0009_multidestino"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("destinos", sa.Column("nota", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("destinos", "nota")
