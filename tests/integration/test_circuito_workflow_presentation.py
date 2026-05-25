from __future__ import annotations

from datetime import datetime
from typing import cast

import pytest

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.infrastructure.persistence.session_identity import clear_authenticated_user_id
from openlogistic_erp.presentation import (
    PresentationAuthorizationService,
    RuntimeSessionViewModel,
    ViajeFormViewModel,
    ViajeWorkflowViewModel,
    build_default_app_shell,
)
from openlogistic_erp.presentation.catalog import CatalogScreenViewModel
from openlogistic_erp.presentation.workflows.circuito import CircuitoWorkflowViewModel
from tests.builders.modelo_seed import build_viaje_export_payload, create_ruta, seed_viaje_dependencies
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load


def _build_shell(session_factory, modelo_workflow, reference_lookup_service=None):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    return build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )


def test_circuito_return_trip_action_is_available_after_superuser_login(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    auth_service,
    rbac_service,
):
    clear_authenticated_user_id()
    username = f"super_return_{datetime.now().timestamp()}".replace(".", "_")
    password = "abc12345"
    auth_service.create_user(username=username, password=password, is_superuser=True)
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    authorization = PresentationAuthorizationService(rbac_service)
    runtime = RuntimeSessionViewModel(auth_service, authorization_service=authorization)
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
        auth_service=auth_service,
        rbac_service=rbac_service,
        runtime_session=runtime,
        authorization_service=authorization,
    )
    runtime.authenticatedChanged.connect(shell.handle_runtime_auth_changed)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    try:
        runtime.login(username, password)
        workflow.open_detalle(circuito_id)

        detail = workflow.detail_view_model
        assert runtime.is_superuser is True
        assert workflow.can_create_return_trip is True
        assert detail is not None
        assert detail.summary["can_add_return_trip"] is True
        assert detail.can_add_return_trip is True
    finally:
        runtime.logout()
        shell.dispose()
        clear_authenticated_user_id()


def test_circuito_return_trip_permission_refreshes_when_switching_to_superuser(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    auth_service,
    rbac_service,
):
    clear_authenticated_user_id()
    user_password = "abc12345"
    regular_username = f"regular_return_{datetime.now().timestamp()}".replace(".", "_")
    super_username = f"super_return_switch_{datetime.now().timestamp()}".replace(".", "_")
    auth_service.create_user(username=regular_username, password=user_password)
    auth_service.create_user(username=super_username, password=user_password, is_superuser=True)
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    authorization = PresentationAuthorizationService(rbac_service)
    runtime = RuntimeSessionViewModel(auth_service, authorization_service=authorization)
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
        auth_service=auth_service,
        rbac_service=rbac_service,
        runtime_session=runtime,
        authorization_service=authorization,
    )
    runtime.authenticatedChanged.connect(shell.handle_runtime_auth_changed)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    try:
        runtime.login(regular_username, user_password)
        runtime.login(super_username, user_password)
        workflow.open_detalle(circuito_id)

        detail = workflow.detail_view_model
        assert runtime.is_superuser is True
        assert workflow.can_create_return_trip is True
        assert detail is not None
        assert detail.can_add_return_trip is True
    finally:
        runtime.logout()
        shell.dispose()
        clear_authenticated_user_id()


def test_app_shell_uses_specialized_circuito_workflow_when_workflow_service_is_available(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    run_action_and_wait_for_applied_load(workflow.list_screen, lambda: shell.select_module("circuito"))

    assert shell.current_workflow_component == "CircuitoWorkflowPage.qml"
    assert isinstance(shell.current_workflow_module, CircuitoWorkflowViewModel)
    assert isinstance(workflow.list_screen, CatalogScreenViewModel)
    assert workflow.list_screen.view_definition.catalog_name == "circuito"
    assert workflow.list_screen.can_create is False
    assert workflow.list_screen.can_delete is False
    assert workflow.list_screen.can_edit is True
    assert workflow.list_screen.form_host.presentation_mode == "page"
    assert workflow.list_screen.form_host.navigation_title == "Circuitos"


def test_circuito_workflow_list_exposes_derived_operational_columns(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    run_action_and_wait_for_applied_load(workflow.list_screen, lambda: shell.select_module("circuito"))

    keys = [column["key"] for column in workflow.list_screen.table_model.columns() if column["kind"] == "data"]

    assert keys == [
        "fecha_inicio",
        "fecha_fin",
        "estado",
        "conductor_label",
        "ruta_ida_label",
        "ruta_vuelta_label",
    ]


def test_circuito_form_only_exposes_basic_editable_fields(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])
    run_action_and_wait_for_applied_load(workflow.list_screen, lambda: shell.select_module("circuito"))

    assert workflow.open_create() is False

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    workflow.open_detalle(created["_circuito_id"])
    detail = workflow.detail_view_model
    form = detail.circuito_form if detail is not None else None

    assert form is not None
    assert [field["name"] for field in form.fields] == ["fecha_inicio", "fecha_fin", "estado"]
    assert all(field["editable"] is True for field in form.fields)


def test_circuito_edit_action_opens_detail_with_header_form(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])
    run_action_and_wait_for_applied_load(workflow.list_screen, lambda: shell.select_module("circuito"))

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])

    assert workflow.open_record_form(circuito_id) is True

    detail = workflow.detail_view_model
    assert workflow.active_page == "detail"
    assert detail is not None
    assert detail.circuito_form.record_id == circuito_id
    assert [field["name"] for field in detail.circuito_form.fields] == ["fecha_inicio", "fecha_fin", "estado"]
    assert detail.can_edit_circuito is True


