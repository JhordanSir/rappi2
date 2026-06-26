"""keycloak: keycloak_sub en usuarios + eliminar tabla tokens

Con Keycloak como proveedor de identidad, el backend ya no emite refresh tokens propios
(se elimina la tabla `tokens`) y enlaza cada usuario por su `sub` de Keycloak.

Revision ID: 0013_keycloak
Revises: 0012_vehiculo_dimensiones
Create Date: 2026-06-26 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_keycloak"
down_revision: Union[str, None] = "0012_vehiculo_dimensiones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Identidad federada de Keycloak.
    op.add_column("usuarios", sa.Column("keycloak_sub", sa.String(length=255), nullable=True))
    op.create_index("ix_usuarios_keycloak_sub", "usuarios", ["keycloak_sub"], unique=True)
    # La gestión de sesiones/refresh pasa a Keycloak: la tabla local de tokens ya no se usa.
    op.drop_table("tokens")


def downgrade() -> None:
    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("fecha_expiracion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tokens_usuario_id", "tokens", ["usuario_id"], unique=False)
    op.create_index("ix_tokens_token", "tokens", ["token"], unique=True)
    op.create_index("ix_tokens_id", "tokens", ["id"], unique=False)

    op.drop_index("ix_usuarios_keycloak_sub", table_name="usuarios")
    op.drop_column("usuarios", "keycloak_sub")
