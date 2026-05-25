from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.application.modelo.services import ModeloCatalogService, ModeloWorkflowService
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import Moneda
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import EstadoFacturacion, EstadoViaje, Viaje
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.tarifa_flete import TarifaFlete
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.presentation import ViajeFormViewModel, ViajeWorkflowViewModel, build_default_app_shell
from openlogistic_erp.presentation.catalog import (
    CatalogColumnDefinition,
    CatalogScreenViewModel,
    CatalogViewDefinition,
    FormDefinition,
    FormHostViewModel,
    FormRegistry,
    InMemoryCatalogTablePreferencesStore,
)
from openlogistic_erp.presentation.catalog.async_load import CatalogLoadRequest, CatalogLoadResult
from openlogistic_erp.presentation.catalog.types import FormMode
from openlogistic_erp.presentation.workflows.viaje import DetalleOperacionViewModel, WorkflowDescriptor
from tests.builders.modelo_seed import (
    build_viaje_export_payload,
    create_cliente,
    create_conductor,
    create_ruta,
    create_ubicacion,
    seed_viaje_dependencies,
)
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load, run_action_and_wait_for_request


class _ControlledLoadRunner:
    def __init__(self) -> None:
        self.requests: dict[int, CatalogLoadRequest] = {}
        self._success_callbacks: dict[int, object] = {}
        self._failure_callbacks: dict[int, object] = {}

    def submit(self, request, on_success, on_failure) -> None:
        self.requests[request.request_id] = request
        self._success_callbacks[request.request_id] = on_success
        self._failure_callbacks[request.request_id] = on_failure

    def succeed(self, request_id: int, rows: list[dict[str, object]], *, total_count: int | None = None) -> None:
        request = self.requests[request_id]
        result = CatalogLoadResult(
            request_id=request_id,
            rows=tuple(dict(row) for row in rows),
            display_rows=tuple(
                tuple("" if row.get(column_key) in (None, "") else str(row.get(column_key)) for column_key in request.column_keys)
                for row in rows
            ),
            column_keys=request.column_keys,
            total_count=int(total_count if total_count is not None else len(rows)),
            page=request.query.page,
            page_size=request.query.page_size,
        )
        callback = self._success_callbacks.pop(request_id)
        self._failure_callbacks.pop(request_id, None)
        callback(result)


def _dispatch_and_succeed(
    runner: _ControlledLoadRunner,
    action,
    rows: list[dict[str, object]],
    *,
    total_count: int | None = None,
) -> int:
    request_id = action()
    assert request_id is not None
    runner.succeed(int(request_id), rows, total_count=total_count)
    return int(request_id)


def _build_direct_viaje_workflow_view_model(
    store: InMemoryCatalogTablePreferencesStore,
    *,
    workflow_service: ModeloWorkflowService | None = None,
    reference_lookup_service=None,
    load_runner=None,
) -> ViajeWorkflowViewModel:
    registry = FormRegistry()
    if workflow_service is not None:
        registry.register(
            FormDefinition(
                form_id="viaje-workflow",
                qml_component="ViajeWorkflowForm.qml",
                presentation_mode="page",
                navigation_title="Viajes",
                catalog_names=("viaje",),
                supported_modes=(FormMode.CREATE, FormMode.EDIT),
                view_model_factory=lambda catalog_name, mode, context: ViajeFormViewModel(
                    workflow_service=workflow_service,
                    reference_lookup_service=reference_lookup_service,
                ),
                priority=100,
            )
        )
    list_screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="viaje",
            columns=(
                CatalogColumnDefinition("referencia", width=180, min_width=140),
                CatalogColumnDefinition("estado", width=140, min_width=120),
            ),
            permissions={"create": True, "edit": True, "delete": True},
            form_id="viaje-workflow",
            page_size=12,
            search_fields=("referencia",),
        ),
        query_service=cast(ModeloCatalogQueryService, object()),
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(
            registry,
            presentation_mode="page",
            navigation_title="Viajes",
        ),
        table_preferences_store=store,
        load_runner=load_runner,
    )
    return ViajeWorkflowViewModel(
        descriptor=WorkflowDescriptor(
            module_id="viaje",
            title="Viajes",
            domain_title="Operacion",
            summary="Resumen",
            qml_component="ViajeWorkflowPage.qml",
        ),
        list_screen=list_screen,
        workflow_service=workflow_service or cast(ModeloWorkflowService, object()),
    )

@pytest.mark.skip(reason="Ejecucion de test inestable, provoca access violation sin motivo claro o de manera consistente.")
def test_app_shell_uses_specialized_viaje_workflow_when_workflow_service_is_available(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )

    shell.select_module("viaje")
    workflow = shell.current_workflow_module

    assert shell.current_workflow_component == "ViajeWorkflowPage.qml"
    assert isinstance(workflow, ViajeWorkflowViewModel)
    assert isinstance(workflow.list_screen, CatalogScreenViewModel)
    assert workflow.list_screen.view_definition.form_id == "viaje-workflow"
    assert workflow.list_screen.columns[-1]["kind"] == "actions"
    assert workflow.list_screen.can_delete is True
    assert workflow.list_screen.form_host.presentation_mode == "page"
    assert workflow.list_screen.form_host.navigation_title == "Viajes"