def test_circuito_detail_header_is_read_only_when_finalized(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])
    run_action_and_wait_for_applied_load(workflow.list_screen, lambda: shell.select_module("circuito"))

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    modelo_workflow.circuito.update(circuito_id, {"estado": "Finalizado"})

    workflow.open_detalle(circuito_id)

    detail = workflow.detail_view_model
    assert detail is not None
    assert detail.circuito_summary["estado"] == "Finalizado"
    assert detail.is_closed is True
    assert detail.can_edit_circuito is False
    assert detail.can_add_return_trip is False
    assert detail.gasto_real_camion_form.is_read_only is True
    assert detail.movimientos_adicionales_form.is_read_only is True
    assert detail.save_section("gasto_real_camion") is False
    assert detail.error_message == "No se puede modificar un circuito finalizado"


def test_circuito_detail_cannot_open_return_trip_when_finalized(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    modelo_workflow.circuito.update(circuito_id, {"estado": "Finalizado"})
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)

    assert workflow.open_return_trip_form("Importacion") is False
    assert workflow.error_message == "No se puede modificar un circuito finalizado"


def test_circuito_detail_loads_basic_summary_trips_and_sections(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {"fecha_descarga": datetime(2026, 1, 16, 10, 0, 0)},
                "gasto_real_thermo": {"combustible_base_thermo": 40},
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-CIR-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )
    circuito_id = int(created["_circuito_id"])
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)
    detail = workflow.detail_view_model

    assert workflow.active_page == "detail"
    assert workflow.detail_summary["circuito"]["id"] == circuito_id
    assert workflow.detail_summary["consumo_camion_analysis"]["type"] in {"BASE", "TRIANGULADO", "POR_PESO"}
    assert detail is not None
    assert detail.summary["consumo_camion_analysis"]["status"] in {"ok", "missing_data", "warning", "error"}
    assert detail.circuito_summary["id"] == circuito_id
    assert detail.viaje_ida["id"] == int(created["id"])
    assert detail.viaje_vuelta == {}
    assert detail.can_add_return_trip is True
    assert detail.visible_sections == ["gasto_real_camion", "movimientos_adicionales"]
    assert detail.gasto_real_camion_form.values["combustible_base_camion"] == "60"
    assert detail.movimientos_adicionales_form.table_model.rowCount() == 0


def test_circuito_movimientos_adicionales_saves_and_reloads_route_labels(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)
    detail = workflow.detail_view_model
    assert detail is not None
    form = detail.movimientos_adicionales_form

    form.add_row()
    form.search_lookup_options("ruta_id", "Origen")
    route_options = form.lookup_options("ruta_id")
    selected_route = next(option for option in route_options if int(option["value"]) == int(deps["ruta_id"]))

    form.set_lookup_field_value(0, "ruta_id", selected_route["value"], selected_route["label"])
    form.set_row_field(0, "fecha_movimiento", "16/01/2026 12:45")
    form.set_row_field(0, "descripcion", "Movimiento adicional de prueba")
    form.set_row_field(0, "es_triangulado", True)

    assert form.save_section() is True

    reloaded_rows = detail.movimientos_adicionales_form.rows
    assert len(reloaded_rows) == 1
    assert int(reloaded_rows[0]["ruta_id"]) == int(deps["ruta_id"])
    assert reloaded_rows[0]["ruta_label"] == selected_route["label"]
    assert reloaded_rows[0]["fecha_movimiento"] == "16/01/2026 12:45"
    assert reloaded_rows[0]["descripcion"] == "Movimiento adicional de prueba"
    assert reloaded_rows[0]["es_triangulado"] is True


