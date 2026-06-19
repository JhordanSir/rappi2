"""estado 'Pendiente de Pago', campos de pasarela en pagos y tabla calificaciones

Revision ID: 0006_pagos_calificaciones
Revises: 0005_perf_indexes
Create Date: 2026-06-19 00:00:00.000000

Fase 2 (Portal del Cliente):
- ordenes.estado admite 'Pendiente de Pago' (la orden del cliente nace así y solo
  pasa a 'Pendiente'/despachable cuando MercadoPago confirma el pago).
- pagos gana columnas de pasarela (metodo, proveedor, preference_id, external_id).
- nueva tabla calificaciones (cliente -> entrega/conductor, 1 por orden).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_pagos_calificaciones"
down_revision: Union[str, None] = "0005_perf_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ESTADOS_NUEVO = "estado IN ('Pendiente de Pago','Pendiente','En Proceso','En Tránsito','Entregado','Cancelado')"
_ESTADOS_VIEJO = "estado IN ('Pendiente','En Proceso','En Tránsito','Entregado','Cancelado')"
# La constraint puede existir con prefijo simple o doble según la naming convention; las cubrimos todas.
# (Sentencias separadas: asyncpg no admite múltiples comandos en un mismo execute.)
_DROP_CHECKS = [
    "ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ck_ordenes_ck_ordenes_orden_estado",
    "ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS ck_ordenes_orden_estado",
    "ALTER TABLE ordenes DROP CONSTRAINT IF EXISTS orden_estado",
]


def _reset_check(definicion: str) -> None:
    for stmt in _DROP_CHECKS:
        op.execute(stmt)
    op.execute(f"ALTER TABLE ordenes ADD CONSTRAINT ck_ordenes_orden_estado CHECK ({definicion})")


def upgrade() -> None:
    # 1) Ampliar el CHECK de ordenes.estado (SQL explícito para no depender del nombre exacto)
    _reset_check(_ESTADOS_NUEVO)

    # 2) Campos de pasarela en pagos
    op.add_column("pagos", sa.Column("metodo", sa.String(length=40), nullable=True))
    op.add_column("pagos", sa.Column("proveedor", sa.String(length=40), nullable=True))
    op.add_column("pagos", sa.Column("preference_id", sa.String(length=120), nullable=True))
    op.add_column("pagos", sa.Column("external_id", sa.String(length=120), nullable=True))

    # 3) Tabla de calificaciones
    op.create_table(
        "calificaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orden_id", sa.Integer(), sa.ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("conductor_id", sa.Integer(), sa.ForeignKey("conductores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("puntaje", sa.Integer(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("puntaje BETWEEN 1 AND 5", name="calificacion_puntaje"),
    )
    op.create_index("ix_calificaciones_conductor_id", "calificaciones", ["conductor_id"])
    op.create_index("ix_calificaciones_cliente_id", "calificaciones", ["cliente_id"])


def downgrade() -> None:
    op.drop_index("ix_calificaciones_cliente_id", table_name="calificaciones")
    op.drop_index("ix_calificaciones_conductor_id", table_name="calificaciones")
    op.drop_table("calificaciones")

    op.drop_column("pagos", "external_id")
    op.drop_column("pagos", "preference_id")
    op.drop_column("pagos", "proveedor")
    op.drop_column("pagos", "metodo")

    # Revertir el CHECK (asumiendo que no quedan ordenes en 'Pendiente de Pago')
    _reset_check(_ESTADOS_VIEJO)
