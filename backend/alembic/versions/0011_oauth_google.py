"""oauth google: password_hash nullable + identidad de Google en usuarios

Revision ID: 0011_oauth_google
Revises: 0010_destino_nota
Create Date: 2026-06-21 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_oauth_google"
down_revision: Union[str, None] = "0010_destino_nota"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Los usuarios solo-Google no tienen contraseña local.
    op.alter_column("usuarios", "password_hash", existing_type=sa.Text(), nullable=True)
    # Identidad de Google (OAuth).
    op.add_column("usuarios", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column(
        "usuarios",
        sa.Column("auth_provider", sa.String(length=20), nullable=False, server_default="local"),
    )
    op.add_column("usuarios", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.create_index("ix_usuarios_google_sub", "usuarios", ["google_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_usuarios_google_sub", table_name="usuarios")
    op.drop_column("usuarios", "avatar_url")
    op.drop_column("usuarios", "auth_provider")
    op.drop_column("usuarios", "google_sub")
    op.alter_column("usuarios", "password_hash", existing_type=sa.Text(), nullable=False)
