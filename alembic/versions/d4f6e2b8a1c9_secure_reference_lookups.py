"""Base de lookups seguros para FK display

Revision ID: d4f6e2b8a1c9
Revises: c7a2d9e4f1b0
Create Date: 2026-04-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d4f6e2b8a1c9"
down_revision: Union[str, Sequence[str], None] = "c7a2d9e4f1b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
set check_function_bodies = off;

create schema if not exists ui_ref;

grant usage on schema ui_ref to anon;
grant usage on schema ui_ref to authenticated;
grant usage on schema ui_ref to service_role;


create or replace function ui_ref.can_use_lookup(p_owner_resource text)
returns boolean
language sql
security definer
set search_path = auth, public
as $$
    select case
        when auth.uid() is null then false
        when exists (
            select 1
              from public.get_user_ids() u(id)
             where u.id = auth.uid()
               and public.is_superuser(u.id)
        ) then true
        else coalesce(
            (
                select up.grant_or_deny
                  from (
                        public.get_user_permissions() up(user_id, permission_id, grant_or_deny)
                        join public.get_permissions() p(id, resource, action)
                          on p.id = up.permission_id
                  )
                 where up.user_id = auth.uid()
                   and p.resource = lower(trim(p_owner_resource))
                   and p.action = 'leer'
            ),
            exists (
                select 1
                  from (
                        (public.get_user_roles() ur(user_id, role_name)
                         join public.get_role_permissions() rp(role_name, permission_id)
                           on rp.role_name = ur.role_name)
                        join public.get_permissions() p2(id, resource, action)
                          on p2.id = rp.permission_id
                  )
                 where ur.user_id = auth.uid()
                   and p2.resource = lower(trim(p_owner_resource))
                   and p2.action = 'leer'
            )
        )
    end;
$$;


create or replace function ui_ref.search_cliente(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, c.nombre::text as label
      from public.cliente c
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or c.nombre ilike ('%' || trim(p_term) || '%')
       )
     order by c.nombre asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_cliente(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, c.nombre::text as label
      from public.cliente c
     where ui_ref.can_use_lookup(p_owner_resource)
       and c.id = any(coalesce(p_ids, array[]::int[]))
     order by c.nombre asc, c.id asc;
$$;


create or replace function ui_ref.search_ubicacion(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select u.id, u.descripcion::text as label
      from public.ubicacion u
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or u.descripcion ilike ('%' || trim(p_term) || '%')
            or u.codigo ilike ('%' || trim(p_term) || '%')
       )
     order by u.descripcion asc, u.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_ubicacion(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select u.id, u.descripcion::text as label
      from public.ubicacion u
     where ui_ref.can_use_lookup(p_owner_resource)
       and u.id = any(coalesce(p_ids, array[]::int[]))
     order by u.descripcion asc, u.id asc;
$$;


create or replace function ui_ref.search_conductor(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, trim(concat_ws(' ', c.nombre, c.apellido))::text as label
      from public.conductor c
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or trim(concat_ws(' ', c.nombre, c.apellido)) ilike ('%' || trim(p_term) || '%')
       )
     order by trim(concat_ws(' ', c.nombre, c.apellido)) asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_conductor(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, trim(concat_ws(' ', c.nombre, c.apellido))::text as label
      from public.conductor c
     where ui_ref.can_use_lookup(p_owner_resource)
       and c.id = any(coalesce(p_ids, array[]::int[]))
     order by trim(concat_ws(' ', c.nombre, c.apellido)) asc, c.id asc;
$$;


create or replace function ui_ref.search_camion(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, c.placa::text as label
      from public.camion c
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or c.placa ilike ('%' || trim(p_term) || '%')
       )
     order by c.placa asc, c.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_camion(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id, c.placa::text as label
      from public.camion c
     where ui_ref.can_use_lookup(p_owner_resource)
       and c.id = any(coalesce(p_ids, array[]::int[]))
     order by c.placa asc, c.id asc;
$$;


create or replace function ui_ref.search_furgon(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select f.id, f.placa::text as label
      from public.furgon f
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or f.placa ilike ('%' || trim(p_term) || '%')
       )
     order by f.placa asc, f.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_furgon(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select f.id, f.placa::text as label
      from public.furgon f
     where ui_ref.can_use_lookup(p_owner_resource)
       and f.id = any(coalesce(p_ids, array[]::int[]))
     order by f.placa asc, f.id asc;
$$;


create or replace function ui_ref.search_thermo(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select t.id, t.codigo::text as label
      from public.thermo t
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or t.codigo ilike ('%' || trim(p_term) || '%')
       )
     order by t.codigo asc, t.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_thermo(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select t.id, t.codigo::text as label
      from public.thermo t
     where ui_ref.can_use_lookup(p_owner_resource)
       and t.id = any(coalesce(p_ids, array[]::int[]))
     order by t.codigo asc, t.id asc;
$$;


create or replace function ui_ref.search_ruta(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select r.id,
           trim(concat_ws(' -> ', origen.descripcion, destino.descripcion))::text as label
      from public.ruta r
      join public.ubicacion origen on origen.id = r.origen_id
      join public.ubicacion destino on destino.id = r.destino_id
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or trim(concat_ws(' -> ', origen.descripcion, destino.descripcion)) ilike ('%' || trim(p_term) || '%')
       )
     order by trim(concat_ws(' -> ', origen.descripcion, destino.descripcion)) asc, r.id asc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_ruta(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select r.id,
           trim(concat_ws(' -> ', origen.descripcion, destino.descripcion))::text as label
      from public.ruta r
      join public.ubicacion origen on origen.id = r.origen_id
      join public.ubicacion destino on destino.id = r.destino_id
     where ui_ref.can_use_lookup(p_owner_resource)
       and r.id = any(coalesce(p_ids, array[]::int[]))
     order by trim(concat_ws(' -> ', origen.descripcion, destino.descripcion)) asc, r.id asc;
$$;


create or replace function ui_ref.search_circuito(p_owner_resource text, p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id,
           concat('Circuito #', c.id, ' - ', to_char(c.fecha_inicio, 'YYYY-MM-DD HH24:MI'))::text as label
      from public.circuito c
     where ui_ref.can_use_lookup(p_owner_resource)
       and (
            nullif(trim(coalesce(p_term, '')), '') is null
            or concat('Circuito #', c.id, ' - ', to_char(c.fecha_inicio, 'YYYY-MM-DD HH24:MI')) ilike ('%' || trim(p_term) || '%')
       )
     order by c.fecha_inicio desc, c.id desc
     limit least(greatest(coalesce(p_limit, 20), 1), 100);
$$;


create or replace function ui_ref.resolve_circuito(p_owner_resource text, p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$
    select c.id,
           concat('Circuito #', c.id, ' - ', to_char(c.fecha_inicio, 'YYYY-MM-DD HH24:MI'))::text as label
      from public.circuito c
     where ui_ref.can_use_lookup(p_owner_resource)
       and c.id = any(coalesce(p_ids, array[]::int[]))
     order by c.fecha_inicio desc, c.id desc;
$$;


create or replace function ui_ref.ruta_origen_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_ubicacion('ruta', p_term, p_limit); $$;

create or replace function ui_ref.ruta_origen_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ubicacion('ruta', p_ids); $$;

create or replace function ui_ref.ruta_destino_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_ubicacion('ruta', p_term, p_limit); $$;

create or replace function ui_ref.ruta_destino_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ubicacion('ruta', p_ids); $$;

create or replace function ui_ref.tarifa_flete_cliente_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_cliente('tarifa_flete', p_term, p_limit); $$;

create or replace function ui_ref.tarifa_flete_cliente_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_cliente('tarifa_flete', p_ids); $$;

create or replace function ui_ref.tarifa_flete_ruta_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_ruta('tarifa_flete', p_term, p_limit); $$;

create or replace function ui_ref.tarifa_flete_ruta_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_ruta('tarifa_flete', p_ids); $$;

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

create or replace function ui_ref.recibo_cliente_search(p_term text, p_limit int default 20)
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.search_cliente('recibo', p_term, p_limit); $$;

create or replace function ui_ref.recibo_cliente_resolve(p_ids int[])
returns table(id integer, label text)
language sql
security definer
set search_path = public
as $$ select * from ui_ref.resolve_cliente('recibo', p_ids); $$;


grant execute on function ui_ref.can_use_lookup(text) to anon;
grant execute on function ui_ref.can_use_lookup(text) to authenticated;
grant execute on function ui_ref.can_use_lookup(text) to service_role;
grant execute on all functions in schema ui_ref to anon;
grant execute on all functions in schema ui_ref to authenticated;
grant execute on all functions in schema ui_ref to service_role;
"""


