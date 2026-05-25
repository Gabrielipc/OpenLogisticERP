"""Repara lookup seguro de thermo para viaje

Revision ID: 4b1816e0a2b9
Revises: e6a6290a7f4c
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "4b1816e0a2b9"
down_revision: Union[str, Sequence[str], None] = "e6a6290a7f4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create or replace function ui_ref.viaje_thermo_search(
    p_term text,
    p_limit int default 20,
    p_include_agregados boolean default false
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select t.id, t.codigo::text as label
      from public.thermo t
     where ui_ref.can_use_lookup('viaje')
       and (
            lower(t.estado::text) = 'activo'
            or (coalesce(p_include_agregados, false) and lower(t.estado::text) = 'agregado')
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or t.codigo ilike ('%' || trim(p_term) || '%')
       )
     order by t.codigo asc, t.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_thermo_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_thermo('viaje', p_ids); $$;

grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to service_role;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.viaje_thermo_resolve(int[]);
drop function if exists ui_ref.viaje_thermo_search(text, int, boolean);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
