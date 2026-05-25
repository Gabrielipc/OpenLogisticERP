from __future__ import annotations

from uuid import uuid4

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.domain.modelo.catalog_queries import CatalogSort, CatalogSortDirection
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.presentation.catalog import (
    CatalogColumnDefinition,
    CatalogScreenViewModel,
    CatalogViewDefinition,
    FormDefinition,
    FormHostViewModel,
    FormRegistry,
    GenericCatalogFormViewModel,
)
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load, run_action_and_wait_for_request


def _build_generic_registry(modelo_workflow) -> FormRegistry:
    return FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )


def test_catalog_screen_search_refreshes_rows_and_clear_restores_records(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            search_field="nombre",
            columns=(CatalogColumnDefinition("id"), CatalogColumnDefinition("nombre"), CatalogColumnDefinition("ruc")),
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    run_action_and_wait_for_request(screen, screen.load)
    initial_total = screen.total_count
    token = uuid4().hex[:8].upper()
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente Search {token}",
            "ruc": f"SEARCH-{token}",
            "direccion": f"Managua {token}",
            "facturable": True,
        },
    )

    run_action_and_wait_for_request(screen, screen.refresh)
    assert screen.total_count == initial_total + 1

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))

    assert screen.search_term == token
    assert screen.total_count == 1
    assert screen.table_model.rowCount() == 1
    assert screen.table_model.row_data(0)["id"] == created["id"]
    assert screen.table_model.display_data(0, 1) == f"Cliente Search {token}"

    run_action_and_wait_for_request(screen, screen.clear_search)

    assert screen.search_term == ""
    assert screen.total_count == initial_total + 1
    assert screen.table_model.rowCount() == min(screen.page_size, screen.total_count)


def test_catalog_screen_search_selection_and_edit_use_stable_record_ids(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    registry = FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=modelo_workflow.catalog,
                ),
                priority=0,
            ),
        )
    )
    view_definition = CatalogViewDefinition.from_schema(
        query_service.get_schema("cliente"),
        form_id="generic-catalog",
    )
    screen = CatalogScreenViewModel(
        view_definition=view_definition,
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(registry),
    )

    run_action_and_wait_for_request(screen, screen.load)
    token = uuid4().hex[:8].upper()
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente Filter {token}",
            "ruc": f"FILTER-{token}",
            "direccion": f"Leon {token}",
            "facturable": True,
        },
    )

    run_action_and_wait_for_request(screen, screen.refresh)
    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))

    record_id = screen.record_id_at_row(0)

    assert record_id == created["id"]

    screen.select_record_by_id(int(record_id))

    assert screen.selected_record_id == created["id"]
    assert screen.selected_row_data is not None
    assert screen.selected_row_data["id"] == created["id"]
    assert screen.open_record_form(int(record_id)) is True
    assert screen.form_host.active_form is not None


def test_catalog_screen_pagination_moves_between_backend_pages(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="cliente",
            search_field="nombre",
            page_size=5,
            columns=(CatalogColumnDefinition("id"), CatalogColumnDefinition("nombre"), CatalogColumnDefinition("ruc")),
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    token = uuid4().hex[:8].upper()
    created_ids: set[int] = set()
    for index in range(7):
        created = modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Page {token} {index}",
                "ruc": f"PAGE-{token}-{index}",
                "direccion": f"Masaya {token} {index}",
                "facturable": True,
            },
        )
        created_ids.add(int(created["id"]))

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))

    first_page_ids = {int(screen.record_id_at_row(row_index)) for row_index in range(screen.table_model.rowCount())}

    assert screen.total_count == 7
    assert screen.current_page == 0
    assert screen.table_model.rowCount() == 5
    assert screen.has_prev_page is False
    assert screen.has_next_page is True
    assert first_page_ids <= created_ids

    run_action_and_wait_for_request(screen, screen.next_page)

    second_page_ids = {int(screen.record_id_at_row(row_index)) for row_index in range(screen.table_model.rowCount())}

    assert screen.current_page == 1
    assert screen.table_model.rowCount() == 2
    assert screen.has_prev_page is True
    assert screen.has_next_page is False
    assert second_page_ids <= created_ids
    assert first_page_ids.isdisjoint(second_page_ids)

    run_action_and_wait_for_request(screen, screen.prev_page)

    assert screen.current_page == 0
    assert screen.table_model.rowCount() == 5
    assert {int(screen.record_id_at_row(row_index)) for row_index in range(screen.table_model.rowCount())} == first_page_ids


