"""Ajusta lookup seguro de conductor por tipo de viaje

Revision ID: 9f2c4d1a7b3e
Revises: 7c9e3f1a6d44
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "9f2c4d1a7b3e"
down_revision: Union[str, Sequence[str], None] = "7c9e3f1a6d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
drop function if exists ui_ref.viaje_conductor_search(text, int, boolean);

create or replace function ui_ref.viaje_conductor_search(
    p_term text,
    p_limit int default 20,
    p_trip_type text default null,
    p_include_agregados boolean default false
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id,
           trim(concat_ws(' ', split_part(c.nombre, ' ', 1), split_part(c.apellido, ' ', 1)))
           || case when lower(c.estado::text) = 'agregado' then ' (AGREGADO)' else '' end as label
      from public.conductor c
     where ui_ref.can_use_lookup('viaje')
       and (
            (
                nullif(trim(coalesce(p_trip_type, '')), '') is null
                and lower(c.estado::text) in ('disponible', 'esperando instrucciones', 'instrucciones')
            )
            or (
                lower(trim(coalesce(p_trip_type, ''))) = 'exportacion'
                and lower(c.estado::text) = 'disponible'
            )
            or (
                lower(trim(coalesce(p_trip_type, ''))) = 'importacion'
                and lower(c.estado::text) in ('esperando instrucciones', 'instrucciones')
            )
            or (
                coalesce(p_include_agregados, false)
                and lower(c.estado::text) = 'agregado'
            )
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or trim(concat_ws(' ', c.nombre, c.apellido)) ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

grant execute on function ui_ref.viaje_conductor_search(text, int, text, boolean) to anon;
grant execute on function ui_ref.viaje_conductor_search(text, int, text, boolean) to authenticated;
grant execute on function ui_ref.viaje_conductor_search(text, int, text, boolean) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.viaje_conductor_search(text, int, text, boolean);

create or replace function ui_ref.viaje_conductor_search(
    p_term text,
    p_limit int default 20,
    p_include_agregados boolean default false
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id,
           trim(concat_ws(' ', split_part(c.nombre, ' ', 1), split_part(c.apellido, ' ', 1)))
           || case when lower(c.estado::text) = 'agregado' then ' (AGREGADO)' else '' end as label
      from public.conductor c
     where ui_ref.can_use_lookup('viaje')
       and (
            lower(c.estado::text) in ('esperando instrucciones', 'instrucciones')
            or (coalesce(p_include_agregados, false) and lower(c.estado::text) = 'agregado')
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or trim(concat_ws(' ', c.nombre, c.apellido)) ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to service_role;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
