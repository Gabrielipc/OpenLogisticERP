"""Repara lookups seguros de viaje

Revision ID: 7c9e3f1a6d44
Revises: 4b1816e0a2b9
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op

revision: str = "7c9e3f1a6d44"
down_revision: Union[str, Sequence[str], None] = "4b1816e0a2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create or replace function ui_ref.viaje_cliente_search(
    p_term text,
    p_limit int default 20,
    p_trip_type text default null
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    with destinos_ancla as (
        select unnest(array['Nicaragua', 'Matadero GINSA', 'San Martin', 'MACESA']::text[]) as descripcion
    ),
    clientes_importacion as (
        select distinct tf.cliente_id
          from public.tarifa_flete tf
          join public.ruta r on r.id = tf.ruta_id
          join public.ubicacion u on u.id = r.destino_id
          join destinos_ancla da on lower(trim(da.descripcion)) = lower(trim(u.descripcion))
    ),
    clientes_exportacion as (
        select distinct tf.cliente_id
          from public.tarifa_flete tf
          join public.ruta r on r.id = tf.ruta_id
          join public.ubicacion u on u.id = r.origen_id
          join destinos_ancla da on lower(trim(da.descripcion)) = lower(trim(u.descripcion))
    )
    select c.id, c.nombre::text as label
      from public.cliente c
     where ui_ref.can_use_lookup('viaje')
       and (
            nullif(trim(coalesce(p_trip_type, '')), '') is null
            or (
                lower(trim(p_trip_type)) = 'importacion'
                and c.id in (select cliente_id from clientes_importacion)
            )
            or (
                lower(trim(p_trip_type)) = 'exportacion'
                and c.id in (select cliente_id from clientes_exportacion)
            )
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or c.nombre ilike ('%' || trim(p_term) || '%')
       )
     order by c.nombre asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_cliente_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_cliente('viaje', p_ids); $$;

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

create or replace function ui_ref.viaje_origen_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ubicacion('viaje', p_ids); $$;

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

create or replace function ui_ref.viaje_destino_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ubicacion('viaje', p_ids); $$;

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

create or replace function ui_ref.viaje_conductor_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_conductor('viaje', p_ids); $$;

create or replace function ui_ref.viaje_furgon_search(
    p_term text,
    p_limit int default 20,
    p_include_agregados boolean default false
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select f.id, f.placa::text as label
      from public.furgon f
     where ui_ref.can_use_lookup('viaje')
       and (
            lower(f.estado::text) = 'activo'
            or (coalesce(p_include_agregados, false) and lower(f.estado::text) = 'agregado')
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or f.placa ilike ('%' || trim(p_term) || '%')
       )
     order by f.placa asc, f.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_furgon_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_furgon('viaje', p_ids); $$;

create or replace function ui_ref.viaje_camion_search(
    p_term text,
    p_limit int default 20,
    p_include_agregados boolean default false
)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, c.placa::text as label
      from public.camion c
     where ui_ref.can_use_lookup('viaje')
       and (
            lower(c.estado::text) = 'activo'
            or (coalesce(p_include_agregados, false) and lower(c.estado::text) = 'agregado')
       )
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or c.placa ilike ('%' || trim(p_term) || '%')
       )
     order by c.placa asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;

create or replace function ui_ref.viaje_camion_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_camion('viaje', p_ids); $$;

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

create or replace function ui_ref.viaje_ruta_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_ruta('viaje', p_term, p_limit); $$;

create or replace function ui_ref.viaje_ruta_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ruta('viaje', p_ids); $$;

create or replace function ui_ref.viaje_circuito_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_circuito('viaje', p_term, p_limit); $$;

create or replace function ui_ref.viaje_circuito_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_circuito('viaje', p_ids); $$;

grant execute on function ui_ref.viaje_cliente_search(text, int, text) to anon;
grant execute on function ui_ref.viaje_cliente_search(text, int, text) to authenticated;
grant execute on function ui_ref.viaje_cliente_search(text, int, text) to service_role;
grant execute on function ui_ref.viaje_cliente_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_cliente_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_cliente_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_origen_search(text, int, int) to anon;
grant execute on function ui_ref.viaje_origen_search(text, int, int) to authenticated;
grant execute on function ui_ref.viaje_origen_search(text, int, int) to service_role;
grant execute on function ui_ref.viaje_origen_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_origen_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_origen_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_destino_search(text, int, int) to anon;
grant execute on function ui_ref.viaje_destino_search(text, int, int) to authenticated;
grant execute on function ui_ref.viaje_destino_search(text, int, int) to service_role;
grant execute on function ui_ref.viaje_destino_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_destino_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_destino_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_conductor_search(text, int, boolean) to service_role;
grant execute on function ui_ref.viaje_conductor_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_conductor_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_conductor_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_furgon_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_furgon_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_furgon_search(text, int, boolean) to service_role;
grant execute on function ui_ref.viaje_furgon_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_furgon_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_furgon_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_camion_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_camion_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_camion_search(text, int, boolean) to service_role;
grant execute on function ui_ref.viaje_camion_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_camion_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_camion_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to anon;
grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to authenticated;
grant execute on function ui_ref.viaje_thermo_search(text, int, boolean) to service_role;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_thermo_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_ruta_search(text, int) to anon;
grant execute on function ui_ref.viaje_ruta_search(text, int) to authenticated;
grant execute on function ui_ref.viaje_ruta_search(text, int) to service_role;
grant execute on function ui_ref.viaje_ruta_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_ruta_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_ruta_resolve(int[]) to service_role;

grant execute on function ui_ref.viaje_circuito_search(text, int) to anon;
grant execute on function ui_ref.viaje_circuito_search(text, int) to authenticated;
grant execute on function ui_ref.viaje_circuito_search(text, int) to service_role;
grant execute on function ui_ref.viaje_circuito_resolve(int[]) to anon;
grant execute on function ui_ref.viaje_circuito_resolve(int[]) to authenticated;
grant execute on function ui_ref.viaje_circuito_resolve(int[]) to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.viaje_circuito_resolve(int[]);
drop function if exists ui_ref.viaje_circuito_search(text, int);
drop function if exists ui_ref.viaje_ruta_resolve(int[]);
drop function if exists ui_ref.viaje_ruta_search(text, int);
drop function if exists ui_ref.viaje_thermo_resolve(int[]);
drop function if exists ui_ref.viaje_thermo_search(text, int, boolean);
drop function if exists ui_ref.viaje_camion_resolve(int[]);
drop function if exists ui_ref.viaje_camion_search(text, int, boolean);
drop function if exists ui_ref.viaje_furgon_resolve(int[]);
drop function if exists ui_ref.viaje_furgon_search(text, int, boolean);
drop function if exists ui_ref.viaje_conductor_resolve(int[]);
drop function if exists ui_ref.viaje_conductor_search(text, int, boolean);
drop function if exists ui_ref.viaje_destino_resolve(int[]);
drop function if exists ui_ref.viaje_destino_search(text, int, int);
drop function if exists ui_ref.viaje_origen_resolve(int[]);
drop function if exists ui_ref.viaje_origen_search(text, int, int);
drop function if exists ui_ref.viaje_cliente_resolve(int[]);
drop function if exists ui_ref.viaje_cliente_search(text, int, text);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
