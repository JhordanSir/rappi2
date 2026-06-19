"""índices de rendimiento para filtros frecuentes

Revision ID: 0005_perf_indexes
Revises: 0004_ruta_geometria
Create Date: 2026-06-15 00:00:00.000000

Cubre los filtros que más se ejecutan en listados y reportes:
- ordenes.estado          (listado de órdenes, dashboard por estado)
- pagos.(estado, fecha_pago) compuesto (recaudación/ventas/SLA filtran estado='Pagado' + rango de fecha)
- asignaciones.estado     (KPIs operativos: EnCurso / Finalizada)
- asignaciones.conductor_id (joins de reportes por conductor)
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_perf_indexes"
down_revision: Union[str, None] = "0004_ruta_geometria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_ordenes_estado", "ordenes", ["estado"])
    op.create_index("ix_pagos_estado_fecha_pago", "pagos", ["estado", "fecha_pago"])
    op.create_index("ix_asignaciones_estado", "asignaciones", ["estado"])
    op.create_index("ix_asignaciones_conductor_id", "asignaciones", ["conductor_id"])


def downgrade() -> None:
    op.drop_index("ix_asignaciones_conductor_id", table_name="asignaciones")
    op.drop_index("ix_asignaciones_estado", table_name="asignaciones")
    op.drop_index("ix_pagos_estado_fecha_pago", table_name="pagos")
    op.drop_index("ix_ordenes_estado", table_name="ordenes")