DOWNGRADE_SQL = """
drop function if exists ui_ref.recibo_cliente_resolve(int[]);
drop function if exists ui_ref.recibo_cliente_search(text, int);
drop function if exists ui_ref.factura_cliente_resolve(int[]);
drop function if exists ui_ref.factura_cliente_search(text, int);
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
drop function if exists ui_ref.viaje_cliente_resolve(int[]);
drop function if exists ui_ref.viaje_destino_resolve(int[]);
drop function if exists ui_ref.viaje_destino_search(text, int, int);
drop function if exists ui_ref.viaje_origen_resolve(int[]);
drop function if exists ui_ref.viaje_origen_search(text, int, int);
drop function if exists ui_ref.viaje_cliente_search(text, int, text);
drop function if exists ui_ref.tarifa_flete_ruta_resolve(int[]);
drop function if exists ui_ref.tarifa_flete_ruta_search(text, int);
drop function if exists ui_ref.tarifa_flete_cliente_resolve(int[]);
drop function if exists ui_ref.tarifa_flete_cliente_search(text, int);
drop function if exists ui_ref.ruta_destino_resolve(int[]);
drop function if exists ui_ref.ruta_destino_search(text, int);
drop function if exists ui_ref.ruta_origen_resolve(int[]);
drop function if exists ui_ref.ruta_origen_search(text, int);

drop function if exists ui_ref.resolve_circuito(text, int[]);
drop function if exists ui_ref.search_circuito(text, text, int);
drop function if exists ui_ref.resolve_ruta(text, int[]);
drop function if exists ui_ref.search_ruta(text, text, int);
drop function if exists ui_ref.resolve_thermo(text, int[]);
drop function if exists ui_ref.search_thermo(text, text, int);
drop function if exists ui_ref.resolve_furgon(text, int[]);
drop function if exists ui_ref.search_furgon(text, text, int);
drop function if exists ui_ref.resolve_camion(text, int[]);
drop function if exists ui_ref.search_camion(text, text, int);
drop function if exists ui_ref.resolve_conductor(text, int[]);
drop function if exists ui_ref.search_conductor(text, text, int);
drop function if exists ui_ref.resolve_ubicacion(text, int[]);
drop function if exists ui_ref.search_ubicacion(text, text, int);
drop function if exists ui_ref.resolve_cliente(text, int[]);
drop function if exists ui_ref.search_cliente(text, text, int);

drop function if exists ui_ref.can_use_lookup(text);
drop schema if exists ui_ref;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
