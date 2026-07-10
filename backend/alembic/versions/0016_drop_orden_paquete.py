"""drop ordenes.peso_kg/largo_cm/ancho_cm/alto_cm (paquete legacy pre-multidestino)

El paquete físico vive por destino (models/destinos.py) desde 0009_multidestino. Las columnas
de paquete en `ordenes` eran copias redundantes (fuente de verdad ambigua): ya no se leen (el
precio y el cubicaje leen por destino) ni se escriben (ver create_orden/update_orden). Se
eliminan. El peso/volumen total de la orden pasa a ser un agregado calculado (@hybrid_property).

Revision ID: 0016_drop_orden_paquete
Revises: 0015_drop_google_sub
Create Date: 2026-07-10 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_drop_orden_paquete"
down_revision: Union[str, None] = "0015_drop_google_sub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Salvaguarda: 0009 hizo backfill de un destino por orden, pero por si quedara alguna orden
    # sin destino, se crea uno desde las columnas legacy ANTES de dropearlas (no perder el peso).
    op.execute(
        """
        INSERT INTO destinos (orden_id, secuencia, direccion, distrito, lat, lon,
                              peso_kg, largo_cm, ancho_cm, alto_cm, estado)
        SELECT o.id, 1, o.direccion_destino, o.distrito_destino, o.lat_destino, o.lon_destino,
               o.peso_kg, o.largo_cm, o.ancho_cm, o.alto_cm, 'Pendiente'
        FROM ordenes o
        WHERE NOT EXISTS (SELECT 1 FROM destinos d WHERE d.orden_id = o.id)
        """
    )
    op.drop_column("ordenes", "peso_kg")
    op.drop_column("ordenes", "largo_cm")
    op.drop_column("ordenes", "ancho_cm")
    op.drop_column("ordenes", "alto_cm")


def downgrade() -> None:
    # Se recrean nullable; los datos NO se restauran (eran copias redundantes, la verdad está en destinos).
    op.add_column("ordenes", sa.Column("peso_kg", sa.Numeric(8, 2), nullable=True))
    op.add_column("ordenes", sa.Column("largo_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("ordenes", sa.Column("ancho_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("ordenes", sa.Column("alto_cm", sa.Numeric(7, 1), nullable=True))
