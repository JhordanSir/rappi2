"""drop incidencias.evidencia_url (funcionalidad muerta, superada por evidencias en GridFS)

`evidencia_url` era un único enlace de evidencia del modelo antiguo. La evidencia real de las
incidencias vive en GridFS/Mongo (endpoints /incidencias/{id}/evidencias/*). La columna se
aceptaba, guardaba y devolvía, pero ningún consumidor la leía (el frontend solo la declaraba en
el tipo). Se elimina.

NOTA: el revision id se mantiene <= 32 caracteres porque `alembic_version.version_num` es
VARCHAR(32); ids más largos fallan al escribir la versión (StringDataRightTruncationError).

Revision ID: 0017_drop_inc_evidencia_url
Revises: 0016_drop_orden_paquete
Create Date: 2026-07-10 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_drop_inc_evidencia_url"
down_revision: Union[str, None] = "0016_drop_orden_paquete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("incidencias", "evidencia_url")


def downgrade() -> None:
    op.add_column("incidencias", sa.Column("evidencia_url", sa.Text(), nullable=True))