def test_viaje_form_exposes_header_layout_items_for_simple_fields(modelo_workflow):
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    layout_items = cast(list[dict[str, object]], form.header_layout_items)

    assert layout_items[0]["type"] == "section"
    assert layout_items[0]["title"] == "Cabecera"
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[1]["fields"])] == [
        "cliente_id",
        "referencia",
    ]
    assert [field["name"] for field in cast(list[dict[str, object]], layout_items[2]["fields"])] == ["descripcion"]
    assert cast(list[dict[str, object]], layout_items[2]["fields"])[0]["full_width"] is True
    route_fields = {
        field["name"]
        for item in layout_items
        if item["type"] == "row"
        for field in cast(list[dict[str, object]], item["fields"])
    }
    assert {"origen_id", "destino_id"}.issubset(route_fields)
    assert any(
        any(field["name"] == "viaje_ida_id" for field in cast(list[dict[str, object]], item["fields"]))
        for item in layout_items
        if item["type"] == "row"
    )


def test_viaje_form_exposes_fuel_order_field_layout_metadata(modelo_workflow):
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    fields = cast(list[dict[str, object]], form.fuel_order_fields)

    assert [field["name"] for field in fields] == [
        "gasolinera",
        "numero_orden",
        "galones_autorizados",
        "tipo",
    ]
    assert fields[1]["span"] == 2
    assert fields[1]["full_width"] is True


def test_viaje_form_shows_type_selector_and_fuel_orders_for_regular_trip_types(modelo_workflow):
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    assert form.show_trip_type_selector is True
    assert form.show_fuel_orders is True

    form.set_trip_type("Importacion")

    assert form.show_trip_type_selector is True
    assert form.show_fuel_orders is True


def test_viaje_workflow_can_create_exportacion_and_open_detail(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    viaje_screen = cast(ViajeWorkflowViewModel, shell._workflow_modules["viaje"]).list_screen
    run_action_and_wait_for_applied_load(viaje_screen, lambda: shell.select_module("viaje"))
    workflow = shell.current_workflow_module

    assert workflow is not None
    assert workflow.open_create() is True
    form = workflow.active_form

    assert form is not None
    assert workflow.active_page == "form"
    assert workflow.active_subpage_title == "Nuevo viaje"

    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("fecha_posicionamiento", "15/01/2026 08:00")
    form.set_field_value("descripcion", "Viaje workflow export")
    form.set_field_value("viaticos_monto", "125.00")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_field_value("temperatura", "38")
    form.set_field_value("combustible_base_thermo", "40")
    form.set_field_value("combustible_base_camion", "60")
    form.set_fuel_order_field(0, "gasolinera", "NEDICSA")
    form.set_fuel_order_field(0, "numero_orden", "ORD-001")
    form.set_fuel_order_field(0, "galones_autorizados", "75")
    form.set_fuel_order_field(0, "tipo", "CAMION")

    run_action_and_wait_for_applied_load(workflow.list_screen, workflow.save_form)
    assert workflow.active_form is None
    assert workflow.list_screen.form_host.is_open is False
    assert workflow.active_page == "list"
    assert isinstance(workflow.selected_record_id, int)
    assert workflow.selected_record_id > 0

    workflow.open_detalle(workflow.selected_record_id)

    assert workflow.active_page == "detail"
    assert workflow.detail_summary["viaje"]["id"] == workflow.selected_record_id
    assert workflow.detail_summary["detalle_operacion"]["viaje_id"] == workflow.selected_record_id

    shell.dispose()

    assert workflow.active_form is None
    assert workflow.detail_view_model is None
    assert workflow.detail_summary == {}


def test_viaje_workflow_detail_view_model_exposes_visible_sections_and_trip_summary(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                },
                "actividad_thermo": {
                    "fecha_hora_encendido": datetime(2026, 1, 15, 8, 30, 0),
                    "fecha_hora_apagado": datetime(2026, 1, 16, 9, 45, 0),
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                    "_consumo_thermo": 12.5,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-VM-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    viaje_screen = cast(ViajeWorkflowViewModel, shell._workflow_modules["viaje"]).list_screen
    run_action_and_wait_for_applied_load(viaje_screen, lambda: shell.select_module("viaje"))
    workflow = cast(ViajeWorkflowViewModel, shell.current_workflow_module)

    workflow.open_detalle(created["id"])
    detail = workflow.detail_view_model

    assert detail is not None
    assert workflow.detail_summary["detalle_operacion"]["viaje_id"] == created["id"]
    assert workflow.detail_summary["consumo_thermo_analysis"]["type"] == "THERMO"
    assert detail.summary["detalle_operacion"]["viaje_id"] == created["id"]
    assert detail.summary["consumo_thermo_analysis"]["status"] in {"ok", "missing_model", "missing_data", "warning", "error"}
    assert detail.visible_sections == ["descarga", "combustible_thermo", "ordenes_combustible"]
    assert detail.viaje_summary["id"] == created["id"]
    assert "dias_viajados" not in detail.viaje_summary
    assert "consumo_thermo" not in detail.viaje_summary
    assert detail.descarga_form.values["fecha_descarga"] == "16/01/2026 10:00"
    assert detail.descarga_form.values["_dias_viajados"] == "2"
    assert detail.combustible_thermo_form.values["fecha_hora_encendido"] == "15/01/2026 08:30"
    assert detail.combustible_thermo_form.values["combustible_base_thermo"] == "40"
    assert detail.combustible_thermo_form.values["_consumo_thermo"] == "12.50"
    assert detail.ordenes_combustible_form.rows[0]["numero_orden"] == "ORD-VM-001"
    assert detail.ordenes_combustible_form.table_model.rowCount() == 1
    assert len(detail.ordenes_combustible_form.row_fields) == 4
    assert detail.section_state("descarga")["dirty"] is False
    assert detail.section_state("combustible_thermo")["visible"] is True


def test_viaje_workflow_detail_view_model_only_exposes_descarga_for_vacio(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    vacio = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": "Vacio",
                "viaje_ida_id": exportacion["id"],
            },
            "detalle_operacion": {
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 18, 14, 30, 0),
                }
            },
        }
    )

    detail = DetalleOperacionViewModel(workflow_service=modelo_workflow)
    detail.load(vacio["id"])

    assert detail.visible_sections == ["descarga"]
    assert detail.section_state("ordenes_combustible")["visible"] is False


