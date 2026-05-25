from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import DBAPIError

from openlogistic_erp.application.dashboard import DashboardService
from openlogistic_erp.domain.modelo.catalog_queries import CatalogQueryRequest
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import EstadoCamion, EstadoFactura, Factura, Moneda
from openlogistic_erp.infrastructure.persistence.reports.facturacion_por_cliente import FacturacionPorClienteReportReader
from openlogistic_erp.infrastructure.persistence.session_identity import authenticated_user
from tests.builders.modelo_seed import create_camion, create_cliente
from tests.builders.security_seed import create_permission, create_role, unique_value


RLS_PROTECTED_TABLES = (
    "cliente",
    "camion",
    "conductor",
    "furgon",
    "thermo",
    "ubicacion",
    "ruta",
    "tarifa_flete",
    "circuito",
    "viaje",
    "detalle_operacion",
    "factura",
    "detalle_factura",
    "recibo",
    "recibo_factura",
)


def test_business_tables_have_rls_enabled(engine):
    stmt = text(
            """
            select c.relname, c.relrowsecurity, c.relforcerowsecurity, count(p.polname) as policies
              from pg_class c
              join pg_namespace n on n.oid = c.relnamespace
              left join pg_policy p on p.polrelid = c.oid
             where n.nspname = 'public'
               and c.relname in :table_names
             group by c.relname, c.relrowsecurity, c.relforcerowsecurity
            """
    ).bindparams(bindparam("table_names", expanding=True))
    with engine.connect() as connection:
        rows = connection.execute(stmt, {"table_names": list(RLS_PROTECTED_TABLES)}).mappings().all()
    by_table = {row["relname"]: row for row in rows}

    missing = sorted(set(RLS_PROTECTED_TABLES) - set(by_table))
    without_rls = sorted(name for name, row in by_table.items() if not row["relrowsecurity"])
    without_policy = sorted(name for name, row in by_table.items() if int(row["policies"] or 0) == 0)

    assert missing == []
    assert without_rls == []
    assert without_policy == []


def test_anon_role_cannot_read_catalog_workflow_or_service_tables(db_connection, session_factory):
    seeded = _seed_business_rows(session_factory, prefix="RLS-ANON")
    _require_database_role(db_connection, "anon")

    for table_name, record_id in _seeded_table_ids(seeded).items():
        count = _count_record_as_role(db_connection, "anon", table_name, record_id)
        assert count == 0, f"anon pudo leer {table_name}#{record_id}"


def test_authenticated_session_can_only_read_resources_granted_by_rbac(
    auth_service,
    db_connection,
    session_factory,
):
    seeded = _seed_business_rows(session_factory, prefix="RLS-RBAC")
    _require_database_role(db_connection, "authenticated")
    user_id = _create_user_with_permissions(
        auth_service,
        session_factory,
        permissions=(("cliente", "leer"),),
    )

    with authenticated_user(user_id):
        with session_factory() as session:
            allowed = session.execute(
                text("select count(*) from public.cliente where id = :record_id"),
                {"record_id": seeded["cliente"]},
            ).scalar_one()
            denied = {
                table_name: session.execute(
                    text(f"select count(*) from public.{table_name} where id = :record_id"),
                    {"record_id": record_id},
                ).scalar_one()
                for table_name, record_id in _seeded_table_ids(seeded).items()
                if table_name != "cliente"
            }

    assert int(allowed) == 1
    assert denied == {name: 0 for name in denied}


def test_catalog_queries_are_empty_without_catalog_read_permission(
    auth_service,
    db_connection,
    session_factory,
):
    seeded = _seed_business_rows(session_factory, prefix="RLS-CATALOG")
    _require_database_role(db_connection, "authenticated")
    user_id = _create_user_with_permissions(
        auth_service,
        session_factory,
        permissions=(("cliente", "leer"),),
    )
    repository = SqlAlchemyCatalogQueryRepository(session_factory)

    with authenticated_user(user_id):
        allowed = repository.query_page(CatalogQueryRequest(catalog_name="cliente", page_size=100))
        denied = repository.query_page(CatalogQueryRequest(catalog_name="camion", page_size=100))

    assert any(row.get("id") == seeded["cliente"] for row in allowed.rows)
    assert all(row.get("id") != seeded["camion"] for row in denied.rows)


