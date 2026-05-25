"""Remediacion de esquema para facturas legacy con Decimal

Revision ID: 9c4f3b2a1d7e
Revises: 7794d427b400
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4f3b2a1d7e"
down_revision: Union[str, None] = "7794d427b400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_dependent_views() -> list[tuple[str, str, str]]:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT
                dependent_ns.nspname AS view_schema,
                dependent_view.relname AS view_name,
                pg_get_viewdef(dependent_view.oid, true) AS view_definition
            FROM pg_depend d
            JOIN pg_rewrite r ON d.objid = r.oid
            JOIN pg_class dependent_view ON r.ev_class = dependent_view.oid
            JOIN pg_namespace dependent_ns ON dependent_view.relnamespace = dependent_ns.oid
            JOIN pg_class source_table ON d.refobjid = source_table.oid
            JOIN pg_attribute a ON a.attrelid = source_table.oid AND a.attnum = d.refobjsubid
            WHERE source_table.relname = 'factura'
              AND a.attname IN ('_subtotal', '_total')
              AND dependent_view.relkind = 'v'
            ORDER BY dependent_ns.nspname, dependent_view.relname
            """
        )
    ).fetchall()
    return [(row.view_schema, row.view_name, row.view_definition) for row in rows]


def _drop_views(views: list[tuple[str, str, str]]) -> None:
    for view_schema, view_name, _ in reversed(views):
        op.execute(sa.text(f'DROP VIEW IF EXISTS "{view_schema}"."{view_name}"'))


def _recreate_views(views: list[tuple[str, str, str]]) -> None:
    for view_schema, view_name, view_definition in views:
        op.execute(sa.text(f'CREATE VIEW "{view_schema}"."{view_name}" AS {view_definition}'))


def upgrade() -> None:
    dependent_views = _get_dependent_views()
    _drop_views(dependent_views)

    op.create_table(
        "factura_remediacion_auditoria",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("factura_id", sa.Integer(), sa.ForeignKey("factura.id"), nullable=False),
        sa.Column("subtotal_old", sa.Numeric(12, 2), nullable=True),
        sa.Column("subtotal_new", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_old", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_new", sa.Numeric(12, 2), nullable=True),
        sa.Column("tasa_cambio_old", sa.Numeric(10, 4), nullable=True),
        sa.Column("tasa_cambio_new", sa.Numeric(10, 4), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_factura_remediacion_auditoria_factura_id",
        "factura_remediacion_auditoria",
        ["factura_id"],
        unique=False,
    )
    op.create_index(
        "ix_factura_remediacion_auditoria_run_id",
        "factura_remediacion_auditoria",
        ["run_id"],
        unique=False,
    )

    op.alter_column(
        "factura",
        "_subtotal",
        existing_type=sa.Float(),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
        postgresql_using='"_subtotal"::numeric(12,2)',
    )
    op.alter_column(
        "factura",
        "_total",
        existing_type=sa.Float(),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
        postgresql_using='"_total"::numeric(12,2)',
    )
    _recreate_views(dependent_views)


def downgrade() -> None:
    dependent_views = _get_dependent_views()
    _drop_views(dependent_views)

    op.alter_column(
        "factura",
        "_total",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='"_total"::double precision',
    )
    op.alter_column(
        "factura",
        "_subtotal",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='"_subtotal"::double precision',
    )

    op.drop_index("ix_factura_remediacion_auditoria_run_id", table_name="factura_remediacion_auditoria")
    op.drop_index("ix_factura_remediacion_auditoria_factura_id", table_name="factura_remediacion_auditoria")
    op.drop_table("factura_remediacion_auditoria")
    _recreate_views(dependent_views)
