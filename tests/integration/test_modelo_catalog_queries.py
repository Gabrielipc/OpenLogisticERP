from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import text

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.domain.modelo.catalog_queries import (
    CatalogFilter,
    CatalogFilterOperator,
    CatalogQueryRequest,
    CatalogSort,
    CatalogSortDirection,
)
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.conductor import Conductor
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.ubicacion import Ubicacion
from openlogistic_erp.infrastructure.persistence.session_identity import authenticated_user
from tests.builders.modelo_seed import build_viaje_export_payload, create_ruta, seed_viaje_dependencies
from tests.builders.security_seed import create_permission, create_role


def _create_cliente(modelo_workflow, suffix: str, facturable: bool, *, token: str):
    return modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente {token} {suffix}",
            "ruc": f"TEST-{token}-{suffix}",
            "direccion": f"Dir {token} {suffix}",
            "facturable": facturable,
        },
    )


def test_catalog_query_service_supports_pagination_sort_and_filters(modelo_workflow, session_factory):
    token = uuid4().hex[:8].upper()
    _create_cliente(modelo_workflow, "301", True, token=token)
    _create_cliente(modelo_workflow, "302", False, token=token)
    _create_cliente(modelo_workflow, "303", True, token=token)

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    first_page = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="cliente",
            page=0,
            page_size=2,
            sort=CatalogSort(field="nombre", direction=CatalogSortDirection.DESC),
            filters=(
                CatalogFilter(field="facturable", operator=CatalogFilterOperator.EQ, value=True),
                CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=token),
            ),
        )
    )

    assert first_page.total_count == 2
    assert len(first_page.rows) == 2
    assert first_page.rows[0]["nombre"] == f"Cliente {token} 303"
    assert first_page.rows[1]["nombre"] == f"Cliente {token} 301"


def test_catalog_query_service_contains_filter(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    _create_cliente(modelo_workflow, "401", True, token=token)
    created = _create_cliente(modelo_workflow, "402", True, token=token)

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    result = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="cliente",
            filters=(CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=f"{token} 402"),),
        )
    )

    assert result.total_count == 1
    assert result.rows[0]["ruc"] == created["ruc"]


def test_catalog_query_service_resolves_secure_fk_labels_for_viaje(
    session_factory,
    modelo_workflow,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        viaje = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
        viaje_permission = create_permission(session, "viaje", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[viaje_permission])
        session.commit()

    user = auth_service.create_user(
        username=f"ops_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    with authenticated_user(user.id):
        result = query_service.query_page(
            CatalogQueryRequest(
                catalog_name="viaje",
                filters=(CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=viaje["id"]),),
            )
        )

        assert result.total_count == 1
        row = result.rows[0]
        assert row["cliente_id"] == deps["cliente_id"]
        assert row["cliente_label"]
        assert row["conductor_label"]
        assert row["ruta_label"]

        with session_factory() as session:
            try:
                visible_clientes = session.execute(text("select count(*) from public.cliente")).scalar_one()
            except Exception as exc:
                assert "permission denied" in str(exc).lower()
            else:
                assert visible_clientes == 0


def test_catalog_query_service_locates_record_page_with_filters(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    for index in range(8):
        _create_cliente(modelo_workflow, f"5{index:02d}", True, token=token)

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    result = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="cliente",
            page=1,
            page_size=5,
            sort=CatalogSort(field="id", direction=CatalogSortDirection.ASC),
            filters=(CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=token),),
        )
    )
    target_id = int(result.rows[-1]["id"])

    page = query_service.locate_record_page(
        "cliente",
        target_id,
        page_size=5,
        sort=CatalogSort(field="id", direction=CatalogSortDirection.ASC),
        filters=(CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=token),),
    )

    assert page == 1


def test_catalog_query_service_uses_primary_key_tiebreaker_when_sort_is_not_unique(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    created_records = [
        _create_cliente(modelo_workflow, f"6{index:02d}", True, token=token)
        for index in range(8)
    ]
    newest_id = int(created_records[-1]["id"])

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    page = query_service.locate_record_page(
        "cliente",
        newest_id,
        page_size=5,
        sort=CatalogSort(field="facturable", direction=CatalogSortDirection.ASC),
        filters=(CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=token),),
    )

    second_page = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="cliente",
            page=1,
            page_size=5,
            sort=CatalogSort(field="facturable", direction=CatalogSortDirection.ASC),
            filters=(CatalogFilter(field="nombre", operator=CatalogFilterOperator.CONTAINS, value=token),),
        )
    )

    assert page == 1
    assert int(second_page.rows[-1]["id"]) == newest_id


def test_catalog_query_service_search_text_uses_multiple_marked_fields(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente Search Scope {token}",
            "ruc": f"SEARCH-SCOPE-{token}",
            "direccion": f"Managua Global {token}",
            "facturable": True,
        },
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    result = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="cliente",
            search_text=f"Global {token}",
        )
    )

    assert result.total_count >= 1
    assert any(row["id"] == created["id"] for row in result.rows)


def test_catalog_query_service_enriches_circuito_rows_with_operational_labels(session_factory, modelo_workflow):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={"descarga": {"fecha_descarga": "2026-01-16T08:00"}},
        )
    )
    circuito_id = int(created["_circuito_id"])

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    result = query_service.query_page(
        CatalogQueryRequest(
            catalog_name="circuito",
            filters=(CatalogFilter(field="id", operator=CatalogFilterOperator.EQ, value=circuito_id),),
        )
    )

    assert result.total_count == 1
    row = result.rows[0]
    assert row["conductor_label"] == "Juan Perez"
    assert row["ruta_ida_label"] == "Origen Demo -> Destino Demo"
    assert row["ruta_vuelta_label"] == ""


def test_catalog_query_service_searches_circuito_by_driver_and_routes(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        viaje_conductor = session.get(Conductor, deps["conductor_id"])
        viaje_conductor.nombre = f"Conductor {token}"
        viaje_conductor.apellido = "Unico"
        origen = session.get(Ubicacion, deps["origen_id"])
        destino = session.get(Ubicacion, deps["destino_id"])
        origen.descripcion = f"Origen {token}"
        destino.descripcion = f"Destino {token}"
        return_route = create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        return_route_id = int(return_route.id)
        session.commit()
    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={"descarga": {"fecha_descarga": "2026-01-16T08:00"}},
        )
    )
    circuito_id = int(created["_circuito_id"])

    modelo_workflow.viaje.create(
        {
            "viaje": {
                "cliente_id": deps["cliente_id"],
                "conductor_id": deps["conductor_id"],
                "furgon_id": deps["furgon_id"],
                "camion_id": deps["camion_id"],
                "thermo_id": deps["thermo_id"],
                "tipo_viaje": "Importacion",
                "_ruta_id": return_route_id,
                "_circuito_id": circuito_id,
                "fecha_posicionamiento": datetime(2026, 1, 16, 10, 0),
            },
            "circuito": {},
            "detalle_operacion": {},
        }
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    by_driver = query_service.query_page(CatalogQueryRequest(catalog_name="circuito", search_text=token))
    by_outbound = query_service.query_page(CatalogQueryRequest(catalog_name="circuito", search_text=f"Origen {token}"))
    by_return = query_service.query_page(
        CatalogQueryRequest(catalog_name="circuito", search_text=f"Destino {token} -> Origen {token}")
    )

    assert any(row["id"] == circuito_id for row in by_driver.rows)
    assert any(row["id"] == circuito_id for row in by_outbound.rows)
    assert any(row["id"] == circuito_id for row in by_return.rows)
