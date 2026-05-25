"""Agrega tasa de cambio a recibo

Revision ID: a8f7c6d5e4b3
Revises: f1a2b3c4d5e6
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8f7c6d5e4b3"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recibo",
        sa.Column(
            "tasa_cambio",
            sa.Numeric(10, 4),
            nullable=False,
            server_default=sa.text("1.0000"),
        ),
    )


def downgrade() -> None:
    op.drop_column("recibo", "tasa_cambio")
