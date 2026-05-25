"""Convierte porcentaje de impuesto y monto_pagado de recibo_factura a numeric

Revision ID: c7a2d9e4f1b0
Revises: 9c4f3b2a1d7e
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a2d9e4f1b0"
down_revision: Union[str, None] = "9c4f3b2a1d7e"
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

    op.alter_column(
        "impuesto",
        "porcentaje",
        existing_type=sa.Float(),
        type_=sa.Numeric(8, 2),
        existing_nullable=False,
        postgresql_using='"porcentaje"::numeric(8,2)',
    )
    op.alter_column(
        "recibo_factura",
        "monto_pagado",
        existing_type=sa.Float(),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
        postgresql_using='"monto_pagado"::numeric(12,2)',
    )

    _recreate_views(dependent_views)


def downgrade() -> None:
    dependent_views = _get_dependent_views()
    _drop_views(dependent_views)

    op.alter_column(
        "recibo_factura",
        "monto_pagado",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='"monto_pagado"::double precision',
    )
    op.alter_column(
        "impuesto",
        "porcentaje",
        existing_type=sa.Numeric(8, 2),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='"porcentaje"::double precision',
    )

    _recreate_views(dependent_views)