def test_catalog_screen_create_navigates_to_page_of_new_record(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(
            query_service.get_schema("cliente"),
            form_id="generic-catalog",
            page_size=5,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(_build_generic_registry(modelo_workflow)),
    )

    token = uuid4().hex[:8].upper()
    for index in range(7):
        modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Create Page {token} {index}",
                "ruc": f"CREATE-PAGE-{token}-{index}",
                "direccion": f"Masaya {token} {index}",
                "facturable": True,
            },
        )

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))

    assert screen.current_page == 0
    assert screen.table_model.rowCount() == 5
    assert screen.open_create_form() is True
    form = screen.form_host.active_form

    assert isinstance(form, GenericCatalogFormViewModel)

    form.set_field_value("nombre", f"Cliente Create Page {token} Nuevo")
    form.set_field_value("ruc", f"CREATE-PAGE-{token}-NEW")
    form.set_field_value("direccion", f"Masaya {token} Nuevo")
    form.set_field_value("facturable", True)

    run_action_and_wait_for_applied_load(screen, form.submit_form)

    assert form.record_id is not None
    assert screen.current_page == 0
    assert screen.selected_record_id == int(form.record_id)
    assert screen.selected_row_index == 0
    assert screen.record_id_at_row(screen.selected_row_index) == int(form.record_id)
    assert screen.open_record_form(screen.record_id_at_row(screen.selected_row_index)) is True


def test_catalog_screen_create_keeps_current_page_when_new_record_stays_visible(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(
            query_service.get_schema("cliente"),
            form_id="generic-catalog",
            page_size=10,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(_build_generic_registry(modelo_workflow)),
    )

    token = uuid4().hex[:8].upper()
    for index in range(3):
        modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Create Same Page {token} {index}",
                "ruc": f"CREATE-SAME-{token}-{index}",
                "direccion": f"Leon {token} {index}",
                "facturable": True,
            },
        )

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))
    assert screen.current_page == 0
    assert screen.open_create_form() is True
    form = screen.form_host.active_form

    assert isinstance(form, GenericCatalogFormViewModel)

    form.set_field_value("nombre", f"Cliente Create Same Page {token} Nuevo")
    form.set_field_value("ruc", f"CREATE-SAME-{token}-NEW")
    form.set_field_value("direccion", f"Leon {token} Nuevo")
    form.set_field_value("facturable", True)

    run_action_and_wait_for_applied_load(screen, form.submit_form)

    assert form.record_id is not None
    assert screen.current_page == 0
    assert screen.selected_record_id == int(form.record_id)
    assert screen.selected_row_index == 0
    assert screen.record_id_at_row(screen.selected_row_index) == int(form.record_id)


