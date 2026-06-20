"""multidestino: destinos por orden y agrupación de órdenes por asignación

Revision ID: 0009_multidestino
Revises: 0008_incidencia_origen
Create Date: 2026-06-19 12:00:00.000000

- Nueva tabla 'destinos': cada orden puede tener varios puntos de entrega, cada uno
  con su paquete y su precio de tramo.
- Nueva tabla puente 'asignacion_ordenes': una asignación agrupa varias órdenes en
  la ruta del conductor.
- paradas.destino_id: enlaza una parada de entrega con su destino.
- Backfill: cada orden existente recibe un destino (desde sus columnas destino_*) y
  cada asignación se enlaza con su orden.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_multidestino"
down_revision: Union[str, None] = "0008_incidencia_origen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "destinos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orden_id", sa.Integer(), sa.ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("secuencia", sa.Integer(), server_default="1", nullable=False),
        sa.Column("direccion", sa.String(length=200), nullable=False),
        sa.Column("distrito", sa.String(length=80), nullable=True),
        sa.Column("lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("peso_kg", sa.Numeric(8, 2), nullable=True),
        sa.Column("largo_cm", sa.Numeric(7, 1), nullable=True),
        sa.Column("ancho_cm", sa.Numeric(7, 1), nullable=True),
        sa.Column("alto_cm", sa.Numeric(7, 1), nullable=True),
        sa.Column("nombre_destinatario", sa.String(length=120), nullable=True),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="Pendiente", nullable=False),
        sa.Column("entrega_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("entrega_lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("entrega_receptor", sa.String(length=120), nullable=True),
        sa.Column("fecha_entrega", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("estado IN ('Pendiente','Entregado','Fallida')", name="ck_destinos_destino_estado"),
    )
    op.create_index("ix_destinos_orden_id", "destinos", ["orden_id"])

    op.create_table(
        "asignacion_ordenes",
        sa.Column("asignacion_id", sa.Integer(), sa.ForeignKey("asignaciones.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("orden_id", sa.Integer(), sa.ForeignKey("ordenes.id", ondelete="CASCADE"), primary_key=True),
    )

    op.add_column("paradas", sa.Column("destino_id", sa.Integer(), sa.ForeignKey("destinos.id", ondelete="SET NULL"), nullable=True))

    # Backfill: un destino por orden, desde las columnas destino_* existentes.
    op.execute(
        """
        INSERT INTO destinos (orden_id, secuencia, direccion, distrito, lat, lon,
                              peso_kg, largo_cm, ancho_cm, alto_cm, subtotal, estado)
        SELECT id, 1, direccion_destino, distrito_destino, lat_destino, lon_destino,
               peso_kg, largo_cm, ancho_cm, alto_cm, total,
               CASE WHEN estado = 'Entregado' THEN 'Entregado' ELSE 'Pendiente' END
        FROM ordenes
        """
    )
    # Backfill: enlazar cada asignación con su orden.
    op.execute(
        "INSERT INTO asignacion_ordenes (asignacion_id, orden_id) SELECT id, orden_id FROM asignaciones"
    )


def downgrade() -> None:
    op.drop_column("paradas", "destino_id")
    op.drop_table("asignacion_ordenes")
    op.drop_index("ix_destinos_orden_id", table_name="destinos")
    op.drop_table("destinos")
