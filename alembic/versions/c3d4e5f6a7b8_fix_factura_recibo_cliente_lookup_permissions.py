"""Corrige lookup de cliente para factura

Revision ID: c3d4e5f6a7b8
Revises: 9f2c4d1a7b3e
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "9f2c4d1a7b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create or replace function ui_ref.factura_cliente_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_cliente('cliente', p_term, p_limit); $$;

create or replace function ui_ref.factura_cliente_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_cliente('cliente', p_ids); $$;
"""


DOWNGRADE_SQL = """
create or replace function ui_ref.factura_cliente_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_cliente('factura', p_term, p_limit); $$;

create or replace function ui_ref.factura_cliente_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_cliente('factura', p_ids); $$;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