def test_catalog_screen_create_respects_active_filters_when_new_record_does_not_match(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(
            query_service.get_schema("cliente"),
            form_id="generic-catalog",
            page_size=5,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(_build_generic_registry(modelo_workflow)),
    )

    filter_token = uuid4().hex[:8].upper()
    for index in range(3):
        modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Filter Guard {filter_token} {index}",
                "ruc": f"FILTER-GUARD-{filter_token}-{index}",
                "direccion": f"Managua {filter_token} {index}",
                "facturable": True,
            },
        )

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(filter_token))
    visible_ids_before = [screen.record_id_at_row(row_index) for row_index in range(screen.table_model.rowCount())]

    assert screen.open_create_form() is True
    form = screen.form_host.active_form

    assert isinstance(form, GenericCatalogFormViewModel)

    other_token = uuid4().hex[:8].upper()
    form.set_field_value("nombre", f"Cliente Hidden {other_token}")
    form.set_field_value("ruc", f"HIDDEN-{other_token}")
    form.set_field_value("direccion", f"Granada {other_token}")
    form.set_field_value("facturable", True)

    run_action_and_wait_for_applied_load(screen, form.submit_form)

    assert screen.search_term == filter_token
    assert screen.current_page == 0
    assert screen.total_count == 3
    assert [screen.record_id_at_row(row_index) for row_index in range(screen.table_model.rowCount())] == visible_ids_before
    assert screen.selected_record_id is None


def test_catalog_screen_create_uses_primary_key_tiebreaker_for_non_unique_sort(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(
            query_service.get_schema("cliente"),
            form_id="generic-catalog",
            page_size=5,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(_build_generic_registry(modelo_workflow)),
    )

    token = uuid4().hex[:8].upper()
    for index in range(7):
        modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Sort Tie {token} {index}",
                "ruc": f"SORT-TIE-{token}-{index}",
                "direccion": f"Masatepe {token} {index}",
                "facturable": True,
            },
        )

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))
    run_action_and_wait_for_request(
        screen,
        lambda: screen.set_sort(CatalogSort(field="facturable", direction=CatalogSortDirection.ASC)),
    )

    assert screen.current_page == 0
    assert screen.open_create_form() is True
    form = screen.form_host.active_form

    assert isinstance(form, GenericCatalogFormViewModel)

    form.set_field_value("nombre", f"Cliente Sort Tie {token} Nuevo")
    form.set_field_value("ruc", f"SORT-TIE-{token}-NEW")
    form.set_field_value("direccion", f"Masatepe {token} Nuevo")
    form.set_field_value("facturable", True)

    run_action_and_wait_for_applied_load(screen, form.submit_form)

    assert form.record_id is not None
    assert screen.current_page == 1
    assert screen.selected_record_id == int(form.record_id)
    assert screen.selected_row_index == 2
    assert screen.record_id_at_row(screen.selected_row_index) == int(form.record_id)


def test_catalog_screen_can_restore_recent_sort_after_visible_header_sort_with_search_and_pagination(
    session_factory,
    modelo_workflow,
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(
            query_service.get_schema("cliente"),
            page_size=2,
        ),
        query_service=query_service,
        catalog_service=modelo_workflow.catalog,
        form_host=FormHostViewModel(FormRegistry()),
    )

    token = uuid4().hex[:8].upper()
    created_ids: list[int] = []
    for index in range(3):
        created = modelo_workflow.catalog.create(
            "cliente",
            {
                "nombre": f"Cliente Restore Sort {token} {index}",
                "ruc": f"RESTORE-SORT-{token}-{index}",
                "direccion": f"Managua {token} {index}",
                "facturable": True,
            },
        )
        created_ids.append(int(created["id"]))

    run_action_and_wait_for_request(screen, lambda: screen.apply_search(token))
    run_action_and_wait_for_request(screen, screen.next_page)

    assert screen.current_page == 1
    assert screen.search_term == token

    run_action_and_wait_for_request(screen, lambda: screen.toggle_sort("nombre"))

    assert screen.current_page == 0
    assert screen.search_term == token
    assert screen.sort_field == "nombre"
    assert screen.sort_direction == "asc"
    assert screen.sort_label == "Nombre ↑"

    run_action_and_wait_for_applied_load(
        screen,
        lambda: screen.apply_sort_payload({"field": "id", "direction": "desc"}),
    )

    assert screen.current_page == 0
    assert screen.search_term == token
    assert screen.sort_field == "id"
    assert screen.sort_direction == "desc"
    assert screen.sort_label == "Más recientes"
    assert screen.record_id_at_row(0) == max(created_ids)