def test_reports_exports_and_dashboard_do_not_return_rows_without_matching_rbac(
    auth_service,
    db_connection,
    session_factory,
):
    seeded = _seed_business_rows(session_factory, prefix="RLS-SERVICES")
    _require_database_role(db_connection, "authenticated")
    user_id = _create_user_with_permissions(
        auth_service,
        session_factory,
        permissions=(("cliente", "leer"),),
    )

    with authenticated_user(user_id):
        report = FacturacionPorClienteReportReader(session_factory).generate(
            {
                "rango_fechas": ["2026-01-01", "2026-12-31"],
                "incluir_detalle": True,
            }
        )
        dashboard = DashboardService(session_factory).get_kpis()
        debt_rows = DashboardService(session_factory).get_client_debt_rows()

    report_rows = [
        row
        for table in report.tables
        for row in table.rows
        if row.get("cliente") == f"Cliente {seeded['prefix']}"
    ]
    assert report_rows == []
    assert dashboard["camiones_disponibles"] == 0
    assert dashboard["facturas_atrasadas"] == 0
    assert all(row["cliente_id"] != seeded["cliente"] for row in debt_rows)


def _seed_business_rows(session_factory, *, prefix: str) -> dict[str, int | str]:
    with session_factory() as session:
        cliente = create_cliente(
            session,
            nombre=f"Cliente {prefix}",
            ruc=f"{prefix}-RUC",
        )
        camion = create_camion(
            session,
            placa=f"{prefix}-CAMION",
            chasis=f"{prefix}-CAMION-CH",
            estado=EstadoCamion.ACTIVO,
        )
        factura = Factura(
            numero_factura=f"{prefix}-FACTURA",
            fecha_emision=datetime(2026, 1, 10, 8, 0, 0),
            cliente_id=cliente.id,
            dias_credito=10,
            moneda=Moneda.USD,
            _subtotal=Decimal("100.00"),
            _total=Decimal("100.00"),
            tasa_cambio=Decimal("1.0000"),
            estado=EstadoFactura.ATRASADA,
        )
        session.add(factura)
        session.commit()
        return {
            "prefix": prefix,
            "cliente": int(cliente.id),
            "camion": int(camion.id),
            "factura": int(factura.id),
        }


def _seeded_table_ids(seeded: dict[str, int | str]) -> dict[str, int]:
    return {
        table_name: int(record_id)
        for table_name, record_id in seeded.items()
        if table_name != "prefix"
    }


def _create_user_with_permissions(auth_service, session_factory, *, permissions: tuple[tuple[str, str], ...]) -> str:
    role_name = unique_value("rls_role")
    username = unique_value("rls_user")
    with session_factory() as session:
        permission_rows = [
            create_permission(session, resource=resource, action=action)
            for resource, action in permissions
        ]
        role = create_role(session, name=role_name, permissions=permission_rows)
        session.commit()

    user = auth_service.create_user(username=username, password="abc12345", roles=[role.name])
    return user.id


def _require_database_role(connection, role_name: str) -> None:
    exists = connection.execute(
        text("select 1 from pg_roles where rolname = :role_name"),
        {"role_name": role_name},
    ).scalar_one_or_none()
    if exists is None:
        pytest.skip(f"El rol PostgreSQL '{role_name}' no existe en este entorno.")


def _count_record_as_role(connection, role_name: str, table_name: str, record_id: int | str) -> int:
    try:
        connection.execute(text(f"set local role {role_name}"))
        value = connection.execute(
            text(f"select count(*) from public.{table_name} where id = :record_id"),
            {"record_id": record_id},
        ).scalar_one()
        return int(value or 0)
    except DBAPIError as exc:
        if _is_permission_denied(exc):
            return 0
        raise
    finally:
        connection.execute(text("reset role"))


def _is_permission_denied(exc: DBAPIError) -> bool:
    original = getattr(exc, "orig", None)
    pgcode = getattr(original, "pgcode", "")
    return pgcode in {"42501", "28000"}
