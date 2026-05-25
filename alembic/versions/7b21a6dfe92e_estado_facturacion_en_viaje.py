from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7b21a6dfe92e"
down_revision: Union[str, None] = "3a65e4fd7445"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Usa valores CONSISTENTES (aquí en MAYÚSCULAS)
ESTADO_FACTURACION_ENUM = sa.Enum(
    "REGISTRADO",
    "FACTURADO",
    "SIN_FACTURA",
    name="estadofacturacion",
)

def upgrade() -> None:
    bind = op.get_bind()
    # 1) Crear el tipo ENUM si no existe
    ESTADO_FACTURACION_ENUM.create(bind, checkfirst=True)

    # 2) Añadir la columna como NULLABLE (temporal) sin default,
    #    hacemos backfill y luego NOT NULL + default
    op.add_column(
        "viaje",
        sa.Column("estado_facturacion", ESTADO_FACTURACION_ENUM, nullable=True),
    )

    # 3) Backfill principal: donde hay cliente (join con cliente)
    #    OJO: casteo de literales al tipo enum con ::estadofacturacion
    op.execute(
        sa.text(
            """
            UPDATE viaje AS v
            SET estado_facturacion = CASE
                WHEN v._facturado IS TRUE THEN 'FACTURADO'::estadofacturacion
                WHEN c.facturable IS FALSE THEN 'SIN_FACTURA'::estadofacturacion
                ELSE 'REGISTRADO'::estadofacturacion
            END
            FROM cliente AS c
            WHERE c.id = v.cliente_id
            """
        )
    )

    # 4) Backfill para viajes sin cliente (cliente_id IS NULL)
    op.execute(
        sa.text(
            """
            UPDATE viaje
            SET estado_facturacion = 'SIN_FACTURA'::estadofacturacion
            WHERE cliente_id IS NULL AND estado_facturacion IS NULL
            """
        )
    )

    # 5) Cualquier remanente que siga NULL => REGISTRADO
    op.execute(
        sa.text(
            """
            UPDATE viaje
            SET estado_facturacion = 'REGISTRADO'::estadofacturacion
            WHERE estado_facturacion IS NULL
            """
        )
    )

    # 6) Hacer NOT NULL + server_default consistente (casteado)
    op.alter_column(
        "viaje",
        "estado_facturacion",
        existing_type=ESTADO_FACTURACION_ENUM,
        nullable=False,
        server_default=sa.text("'REGISTRADO'::estadofacturacion"),
    )

    # 7) Índice
    op.create_index(
        "ix_viaje_estado_facturacion",
        "viaje",
        ["estado_facturacion"],
    )

    # 8) Eliminar booleano antiguo
    op.drop_column("viaje", "_facturado")


def downgrade() -> None:
    # 1) Reponer el booleano (default FALSE para evitar NULLs)
    op.add_column(
        "viaje",
        sa.Column(
            "_facturado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )

    # 2) Backfill desde el enum (TRUE sólo si FACTURADO)
    op.execute(
        sa.text(
            """
            UPDATE viaje
            SET _facturado = CASE
                WHEN estado_facturacion = 'FACTURADO' THEN TRUE
                ELSE FALSE
            END
            """
        )
    )

    # 3) Índice fuera
    op.drop_index("ix_viaje_estado_facturacion", table_name="viaje")

    # 4) Quitar columna enum
    op.drop_column("viaje", "estado_facturacion")

    # 5) Borrar el tipo enum
    ESTADO_FACTURACION_ENUM.drop(op.get_bind(), checkfirst=True)
