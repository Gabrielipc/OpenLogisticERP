"""unifica viaticos monto/moneda en viaje

Revision ID: b1a3f5c7d9e2
Revises: 131e13c942a6
Create Date: 2025-12-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1a3f5c7d9e2"
down_revision: Union[str, None] = "131e13c942a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    moneda_enum = sa.Enum(name="moneda")

    op.add_column("viaje", sa.Column("viaticos_monto", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "viaje",
        sa.Column(
            "viaticos_moneda",
            moneda_enum,
            nullable=False,
            server_default=sa.text("'USD'::moneda"),
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE viaje
            SET viaticos_monto = COALESCE(viaticos, viaticos_importacion, retorno_viaticos)
            """
        )
    )


def downgrade() -> None:
    op.drop_column("viaje", "viaticos_moneda")
    op.drop_column("viaje", "viaticos_monto")
