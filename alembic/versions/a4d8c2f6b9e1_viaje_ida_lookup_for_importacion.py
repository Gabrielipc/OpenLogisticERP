"""Agrega lookup de viaje de ida para importacion

Revision ID: a4d8c2f6b9e1
Revises: b2c4d6e8f0a1
Create Date: 2026-05-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "a4d8c2f6b9e1"
down_revision: Union[str, Sequence[str], None] = "b2c4d6e8f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create or replace function ui_ref.viaje_ida_search(
    p_term text,
    p_limit int default 20,
    p_conductor_id int default null,
    p_camion_id int default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    with same_driver as (
        select exists (
            select 1
              from public.viaje v
             where ui_ref.can_use_lookup('viaje')
               and v.tipo_viaje::text = 'EXPOR'
               and p_conductor_id is not null
               and v.conductor_id = p_conductor_id
               and not exists (
                    select 1
                      from public.viaje vuelta
                     where vuelta._circuito_id = v._circuito_id
                       and vuelta.id <> v.id
                       and vuelta.tipo_viaje::text in ('IMPOR', 'VACIO')
               )
        ) as has_candidates
    )
    select v.id,
           concat_ws(
               ' - ',
               coalesce(nullif(v.referencia, ''), 'Viaje #' || v.id::text),
               to_char(v.fecha_posicionamiento, 'YYYY-MM-DD HH24:MI'),
               nullif(trim(coalesce(c.nombre, '') || ' ' || coalesce(c.apellido, '')), ''),
               ca.placa
           )::text as label
      from public.viaje v
      left join public.conductor c on c.id = v.conductor_id
      left join public.camion ca on ca.id = v.camion_id
      cross join same_driver sd
     where ui_ref.can_use_lookup('viaje')
       and v.tipo_viaje::text = 'EXPOR'
       and not exists (
            select 1
              from public.viaje vuelta
             where vuelta._circuito_id = v._circuito_id
               and vuelta.id <> v.id
               and vuelta.tipo_viaje::text in ('IMPOR', 'VACIO')
       )
       and (
            (sd.has_candidates and p_conductor_id is not null and v.conductor_id = p_conductor_id)
            or (
                not sd.has_candidates
                and p_camion_id is not null
                and v.camion_id = p_camion_id
            )
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or v.referencia ilike ('%' || trim(p_term) || '%')
            or v.descripcion ilike ('%' || trim(p_term) || '%')
            or c.nombre ilike ('%' || trim(p_term) || '%')
            or c.apellido ilike ('%' || trim(p_term) || '%')
            or ca.placa ilike ('%' || trim(p_term) || '%')
       )
     order by v.fecha_posicionamiento desc nulls last, v.id desc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_ida_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select v.id,
           concat_ws(
               ' - ',
               coalesce(nullif(v.referencia, ''), 'Viaje #' || v.id::text),
               to_char(v.fecha_posicionamiento, 'YYYY-MM-DD HH24:MI'),
               nullif(trim(coalesce(c.nombre, '') || ' ' || coalesce(c.apellido, '')), ''),
               ca.placa
           )::text as label
      from public.viaje v
      left join public.conductor c on c.id = v.conductor_id
      left join public.camion ca on ca.id = v.camion_id
     where ui_ref.can_use_lookup('viaje')
       and v.id = any(p_ids)
     order by v.id asc;
$$;

grant execute on function ui_ref.viaje_ida_search(text, int, int, int) to anon;
grant execute on function ui_ref.viaje_ida_search(text, int, int, int) to authenticated;
grant execute on function ui_ref.viaje_ida_search(text, int, int, int) to service_role;
grant execute on function ui_ref.viaje_ida_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_ida_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_ida_resolve(int[]) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.viaje_ida_resolve(int[]);
drop function if exists ui_ref.viaje_ida_search(text, int, int, int);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
