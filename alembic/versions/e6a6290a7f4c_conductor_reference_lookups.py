"""Agrega lookups seguros de conductor para FK display

Revision ID: e6a6290a7f4c
Revises: d4f6e2b8a1c9
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e6a6290a7f4c"
down_revision: Union[str, Sequence[str], None] = "d4f6e2b8a1c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create or replace function ui_ref.conductor_camion_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_camion('conductor', p_term, p_limit); $$;

create or replace function ui_ref.conductor_camion_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_camion('conductor', p_ids); $$;

create or replace function ui_ref.conductor_furgon_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_furgon('conductor', p_term, p_limit); $$;

create or replace function ui_ref.conductor_furgon_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_furgon('conductor', p_ids); $$;

create or replace function ui_ref.conductor_thermo_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_thermo('conductor', p_term, p_limit); $$;

create or replace function ui_ref.conductor_thermo_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_thermo('conductor', p_ids); $$;

grant execute on function ui_ref.conductor_camion_search(text, int) to anon;
grant execute on function ui_ref.conductor_camion_search(text, int) to authenticated;
grant execute on function ui_ref.conductor_camion_search(text, int) to service_role;
grant execute on function ui_ref.conductor_camion_resolve(int[]) to anon;
grant execute on function ui_ref.conductor_camion_resolve(int[]) to authenticated;
grant execute on function ui_ref.conductor_camion_resolve(int[]) to service_role;

grant execute on function ui_ref.conductor_furgon_search(text, int) to anon;
grant execute on function ui_ref.conductor_furgon_search(text, int) to authenticated;
grant execute on function ui_ref.conductor_furgon_search(text, int) to service_role;
grant execute on function ui_ref.conductor_furgon_resolve(int[]) to anon;
grant execute on function ui_ref.conductor_furgon_resolve(int[]) to authenticated;
grant execute on function ui_ref.conductor_furgon_resolve(int[]) to service_role;

grant execute on function ui_ref.conductor_thermo_search(text, int) to anon;
grant execute on function ui_ref.conductor_thermo_search(text, int) to authenticated;
grant execute on function ui_ref.conductor_thermo_search(text, int) to service_role;
grant execute on function ui_ref.conductor_thermo_resolve(int[]) to anon;
grant execute on function ui_ref.conductor_thermo_resolve(int[]) to authenticated;
grant execute on function ui_ref.conductor_thermo_resolve(int[]) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.conductor_thermo_resolve(int[]);
drop function if exists ui_ref.conductor_thermo_search(text, int);
drop function if exists ui_ref.conductor_furgon_resolve(int[]);
drop function if exists ui_ref.conductor_furgon_search(text, int);
drop function if exists ui_ref.conductor_camion_resolve(int[]);
drop function if exists ui_ref.conductor_camion_search(text, int);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