def test_viaje_workflow_detail_view_model_can_save_individual_sections_and_global_changes(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                    "_consumo_thermo": 18.5,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-SAVE-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )

    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
    )

    workflow.open_detalle(created["id"])
    detail = workflow.detail_view_model

    assert detail is not None
    assert workflow.error_message == ""
    assert detail.descarga_form.values["fecha_descarga"] != ""
    detail.descarga_form.set_field_value("peso", "44000")
    assert detail.descarga_form.is_dirty is True
    assert detail.save_section("descarga") is True, detail.error_message

    summary = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert summary["descarga"]["peso"] == "44000"

    detail.combustible_thermo_form.set_field_value("restante_thermo", "6.5")
    assert detail.save_section("combustible_thermo") is True, detail.error_message
    summary_after_thermo_save = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert summary_after_thermo_save["gasto_real_thermo"]["restante_thermo"] == "6.50"
    assert summary_after_thermo_save["gasto_real_thermo"]["_consumo_thermo"] == "18.50"
    assert "consumo_thermo" not in summary_after_thermo_save["viaje_summary"]

    detail.ordenes_combustible_form.table_model.set_cell_value(0, 1, "ORD-SAVE-002")
    assert detail.ordenes_combustible_form.rows[0]["numero_orden"] == "ORD-SAVE-002"
    detail.descarga_form.set_field_value("fecha_descarga", "")
    assert detail.save_all() is False

    summary_after_failed_save = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert summary_after_failed_save["ordenes_combustible"][0]["numero_orden"] == "ORD-SAVE-001"

    detail.descarga_form.set_field_value("fecha_descarga", "16/01/2026 10:00")
    assert detail.save_all() is True

    summary_after_global_save = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert summary_after_global_save["ordenes_combustible"][0]["numero_orden"] == "ORD-SAVE-002"


def test_viaje_workflow_detail_view_model_closes_after_valid_save_and_can_reopen(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                    "peso": "41000",
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-CLOSE-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )

    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
    )
    workflow.open_detalle(created["id"])
    detail = workflow.detail_view_model

    detail.ordenes_combustible_form.table_model.set_cell_value(0, 1, "ORD-CLOSE-002")
    assert detail.close_detail() is True, detail.error_message
    assert detail.is_closed is True
    closed_summary = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert closed_summary["detalle_operacion"]["estado"] == "Cerrado"
    assert closed_summary["viaje_summary"]["estado"] == "Finalizado"
    assert closed_summary["ordenes_combustible"][0]["numero_orden"] == "ORD-CLOSE-002"

    assert detail.reopen_detail() is True, detail.error_message
    assert detail.is_closed is False
    reopened_summary = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert reopened_summary["detalle_operacion"]["estado"] == "Abierto"
    assert reopened_summary["viaje_summary"]["estado"] == "En curso"


