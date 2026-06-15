"""esquema inicial: 15 tablas alineadas al diagrama

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INTERVAL

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_roles_nombre"),
    )

    op.create_table(
        "permisos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("recurso", sa.String(length=50), nullable=False),
        sa.Column("accion", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["rol_id"], ["roles.id"], name="fk_permisos_rol_id_roles", ondelete="CASCADE"),
        sa.UniqueConstraint("rol_id", "recurso", "accion", name="uq_permisos_rol_recurso_accion"),
    )

    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("telefono", sa.String(length=20), nullable=True),
        sa.Column("cc_id", sa.String(length=30), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_registro", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_clientes_email"),
    )
    op.create_index("ix_clientes_email", "clientes", ["email"])

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("rol_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_registro", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["rol_id"], ["roles.id"], name="fk_usuarios_rol_id_roles", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], name="fk_usuarios_cliente_id_clientes", ondelete="SET NULL"),
        sa.UniqueConstraint("username", name="uq_usuarios_username"),
        sa.UniqueConstraint("email", name="uq_usuarios_email"),
        sa.UniqueConstraint("cliente_id", name="uq_usuarios_cliente_id"),
    )
    op.create_index("ix_usuarios_username", "usuarios", ["username"])
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("fecha_expiracion", sa.DateTime(), nullable=False),
        sa.Column("revocado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], name="fk_tokens_usuario_id_usuarios", ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_tokens_token"),
    )
    op.create_index("ix_tokens_usuario_id", "tokens", ["usuario_id"])
    op.create_index("ix_tokens_token", "tokens", ["token"])

    op.create_table(
        "clientes_direcciones",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("direccion", sa.String(length=200), nullable=False),
        sa.Column("distrito", sa.String(length=80), nullable=True),
        sa.Column("ciudad", sa.String(length=80), nullable=True),
        sa.Column("estado", sa.String(length=80), nullable=True),
        sa.Column("pais", sa.String(length=80), nullable=True),
        sa.Column("es_principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], name="fk_clientes_direcciones_cliente_id_clientes", ondelete="CASCADE"),
    )
    op.create_index("ix_clientes_direcciones_cliente_id", "clientes_direcciones", ["cliente_id"])

    op.create_table(
        "ordenes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.Column("direccion_origen", sa.String(length=200), nullable=False),
        sa.Column("distrito_origen", sa.String(length=80), nullable=True),
        sa.Column("direccion_destino", sa.String(length=200), nullable=False),
        sa.Column("distrito_destino", sa.String(length=80), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("total", sa.Numeric(10, 2), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], name="fk_ordenes_cliente_id_clientes", ondelete="CASCADE"),
        sa.CheckConstraint(
            "estado IN ('Pendiente','En Proceso','En Tránsito','Entregado','Cancelado')",
            name="ck_ordenes_orden_estado",
        ),
    )
    op.create_index("ix_ordenes_cliente_id", "ordenes", ["cliente_id"])

    op.create_table(
        "pagos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("fecha_pago", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.Column("referencia_banco", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["orden_id"], ["ordenes.id"], name="fk_pagos_orden_id_ordenes", ondelete="CASCADE"),
    )
    op.create_index("ix_pagos_orden_id", "pagos", ["orden_id"])

    op.create_table(
        "facturas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ruc", sa.String(length=20), nullable=True),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["orden_id"], ["ordenes.id"], name="fk_facturas_orden_id_ordenes", ondelete="CASCADE"),
    )
    op.create_index("ix_facturas_orden_id", "facturas", ["orden_id"])

    op.create_table(
        "vehiculos",
        sa.Column("placa", sa.String(length=15), primary_key=True, index=True),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("capacidad_kg", sa.Numeric(8, 2), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Operativo"),
        sa.Column("fecha_mantenimiento", sa.DateTime(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "conductores",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_placa", sa.String(length=15), nullable=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("licencia", sa.String(length=30), nullable=False),
        sa.Column("disponibilidad", sa.String(length=20), nullable=False, server_default="Disponible"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], name="fk_conductores_usuario_id_usuarios", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vehiculo_placa"], ["vehiculos.placa"],
            name="fk_conductores_vehiculo_placa_vehiculos",
            ondelete="SET NULL", onupdate="CASCADE",
        ),
        sa.UniqueConstraint("usuario_id", name="uq_conductores_usuario_id"),
        sa.UniqueConstraint("licencia", name="uq_conductores_licencia"),
    )
    op.create_index("ix_conductores_vehiculo_placa", "conductores", ["vehiculo_placa"])

    op.create_table(
        "asignaciones",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("conductor_id", sa.Integer(), nullable=False),
        sa.Column("vehiculo_placa", sa.String(length=15), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Asignada"),
        sa.Column("fecha_inicio", sa.DateTime(), nullable=True),
        sa.Column("fecha_fin", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["orden_id"], ["ordenes.id"], name="fk_asignaciones_orden_id_ordenes", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conductor_id"], ["conductores.id"], name="fk_asignaciones_conductor_id_conductores", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["vehiculo_placa"], ["vehiculos.placa"],
            name="fk_asignaciones_vehiculo_placa_vehiculos",
            ondelete="RESTRICT", onupdate="CASCADE",
        ),
    )
    op.create_index("ix_asignaciones_orden_id", "asignaciones", ["orden_id"])

    op.create_table(
        "rutas_planificadas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("orden_id", sa.Integer(), nullable=False),
        sa.Column("distancia_km", sa.Numeric(8, 2), nullable=True),
        sa.Column("tiempo_estimado", INTERVAL(), nullable=True),
        sa.ForeignKeyConstraint(["orden_id"], ["ordenes.id"], name="fk_rutas_planificadas_orden_id_ordenes", ondelete="CASCADE"),
    )
    op.create_index("ix_rutas_planificadas_orden_id", "rutas_planificadas", ["orden_id"])

    op.create_table(
        "paradas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ruta_id", sa.Integer(), nullable=False),
        sa.Column("orden_id", sa.Integer(), nullable=True),
        sa.Column("direccion", sa.String(length=200), nullable=False),
        sa.Column("distrito", sa.String(length=80), nullable=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("fecha_paso", sa.DateTime(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="Pendiente"),
        sa.ForeignKeyConstraint(["ruta_id"], ["rutas_planificadas.id"], name="fk_paradas_ruta_id_rutas_planificadas", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["orden_id"], ["ordenes.id"], name="fk_paradas_orden_id_ordenes", ondelete="SET NULL"),
        sa.UniqueConstraint("ruta_id", "secuencia", name="uq_paradas_ruta_secuencia"),
    )
    op.create_index("ix_paradas_ruta_id", "paradas", ["ruta_id"])

    op.create_table(
        "incidencias",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("asignacion_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("severidad", sa.Integer(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("evidencia_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["asignacion_id"], ["asignaciones.id"], name="fk_incidencias_asignacion_id_asignaciones", ondelete="CASCADE"),
        sa.CheckConstraint("severidad BETWEEN 1 AND 5", name="ck_incidencias_severidad_rango"),
    )
    op.create_index("ix_incidencias_asignacion_id", "incidencias", ["asignacion_id"])


def downgrade() -> None:
    op.drop_table("incidencias")
    op.drop_table("paradas")
    op.drop_table("rutas_planificadas")
    op.drop_table("asignaciones")
    op.drop_table("conductores")
    op.drop_table("vehiculos")
    op.drop_table("facturas")
    op.drop_table("pagos")
    op.drop_table("ordenes")
    op.drop_table("clientes_direcciones")
    op.drop_table("tokens")
    op.drop_table("usuarios")
    op.drop_table("clientes")
    op.drop_table("permisos")
    op.drop_table("roles")
