"""drop usuarios.google_sub (dead code de la era pre-Keycloak)

La columna `google_sub` se añadió con el login por Google (0011_oauth_google). Desde la
federación con Keycloak (0013_keycloak) la identidad se vincula por `keycloak_sub` y
`google_sub` quedó sin uso: no se lee ni se escribe en ningún flujo. Se elimina.

Revision ID: 0015_drop_google_sub
Revises: 0014_check_estados
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_drop_google_sub"
down_revision: Union[str, None] = "0014_check_estados"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_usuarios_google_sub", table_name="usuarios")
    op.drop_column("usuarios", "google_sub")


def downgrade() -> None:
    op.add_column("usuarios", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_usuarios_google_sub", "usuarios", ["google_sub"], unique=True)
