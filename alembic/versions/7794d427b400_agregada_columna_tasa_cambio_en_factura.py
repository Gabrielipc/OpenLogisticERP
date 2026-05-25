"""Agregada columna tasa_cambio en factura

Revision ID: 7794d427b400
Revises: b1a3f5c7d9e2
Create Date: 2026-02-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7794d427b400'
down_revision: Union[str, None] = 'b1a3f5c7d9e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'factura',
        sa.Column('tasa_cambio', sa.Numeric(10, 4), nullable=False, server_default='1.0000')
    )


def downgrade() -> None:
    op.drop_column('factura', 'tasa_cambio')
