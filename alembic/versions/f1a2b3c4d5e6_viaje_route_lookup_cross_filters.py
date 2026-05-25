"""Amplia lookups de ruta de viaje con filtros cruzados

Revision ID: f1a2b3c4d5e6
Revises: c3d4e5f6a7b8
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
drop function if exists ui_ref.viaje_origen_search(text, int, int);
drop function if exists ui_ref.viaje_destino_search(text, int, int);

create or replace function ui_ref.viaje_origen_search(
    p_term text,
    p_limit int default 20,
    p_cliente_id int default null,
    p_destino_id int default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select distinct u.id, u.descripcion::text as label
      from public.ubicacion u
      join public.ruta r on r.origen_id = u.id
      join public.tarifa_flete tf on tf.ruta_id = r.id
     where ui_ref.can_use_lookup('viaje')
       and p_cliente_id is not null
       and tf.cliente_id = p_cliente_id
       and (
            p_destino_id is null
            or r.destino_id = p_destino_id
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or u.descripcion ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, u.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_destino_search(
    p_term text,
    p_limit int default 20,
    p_cliente_id int default null,
    p_origen_id int default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select distinct u.id, u.descripcion::text as label
      from public.ubicacion u
      join public.ruta r on r.destino_id = u.id
      join public.tarifa_flete tf on tf.ruta_id = r.id
     where ui_ref.can_use_lookup('viaje')
       and p_cliente_id is not null
       and tf.cliente_id = p_cliente_id
       and (
            p_origen_id is null
            or r.origen_id = p_origen_id
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or u.descripcion ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, u.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

grant execute on function ui_ref.viaje_origen_search(text, int, int, int) to anon;
grant execute on function ui_ref.viaje_origen_search(text, int, int, int) to authenticated;
grant execute on function ui_ref.viaje_origen_search(text, int, int, int) to service_role;

grant execute on function ui_ref.viaje_destino_search(text, int, int, int) to anon;
grant execute on function ui_ref.viaje_destino_search(text, int, int, int) to authenticated;
grant execute on function ui_ref.viaje_destino_search(text, int, int, int) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.viaje_origen_search(text, int, int, int);
drop function if exists ui_ref.viaje_destino_search(text, int, int, int);

create or replace function ui_ref.viaje_origen_search(
    p_term text,
    p_limit int default 20,
    p_cliente_id int default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select distinct u.id, u.descripcion::text as label
      from public.ubicacion u
      join public.ruta r on r.origen_id = u.id
      join public.tarifa_flete tf on tf.ruta_id = r.id
     where ui_ref.can_use_lookup('viaje')
       and p_cliente_id is not null
       and tf.cliente_id = p_cliente_id
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or u.descripcion ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, u.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_destino_search(
    p_term text,
    p_limit int default 20,
    p_cliente_id int default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select distinct u.id, u.descripcion::text as label
      from public.ubicacion u
      join public.ruta r on r.destino_id = u.id
      join public.tarifa_flete tf on tf.ruta_id = r.id
     where ui_ref.can_use_lookup('viaje')
       and p_cliente_id is not null
       and tf.cliente_id = p_cliente_id
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or u.descripcion ilike ('%' || trim(p_term) || '%')
       )
     order by label asc, u.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

grant execute on function ui_ref.viaje_origen_search(text, int, int) to anon;
grant execute on function ui_ref.viaje_origen_search(text, int, int) to authenticated;
grant execute on function ui_ref.viaje_origen_search(text, int, int) to service_role;

grant execute on function ui_ref.viaje_destino_search(text, int, int) to anon;
grant execute on function ui_ref.viaje_destino_search(text, int, int) to authenticated;
grant execute on function ui_ref.viaje_destino_search(text, int, int) to service_role;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
