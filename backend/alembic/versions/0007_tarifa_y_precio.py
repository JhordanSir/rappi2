"""tarifa configurable y campos de precio/paquete en ordenes

Revision ID: 0007_tarifa_y_precio
Revises: 0006_pagos_calificaciones
Create Date: 2026-06-19 10:00:00.000000

Fase 0 del rediseño:
- ordenes: peso/dimensiones del paquete, nivel_servicio, programado_para y
  ajuste manual de precio (monto/motivo/por). 'total' pasa a ser calculado por el servidor.
- nueva tabla tarifa_config (una fila vigente) editable por el admin, que alimenta
  el cálculo automático de precio.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_tarifa_y_precio"
down_revision: Union[str, None] = "0006_pagos_calificaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Campos de paquete / servicio / ajuste en ordenes
    op.add_column("ordenes", sa.Column("peso_kg", sa.Numeric(8, 2), nullable=True))
    op.add_column("ordenes", sa.Column("largo_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("ordenes", sa.Column("ancho_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("ordenes", sa.Column("alto_cm", sa.Numeric(7, 1), nullable=True))
    op.add_column("ordenes", sa.Column("nivel_servicio", sa.String(length=20), server_default="estandar", nullable=False))
    op.add_column("ordenes", sa.Column("programado_para", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ordenes", sa.Column("ajuste_monto", sa.Numeric(10, 2), nullable=True))
    op.add_column("ordenes", sa.Column("ajuste_motivo", sa.String(length=200), nullable=True))
    op.add_column("ordenes", sa.Column("ajuste_por", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True))
    op.create_check_constraint("ck_ordenes_orden_nivel_servicio", "ordenes", "nivel_servicio IN ('estandar','express','urgente')")

    # 2) Tabla de tarifa configurable
    op.create_table(
        "tarifa_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("moneda", sa.String(length=8), server_default="PEN", nullable=False),
        sa.Column("tarifa_base", sa.Numeric(10, 2), server_default="5.00", nullable=False),
        sa.Column("precio_km", sa.Numeric(10, 2), server_default="1.20", nullable=False),
        sa.Column("precio_min", sa.Numeric(10, 2), server_default="0.30", nullable=False),
        sa.Column("precio_kg", sa.Numeric(10, 2), server_default="0.50", nullable=False),
        sa.Column("factor_volumetrico", sa.Integer(), server_default="5000", nullable=False),
        sa.Column("minimo", sa.Numeric(10, 2), server_default="6.00", nullable=False),
        sa.Column("mult_estandar", sa.Numeric(5, 2), server_default="1.00", nullable=False),
        sa.Column("mult_express", sa.Numeric(5, 2), server_default="1.50", nullable=False),
        sa.Column("mult_urgente", sa.Numeric(5, 2), server_default="2.00", nullable=False),
        sa.Column("recargo_nocturno_pct", sa.Numeric(5, 2), server_default="0.20", nullable=False),
        sa.Column("nocturno_desde", sa.Integer(), server_default="22", nullable=False),
        sa.Column("nocturno_hasta", sa.Integer(), server_default="6", nullable=False),
        sa.Column("recargo_pico_pct", sa.Numeric(5, 2), server_default="0.15", nullable=False),
        sa.Column("pico_ventanas", sa.JSON(), nullable=False),
        sa.Column("recargo_finde_pct", sa.Numeric(5, 2), server_default="0.10", nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Fila vigente por defecto (el cálculo y el admin la leen/editan por id=1).
    op.execute(
        "INSERT INTO tarifa_config (id, pico_ventanas) VALUES (1, '[[7,9],[18,20]]')"
    )


def downgrade() -> None:
    op.drop_table("tarifa_config")
    op.drop_constraint("ck_ordenes_orden_nivel_servicio", "ordenes", type_="check")
    op.drop_column("ordenes", "ajuste_por")
    op.drop_column("ordenes", "ajuste_motivo")
    op.drop_column("ordenes", "ajuste_monto")
    op.drop_column("ordenes", "programado_para")
    op.drop_column("ordenes", "nivel_servicio")
    op.drop_column("ordenes", "alto_cm")
    op.drop_column("ordenes", "ancho_cm")
    op.drop_column("ordenes", "largo_cm")
    op.drop_column("ordenes", "peso_kg")
