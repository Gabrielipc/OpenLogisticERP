"""add es_triangulado to movimiento_adicional

Revision ID: b2c4d6e8f0a1
Revises: a8f7c6d5e4b3
Create Date: 2026-05-05

The legacy consumption analysis inferred triangulated movements from free-text
descriptions. This column makes the business marker explicit while preserving
legacy rows through a one-time text backfill.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b2c4d6e8f0a1"
down_revision = "a8f7c6d5e4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movimiento_adicional",
        sa.Column("es_triangulado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE movimiento_adicional
        SET es_triangulado = true
        WHERE descripcion IS NOT NULL
          AND lower(descripcion) LIKE '%triangulado%'
        """
    )
    op.alter_column("movimiento_adicional", "es_triangulado", server_default=None)


def downgrade() -> None:
    op.drop_column("movimiento_adicional", "es_triangulado")