def test_viaje_workflow_detail_view_model_is_read_only_when_detail_is_closed(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                    "peso": "41000",
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-CLOSED-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )
    modelo_workflow.viaje.terminar_viaje(created["id"])

    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
    )

    workflow.open_detalle(created["id"])
    detail = workflow.detail_view_model

    assert detail.is_closed is True
    assert detail.can_save_all is False
    assert workflow.delete_active_viaje() is False
    assert modelo_workflow.viaje.get(created["id"]) is not None

    original_orders = detail.ordenes_combustible_form.rows
    detail.descarga_form.set_field_value("peso", "44000")
    detail.ordenes_combustible_form.set_row_field(0, "numero_orden", "ORD-CLOSED-002")
    detail.ordenes_combustible_form.add_row()
    detail.ordenes_combustible_form.remove_row(0)

    assert detail.descarga_form.values["peso"] == "41000"
    assert detail.descarga_form.is_dirty is False
    assert detail.ordenes_combustible_form.rows == original_orders
    assert detail.ordenes_combustible_form.is_dirty is False
    assert detail.save_section("descarga") is False
    assert detail.save_all() is False

    summary = modelo_workflow.viaje.get_detail_summary(created["id"])
    assert summary["descarga"]["peso"] == "41000"
    assert summary["ordenes_combustible"][0]["numero_orden"] == "ORD-CLOSED-001"