def test_circuito_detail_add_return_trip_opens_viaje_form_with_locked_circuito(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)

    assert workflow.open_return_trip_form("Importacion") is True
    form = workflow.active_form

    assert isinstance(form, ViajeFormViewModel)
    assert workflow.active_page == "form"
    assert form.fixed_trip_type == "Importacion"
    assert form.trip_type_locked is True
    assert form.values["_circuito_id"] == circuito_id
    assert form.values["viaje_ida_id"] == int(created["id"])
    assert form.values["conductor_id"] == int(deps["conductor_id"])
    assert form.is_field_locked("conductor_id") is True
    assert form.is_field_locked("viaje_ida_id") is True
    assert form.is_field_locked("_circuito_id") is True
    assert form.is_field_locked("camion_id") is False
    assert form.is_field_locked("furgon_id") is False
    assert form.is_field_locked("thermo_id") is False

    workflow.close_form()

    assert workflow.open_return_trip_form("Vacio") is True
    vacio_form = workflow.active_form

    assert isinstance(vacio_form, ViajeFormViewModel)
    assert vacio_form.fixed_trip_type == "Vacio"
    assert vacio_form.trip_type_locked is True
    assert vacio_form.title == "Nuevo viaje vacío"
    assert vacio_form.show_trip_type_selector is False
    assert vacio_form.show_fuel_orders is False
    assert vacio_form.values["_circuito_id"] == circuito_id
    assert vacio_form.values["viaje_ida_id"] == int(created["id"])
    assert vacio_form.values["conductor_id"] == int(deps["conductor_id"])
    assert vacio_form.is_field_locked("conductor_id") is True
    assert vacio_form.is_field_locked("viaje_ida_id") is True
    assert vacio_form.is_field_locked("_circuito_id") is True


@pytest.mark.parametrize("trip_type", ["Importacion", "Vacio"])
def test_circuito_return_trip_flow_saves_and_reopens_same_detail_without_add_action(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    trip_type,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        if trip_type == "Vacio":
            create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
            session.commit()
    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": "2026-01-16T10:00",
                }
            },
        )
    )
    circuito_id = int(created["_circuito_id"])
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)

    assert workflow.detail_view_model is not None
    assert workflow.detail_view_model.can_add_return_trip is True
    assert workflow.open_return_trip_form(trip_type) is True
    form = workflow.active_form

    assert isinstance(form, ViajeFormViewModel)
    assert workflow.active_page == "form"
    assert form.fixed_trip_type == trip_type
    assert form.trip_type_locked is True
    assert form.values["_circuito_id"] == circuito_id

    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 12:00")
    form.set_field_value("descripcion", f"Viaje de vuelta {trip_type}")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", f"RET-{trip_type[:3].upper()}")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "THERMO")

    assert workflow.save_form() is True

    detail = workflow.detail_view_model
    assert workflow.active_page == "detail"
    assert workflow.active_form is None
    assert workflow.detail_summary["circuito"]["id"] == circuito_id
    assert detail is not None
    assert detail.circuito_summary["id"] == circuito_id
    assert detail.viaje_ida["id"] == int(created["id"])
    assert isinstance(detail.viaje_vuelta["id"], int)
    assert detail.viaje_vuelta["tipo_viaje"] == trip_type
    assert detail.can_add_return_trip is False


def test_circuito_empty_return_trip_does_not_require_fuel_orders(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()
    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": "2026-01-16T10:00",
                }
            },
        )
    )
    circuito_id = int(created["_circuito_id"])
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    workflow = cast(CircuitoWorkflowViewModel, shell._workflow_modules["circuito"])

    workflow.open_detalle(circuito_id)

    assert workflow.open_return_trip_form("Vacio") is True
    form = workflow.active_form

    assert isinstance(form, ViajeFormViewModel)
    assert form.show_fuel_orders is False

    form.set_field_value("fecha_posicionamiento", "16/01/2026 12:00")
    form.set_field_value("descripcion", "Viaje vacío sin órdenes")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")

    assert "ordenes_combustible" not in form._field_errors
    assert form.is_valid is True
    assert workflow.save_form() is True

    detail = workflow.detail_view_model
    assert detail is not None
    assert detail.viaje_vuelta["tipo_viaje"] == "Vacio"


def test_app_shell_can_open_viaje_detail_route_from_circuito_context(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    shell = _build_shell(session_factory, modelo_workflow, reference_lookup_service)
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    assert shell.navigate_to({"module_id": "viaje", "target": "detail", "record_id": int(created["id"])}) is True

    assert shell.current_module_id == "viaje"
    viaje_workflow = cast(ViajeWorkflowViewModel, shell._workflow_modules["viaje"])
    assert viaje_workflow.active_page == "detail"
    assert viaje_workflow.detail_summary["detalle_operacion"]["viaje_id"] == int(created["id"])