def test_viaje_form_validates_importacion_against_selected_circuito(
    session_factory,
    modelo_workflow,
):
    token = uuid4().hex[:8]
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        other_conductor = create_conductor(
            session,
            nombre="Carlos",
            apellido=f"Prueba-{token}",
            cedula="001-000000-0001A",
            licencia="LIC-99",
        )
        session.commit()
        other_conductor_id = other_conductor.id

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": "2026-01-16T10:00",
                }
            },
        )
    )

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", other_conductor_id)
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("viaje_ida_id", exportacion["id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 09:00")
    form.set_field_value("descripcion", "Import workflow invalid")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", "IMP-001")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "THERMO")

    assert form.submit_form() is False
    assert form.field_error("conductor_id") == ""
    assert form.field_error("fecha_posicionamiento") != ""


def test_viaje_form_can_create_importacion_when_circuito_constraints_match(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": "2026-01-16T10:00",
                }
            },
        )
    )

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("viaje_ida_id", exportacion["id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 12:00")
    form.set_field_value("descripcion", "Import workflow valid")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", "IMP-002")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "THERMO")

    assert form.submit_form() is True
    assert isinstance(form.record_id, int)
    saved = modelo_workflow.viaje.get(form.record_id)
    assert saved is not None
    assert str(saved["tipo_viaje"]) == "Importacion"
    assert int(saved["_circuito_id"]) == int(exportacion["_circuito_id"])


def test_viaje_form_can_create_importacion_with_different_conductor_when_camion_matches(
    session_factory,
    modelo_workflow,
):
    token = uuid4().hex[:8]
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        other_conductor = create_conductor(
            session,
            nombre="Luis",
            apellido=f"Retorno-{token}",
            cedula=f"001-{token[:6]}-0002A",
            licencia=f"LIC-{token[:6]}",
        )
        session.commit()
        other_conductor_id = int(other_conductor.id)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": "2026-01-16T10:00",
                }
            },
        )
    )

    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", other_conductor_id)
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("viaje_ida_id", exportacion["id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 12:00")
    form.set_field_value("descripcion", "Import workflow fallback camion")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", "IMP-CAMION")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "THERMO")

    assert form.submit_form() is True, form.error_message
    assert isinstance(form.record_id, int)


def test_viaje_form_rejects_importacion_when_selected_ida_already_has_return_trip(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={"descarga": {"fecha_descarga": "2026-01-16T10:00"}},
        )
    )
    modelo_workflow.viaje.create(
        {
            "viaje": {
                "cliente_id": deps["cliente_id"],
                "conductor_id": deps["conductor_id"],
                "furgon_id": deps["furgon_id"],
                "camion_id": deps["camion_id"],
                "thermo_id": deps["thermo_id"],
                "tipo_viaje": "Importacion",
                "_ruta_id": deps["ruta_id"],
                "viaje_ida_id": exportacion["id"],
                "fecha_posicionamiento": datetime(2026, 1, 16, 12, 0, 0),
                "descripcion": "Primera vuelta",
            },
            "detalle_operacion": {
                "ordenes_combustible": [
                    {
                        "gasolinera": "MOVIL",
                        "numero_orden": "IMP-PRIMERA",
                        "galones_autorizados": 50,
                        "tipo": "THERMO",
                    }
                ]
            },
        }
    )

    form = ViajeFormViewModel(workflow_service=modelo_workflow)
    form.load(None)
    form.set_trip_type("Importacion")
    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("viaje_ida_id", exportacion["id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 13:00")
    form.set_field_value("descripcion", "Segunda vuelta")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", "IMP-SEGUNDA")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "THERMO")

    assert form.submit_form() is False
    assert "vuelta" in form.error_message


def test_viaje_form_can_prepare_vacio_without_cliente(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    form = ViajeFormViewModel(workflow_service=modelo_workflow)
    form.load(None)
    form.set_trip_type("Vacio")
    form.set_field_value("viaje_ida_id", exportacion["id"])
    form.set_field_value("fecha_posicionamiento", "16/01/2026 12:00")
    form.set_field_value("viaticos_monto", "100")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_fuel_order_field(0, "gasolinera", "MOVIL")
    form.set_fuel_order_field(0, "numero_orden", "VAC-001")
    form.set_fuel_order_field(0, "galones_autorizados", "50")
    form.set_fuel_order_field(0, "tipo", "CAMION")

    assert form.values["cliente_id"] == ""
    assert form.values["origen_id"] == deps["destino_id"]
    assert form.values["destino_id"] == deps["origen_id"]
    assert form.is_valid is True


def test_viaje_form_locks_automatic_text_fields_for_vacio_return(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    form.prepare_return_trip(int(exportacion["_circuito_id"]), "Vacio")

    assert form.is_field_locked("referencia") is True
    assert form.is_field_locked("descripcion") is True


def test_viaje_form_locks_automatic_text_fields_when_switching_to_vacio(modelo_workflow):
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    form.load(None)
    form.set_trip_type("Vacio")

    assert form.is_field_locked("referencia") is True
    assert form.is_field_locked("descripcion") is True


def test_viaje_form_locks_automatic_text_fields_when_editing_vacio(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    vacio = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": "Vacio",
                "viaje_ida_id": exportacion["id"],
            }
        }
    )
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    form.load(vacio["id"])

    assert form.is_field_locked("referencia") is True
    assert form.is_field_locked("descripcion") is True


def test_viaje_form_keeps_text_fields_editable_for_exportacion(modelo_workflow):
    form = ViajeFormViewModel(workflow_service=modelo_workflow)

    form.load(None)

    assert form.is_field_locked("referencia") is False
    assert form.is_field_locked("descripcion") is False


def test_viaje_form_vacio_reports_missing_reverse_route(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    form = ViajeFormViewModel(workflow_service=modelo_workflow)
    form.load(None)
    form.set_trip_type("Vacio")
    form.set_field_value("viaje_ida_id", exportacion["id"])

    assert "ruta de retorno" in form.field_error("destino_id").lower()


def test_viaje_form_persists_optional_referencia_on_create_and_edit(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("referencia", "REF-MANUAL-001")
    form.set_field_value("cliente_id", deps["cliente_id"])
    form.set_field_value("origen_id", deps["origen_id"])
    form.set_field_value("destino_id", deps["destino_id"])
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("fecha_posicionamiento", "15/01/2026 08:00")
    form.set_field_value("descripcion", "Viaje con referencia manual")
    form.set_field_value("viaticos_monto", "125.00")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_field_value("temperatura", "38")
    form.set_field_value("combustible_base_thermo", "40")
    form.set_field_value("combustible_base_camion", "60")
    form.set_fuel_order_field(0, "gasolinera", "NEDICSA")
    form.set_fuel_order_field(0, "numero_orden", "ORD-REF-001")
    form.set_fuel_order_field(0, "galones_autorizados", "75")
    form.set_fuel_order_field(0, "tipo", "CAMION")

    assert form.submit_form() is True
    assert isinstance(form.record_id, int)

    saved = modelo_workflow.viaje.get(form.record_id)
    assert saved is not None
    assert saved["referencia"] == "REF-MANUAL-001"

    form.load(form.record_id)

    assert form.values["referencia"] == "REF-MANUAL-001"


def test_viaje_form_resuelve_ruta_desde_origen_y_destino(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        cliente = create_cliente(session, nombre="Cliente Ruta Derivada")
        origen = create_ubicacion(session, descripcion="Origen Ruta Derivada")
        destino = create_ubicacion(session, descripcion="Destino Ruta Derivada")
        ruta = create_ruta(session, origen=origen, destino=destino)
        session.add(
            TarifaFlete(
                cliente_id=cliente.id,
                ruta_id=ruta.id,
                costo=Decimal("145.00"),
                moneda=Moneda.USD,
            )
        )
        deps = seed_viaje_dependencies(session)
        session.commit()

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("origen_id", origen.id)
    form.set_field_value("destino_id", destino.id)
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("fecha_posicionamiento", "15/01/2026 08:00")
    form.set_field_value("descripcion", "Viaje con ruta derivada")
    form.set_field_value("viaticos_monto", "125.00")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_field_value("temperatura", "38")
    form.set_field_value("combustible_base_thermo", "40")
    form.set_field_value("combustible_base_camion", "60")
    form.set_fuel_order_field(0, "gasolinera", "NEDICSA")
    form.set_fuel_order_field(0, "numero_orden", "ORD-DERIVADA")
    form.set_fuel_order_field(0, "galones_autorizados", "75")
    form.set_fuel_order_field(0, "tipo", "CAMION")

    assert form.submit_form() is True
    assert isinstance(form.record_id, int)

    saved = modelo_workflow.viaje.get(form.record_id)
    assert saved is not None
    assert int(saved["_ruta_id"]) == int(ruta.id)
    assert int(saved["cliente_id"]) == int(cliente.id)


def test_viaje_form_marca_error_si_no_existe_ruta_para_origen_y_destino(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        cliente = create_cliente(session, nombre="Cliente Sin Ruta")
        origen = create_ubicacion(session, descripcion="Origen Sin Ruta")
        destino = create_ubicacion(session, descripcion="Destino Sin Ruta")
        deps = seed_viaje_dependencies(session)
        session.commit()

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("origen_id", origen.id)
    form.set_field_value("destino_id", destino.id)
    form.set_field_value("conductor_id", deps["conductor_id"])
    form.set_field_value("furgon_id", deps["furgon_id"])
    form.set_field_value("camion_id", deps["camion_id"])
    form.set_field_value("thermo_id", deps["thermo_id"])
    form.set_field_value("fecha_posicionamiento", "15/01/2026 08:00")
    form.set_field_value("descripcion", "Viaje sin ruta valida")
    form.set_field_value("viaticos_monto", "125.00")
    form.set_field_value("viaticos_moneda", "USD")
    form.set_field_value("temperatura", "38")
    form.set_field_value("combustible_base_thermo", "40")
    form.set_field_value("combustible_base_camion", "60")
    form.set_fuel_order_field(0, "gasolinera", "NEDICSA")
    form.set_fuel_order_field(0, "numero_orden", "ORD-SIN-RUTA")
    form.set_fuel_order_field(0, "galones_autorizados", "75")
    form.set_fuel_order_field(0, "tipo", "CAMION")

    assert form.submit_form() is False
    assert form.field_error("destino_id") != ""


def test_viaje_form_valida_ruta_en_reactivo_y_mantiene_payload_incompleto_fuera_del_submit(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        cliente = create_cliente(session, nombre="Cliente Error Reactivo")
        origen = create_ubicacion(session, descripcion="Origen Error Reactivo")
        destino = create_ubicacion(session, descripcion="Destino Error Reactivo")
        deps = seed_viaje_dependencies(session)
        session.commit()

    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("origen_id", origen.id)
    form.set_field_value("destino_id", destino.id)

    assert form.values["_ruta_id"] == ""
    assert form.field_error("destino_id") == (
        "No existe una ruta tarifada para el cliente seleccionado entre "
        "Origen Error Reactivo y Destino Error Reactivo."
    )
    assert form.is_valid is False


def test_viaje_form_edits_fuel_order_without_replacing_repeater_model(modelo_workflow):
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
    )
    form.load(None)
    fuel_order_model_resets = 0

    def count_fuel_order_model_reset():
        nonlocal fuel_order_model_resets
        fuel_order_model_resets += 1

    form.fuelOrdersChanged.connect(count_fuel_order_model_reset)

    form.set_fuel_order_field(0, "numero_orden", "ORD")

    assert form.fuel_orders[0]["numero_orden"] == "ORD"
    assert fuel_order_model_resets == 0


def test_viaje_workflow_uses_catalog_list_screen_for_table_state_and_editing(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    runner = _ControlledLoadRunner()
    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
        load_runner=runner,
    )

    created_id = int(created["id"])
    _dispatch_and_succeed(
        runner,
        workflow.refresh,
        [
            {"id": created_id, "referencia": str(created["referencia"]), "estado": str(created["estado"])},
            {"id": 9998, "referencia": "REF-ZETA", "estado": "En viaje"},
        ],
        total_count=2,
    )

    assert workflow.list_screen.table_model.rowCount() == 2

    workflow.list_screen.set_column_width("referencia", 280)

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.toggle_sort("referencia"),
        [
            {"id": 9998, "referencia": "REF-ZETA", "estado": "En viaje"},
            {"id": created_id, "referencia": str(created["referencia"]), "estado": str(created["estado"])},
        ],
        total_count=2,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.apply_search(str(created["referencia"])),
        [{"id": created_id, "referencia": str(created["referencia"]), "estado": str(created["estado"])}],
        total_count=1,
    )

    workflow.list_screen.select_row_index(0)

    assert workflow.selected_record_id == created_id
    assert workflow.list_screen.sort_field == "referencia"
    assert workflow.list_screen.sort_direction == "asc"
    assert workflow.list_screen.selected_row_index == 0
    assert workflow.list_screen.row_data_at(0)["id"] == created_id
    assert workflow.list_screen.column_width_at(0) == 280
    assert workflow.list_screen.columns[0]["width"] == 280
    assert workflow.open_record_form(created_id) is True
    assert workflow.active_form is not None
    assert workflow.list_screen.form_host.is_open is True
    assert workflow.active_page == "form"
    assert workflow.active_subpage_title.startswith("Editar viaje")


def test_viaje_workflow_opens_unbilled_trip_subpage_and_exposes_rows(
    modelo_workflow,
    session_factory,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
    )

    assert workflow.open_subpage("unbilled_trips", {}) is True
    assert workflow.active_page == "unbilled_trips"
    exposed_trip_ids = {
        trip["id"]
        for client_group in workflow.unbilled_trips
        for trip in client_group["viajes"]
    }
    assert created["id"] in exposed_trip_ids


def test_viaje_workflow_preserves_list_state_when_opening_and_closing_detail(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    runner = _ControlledLoadRunner()
    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
        load_runner=runner,
    )

    _dispatch_and_succeed(
        runner,
        workflow.refresh,
        [
            {"id": int(created["id"]), "referencia": str(created["referencia"]), "estado": str(created["estado"])},
            {"id": 9999, "referencia": "OTRO", "estado": "Planificado"},
        ],
        total_count=2,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.apply_search(str(created["referencia"])),
        [{"id": int(created["id"]), "referencia": str(created["referencia"]), "estado": str(created["estado"])}],
        total_count=1,
    )

    workflow.list_screen.select_row_index(0)
    selected_before = workflow.selected_record_id
    search_before = workflow.list_screen.search_term

    workflow.open_detalle(int(created["id"]))
    workflow.close_detalle()

    assert workflow.active_page == "list"
    assert workflow.selected_record_id == selected_before
    assert workflow.list_screen.search_term == search_before
    assert workflow.list_screen.selected_row_index == 0


def test_viaje_workflow_accepts_string_record_id_when_opening_detail(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    workflow.open_detalle(str(created["id"]))

    assert workflow.active_page == "detail"
    assert workflow.detail_summary["viaje"]["id"] == int(created["id"])
    assert workflow.selected_record_id == int(created["id"])


def test_viaje_workflow_can_delete_selected_trip_from_detail_and_return_to_list(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    viaje_workflow = cast(ViajeWorkflowViewModel, shell._workflow_modules["viaje"])
    run_action_and_wait_for_applied_load(viaje_workflow.list_screen, lambda: shell.select_module("viaje"))

    viaje_workflow.open_detalle(created["id"])

    assert viaje_workflow.active_page == "detail"
    assert viaje_workflow.detail_summary["viaje"]["id"] == int(created["id"])

    _, applied = run_action_and_wait_for_applied_load(
        viaje_workflow.list_screen,
        viaje_workflow.delete_selected_viaje,
    )

    assert applied is True
    assert viaje_workflow.active_page == "list"
    assert viaje_workflow.detail_summary == {}
    assert viaje_workflow.selected_record_id is None
    assert modelo_workflow.viaje.get(created["id"]) is None


def test_viaje_workflow_can_delete_active_detail_trip_even_without_list_selection(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    viaje_workflow = cast(ViajeWorkflowViewModel, shell._workflow_modules["viaje"])
    run_action_and_wait_for_applied_load(viaje_workflow.list_screen, lambda: shell.select_module("viaje"))

    viaje_workflow.open_detalle(created["id"])
    viaje_workflow.list_screen.select_record(None)

    assert viaje_workflow.active_page == "detail"
    assert viaje_workflow.selected_record_id is None
    assert viaje_workflow.detail_summary["viaje"]["id"] == int(created["id"])

    _, applied = run_action_and_wait_for_applied_load(
        viaje_workflow.list_screen,
        viaje_workflow.delete_active_viaje,
    )

    assert applied is True
    assert viaje_workflow.active_page == "list"
    assert viaje_workflow.detail_summary == {}
    assert modelo_workflow.viaje.get(created["id"]) is None


def test_viaje_list_handles_repeated_search_sort_and_pagination_without_custom_table_logic(
    modelo_workflow,
    reference_lookup_service,
):
    runner = _ControlledLoadRunner()
    workflow = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
        load_runner=runner,
    )

    _dispatch_and_succeed(
        runner,
        workflow.refresh,
        [
            {"id": 1, "referencia": "ALFA", "estado": "Planificado"},
            {"id": 2, "referencia": "BETA", "estado": "En viaje"},
        ],
        total_count=30,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.apply_search("a"),
        [{"id": 1, "referencia": "ALFA", "estado": "Planificado"}],
        total_count=1,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.apply_search("ab"),
        [],
        total_count=0,
    )

    _dispatch_and_succeed(
        runner,
        workflow.list_screen.clear_search,
        [
            {"id": 1, "referencia": "ALFA", "estado": "Planificado"},
            {"id": 2, "referencia": "BETA", "estado": "En viaje"},
        ],
        total_count=30,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.toggle_sort("referencia"),
        [
            {"id": 1, "referencia": "ALFA", "estado": "Planificado"},
            {"id": 2, "referencia": "BETA", "estado": "En viaje"},
        ],
        total_count=30,
    )

    _dispatch_and_succeed(
        runner,
        lambda: workflow.list_screen.toggle_sort("referencia"),
        [
            {"id": 2, "referencia": "BETA", "estado": "En viaje"},
            {"id": 1, "referencia": "ALFA", "estado": "Planificado"},
        ],
        total_count=30,
    )

    _dispatch_and_succeed(
        runner,
        workflow.list_screen.next_page,
        [
            {"id": 3, "referencia": "GAMMA", "estado": "Finalizado"},
            {"id": 4, "referencia": "DELTA", "estado": "Planificado"},
        ],
        total_count=30,
    )

    _dispatch_and_succeed(
        runner,
        workflow.list_screen.prev_page,
        [
            {"id": 2, "referencia": "BETA", "estado": "En viaje"},
            {"id": 1, "referencia": "ALFA", "estado": "Planificado"},
        ],
        total_count=30,
    )

    assert workflow.error_message in ("", workflow.list_screen.error_message)


def test_viaje_workflow_persists_column_widths_in_the_backing_catalog_screen():
    store = InMemoryCatalogTablePreferencesStore()
    view_model = _build_direct_viaje_workflow_view_model(store)

    view_model.list_screen.set_column_width("estado", 230)

    restored = _build_direct_viaje_workflow_view_model(store)

    assert restored.list_screen.columns[1]["width"] == 230


def test_viaje_workflow_column_width_updates_do_not_reset_the_backing_table_model():
    store = InMemoryCatalogTablePreferencesStore()
    view_model = _build_direct_viaje_workflow_view_model(store)
    refresh_calls: list[bool] = []

    def track_refresh() -> None:
        refresh_calls.append(True)

    view_model.list_screen._refresh_table_model = track_refresh  # type: ignore[method-assign]

    view_model.list_screen.set_column_width("estado", 230)

    assert refresh_calls == []
    assert view_model.list_screen.columns[1]["width"] == 230


def test_viaje_global_date_filter_preserves_existing_filters():
    load_runner = _ControlledLoadRunner()
    view_model = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        load_runner=load_runner,
    )
    screen = view_model.list_screen

    assert screen.apply_filter_payload({"field": "estado", "operator": "eq", "value": "REGISTRADO"})
    assert view_model.apply_date_filter("last_week", "")

    filters_by_field = {filter_spec.field: filter_spec for filter_spec in screen.filters}
    date_filter = filters_by_field["fecha_posicionamiento"]
    expected_start = datetime.combine(date.today() - timedelta(days=6), datetime.min.time())

    assert view_model.date_filter_mode == "last_week"
    assert filters_by_field["estado"].value == "REGISTRADO"
    assert date_filter.operator.value == "between"
    assert date_filter.value == expected_start.isoformat(timespec="seconds")


def test_viaje_global_date_filter_accepts_selected_month_and_can_return_to_history():
    load_runner = _ControlledLoadRunner()
    view_model = _build_direct_viaje_workflow_view_model(
        InMemoryCatalogTablePreferencesStore(),
        load_runner=load_runner,
    )

    assert view_model.apply_date_filter("selected_month", "2026-02")
    date_filter = view_model.list_screen.filters[0]

    assert view_model.date_filter_mode == "selected_month"
    assert view_model.selected_month == "2026-02"
    assert date_filter.field == "fecha_posicionamiento"
    assert date_filter.value == "2026-02-01T00:00:00"
    assert date_filter.value_to == "2026-02-28T23:59:59"

    assert view_model.apply_date_filter("all", "2026-02")

    assert view_model.date_filter_mode == "all"
    assert view_model.list_screen.filters == ()


def test_viaje_list_accepts_enum_multiselect_filter_without_unhashable_list_error(
    session_factory,
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    load_runner = _ControlledLoadRunner()
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("viaje")),
        query_service=query_service,
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
        load_runner=load_runner,
    )

    applied = screen.apply_filter_payload(
        {
            "field": "tipo_viaje",
            "operator": "in",
            "value": ["EXPOR", "IMPOR"],
        }
    )

    assert applied is True
    assert screen.error_message == ""
    assert len(screen.filters) == 1
    assert screen.active_filters[0]["displayValue"] == "EXPOR, IMPOR"


def test_viaje_list_search_with_active_enum_filter_does_not_raise_unhashable_list(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    query_service = ModeloCatalogQueryService(
        SqlAlchemyCatalogQueryRepository(session_factory),
        reference_lookup_service=reference_lookup_service,
    )
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("viaje")),
        query_service=query_service,
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
    )

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            viaje={"descripcion": f"Filtro y busqueda {uuid4().hex[:8]}"},
        )
    )

    assert screen.apply_filter_payload(
        {
            "field": "tipo_viaje",
            "operator": "in",
            "value": ["EXPOR"],
        }
    )

    _, applied = run_action_and_wait_for_request(screen, lambda: screen.apply_search("Filtro y busqueda"))

    assert applied is True
    assert screen.error_message == ""


def test_viaje_list_accepts_single_enum_selection_sent_as_list_for_eq_operator(
):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(lambda: None))
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition.from_schema(query_service.get_schema("viaje")),
        query_service=query_service,
        catalog_service=cast(ModeloCatalogService, object()),
        form_host=FormHostViewModel(FormRegistry()),
        load_runner=_ControlledLoadRunner(),
    )

    applied = screen.apply_filter_payload(
        {
            "field": "estado_facturacion",
            "operator": "eq",
            "value": ["REGISTRADO"],
        }
    )

    assert applied is True
    assert screen.error_message == ""
    assert len(screen.filters) == 1
    assert screen.filters[0].value == "REGISTRADO"
