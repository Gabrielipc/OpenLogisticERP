from __future__ import annotations

from typing import cast
from uuid import uuid4

from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.presentation import build_default_app_shell
from openlogistic_erp.presentation.catalog import CatalogColumnOverride
from openlogistic_erp.presentation.catalog import build_default_catalog_workbench
from openlogistic_erp.presentation.catalog import column_overrides
from openlogistic_erp.presentation.catalog import GenericCatalogFormViewModel
from openlogistic_erp.presentation.workflows.factura import FacturaFormViewModel
from openlogistic_erp.presentation.workflows.recibo import ReciboFormViewModel
from tests.builders.modelo_seed import build_factura_payload, create_cliente
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load, run_action_and_wait_for_request


def test_app_shell_defers_initial_load_until_initialize(session_factory, modelo_workflow, monkeypatch):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    load_calls: list[str] = []
    current_screen = shell.current_catalog_screen

    assert current_screen is not None

    def fake_load_screen(self):
        if self is current_screen:
            load_calls.append("cliente")

    monkeypatch.setattr(type(current_screen), "load_screen", fake_load_screen)

    shell.initialize()
    shell.initialize()

    assert load_calls == ["cliente"]


def test_app_shell_applies_catalog_column_overrides(session_factory, modelo_workflow, monkeypatch):
    monkeypatch.setattr(
        column_overrides,
        "CATALOG_COLUMN_OVERRIDES",
        {"cliente": CatalogColumnOverride(include=("nombre", "ruc"), headers={"ruc": "RUC"})},
    )
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    cliente_screen = shell.current_catalog_screen

    assert cliente_screen is not None
    data_columns = [column for column in cliente_screen.columns if column["kind"] == "data"]
    assert [column["key"] for column in data_columns] == ["nombre", "ruc"]
    assert data_columns[1]["header"] == "RUC"


def test_catalog_workbench_applies_catalog_column_overrides(session_factory, modelo_workflow, monkeypatch):
    monkeypatch.setattr(
        column_overrides,
        "CATALOG_COLUMN_OVERRIDES",
        {"cliente": CatalogColumnOverride(include=("nombre",), widths={"nombre": 260})},
    )
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    workbench = build_default_catalog_workbench(query_service, modelo_workflow.catalog)
    cliente_screen = workbench.current_screen

    data_columns = [column for column in cliente_screen.columns if column["kind"] == "data"]
    assert [column["key"] for column in data_columns] == ["nombre"]
    assert data_columns[0]["width"] == 260


def test_app_shell_exposes_grouped_modules_and_catalog_navigation(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    groups = cast(list[dict[str, object]], shell.module_groups)
    impuesto_screen = shell._catalog_screens["impuesto"]

    assert [group["domain_id"] for group in groups] == [
        "planificacion",
        "contabilidad",
        "operacion",
        "tesoreria_facturacion",
    ]
    assert [module["module_id"] for module in cast(list[dict[str, object]], groups[0]["modules"])] == [
        "cliente",
        "ubicacion",
        "camion",
        "conductor",
        "furgon",
        "thermo",
    ]
    assert shell.current_module_id == "cliente"

    run_action_and_wait_for_applied_load(impuesto_screen, lambda: shell.select_module("impuesto"))

    assert shell.current_module_id == "impuesto"
    assert shell.current_catalog_screen is not None
    assert shell.current_catalog_screen.title == "Gestión de Impuestos"

    form = shell.current_catalog_screen.open_create()

    assert isinstance(form, GenericCatalogFormViewModel)
    fields = cast(list[dict[str, object]], form.fields)
    assert any(field["name"] == "tipo" for field in fields)


def test_cliente_module_supports_create_flow(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    cliente_screen = shell.current_catalog_screen

    assert cliente_screen is not None

    run_action_and_wait_for_applied_load(cliente_screen, shell.initialize)

    baseline = cliente_screen.total_count
    token = uuid4().hex[:8].upper()

    assert cliente_screen.open_create_form() is True
    form = cliente_screen.form_host.active_form

    assert isinstance(form, GenericCatalogFormViewModel)

    form.set_field_value("nombre", f"Cliente QML {token}")
    form.set_field_value("ruc", f"QML-{token}")
    form.set_field_value("direccion", f"Masaya {token}")
    form.set_field_value("facturable", True)

    run_action_and_wait_for_applied_load(cliente_screen, form.submit_form)
    assert form.record_id is not None
    assert cliente_screen.total_count == baseline + 1


def test_catalog_leaving_module_resets_search_but_preserves_filters(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    cliente_screen = shell.current_catalog_screen

    assert cliente_screen is not None

    impuesto_screen = shell._catalog_screens["impuesto"]
    run_action_and_wait_for_applied_load(cliente_screen, shell.initialize)

    search_term = f"NO-MATCH-{uuid4().hex[:8]}"
    run_action_and_wait_for_request(cliente_screen, lambda: cliente_screen.apply_search(search_term))
    run_action_and_wait_for_applied_load(
        cliente_screen,
        lambda: cliente_screen.apply_filter_payload({"field": "facturable", "operator": "eq", "value": True}),
    )

    assert cliente_screen.search_term == search_term
    assert len(cliente_screen.filters) == 1

    run_action_and_wait_for_applied_load(impuesto_screen, lambda: shell.select_module("impuesto"))
    assert shell.current_module_id == "impuesto"

    run_action_and_wait_for_applied_load(cliente_screen, lambda: shell.select_module("cliente"))

    assert shell.current_catalog_screen is cliente_screen
    assert shell.current_catalog_screen.search_term == ""
    assert len(shell.current_catalog_screen.filters) == 1


def test_factura_and_recibo_modules_use_catalog_shell_with_specialized_forms(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog, workflow_service=modelo_workflow)

    factura_screen = shell._catalog_screens["factura"]
    recibo_screen = shell._catalog_screens["recibo"]

    run_action_and_wait_for_applied_load(factura_screen, lambda: shell.select_module("factura"))
    assert shell.current_module_id == "factura"
    assert shell.current_catalog_screen is factura_screen
    assert factura_screen.form_host.presentation_mode == "page"
    assert factura_screen.form_host.navigation_title == "Facturas"
    assert factura_screen.can_export is True
    assert isinstance(shell.current_catalog_screen.open_create(), FacturaFormViewModel)

    run_action_and_wait_for_applied_load(recibo_screen, lambda: shell.select_module("recibo"))
    assert shell.current_module_id == "recibo"
    assert shell.current_catalog_screen is recibo_screen
    assert recibo_screen.form_host.presentation_mode == "page"
    assert recibo_screen.form_host.navigation_title == "Recibos"
    assert recibo_screen.can_export is False
    assert isinstance(shell.current_catalog_screen.open_create(), ReciboFormViewModel)


def test_app_shell_closes_active_form_when_switching_modules(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog, workflow_service=modelo_workflow)

    factura_screen = shell._catalog_screens["factura"]
    recibo_screen = shell._catalog_screens["recibo"]

    run_action_and_wait_for_applied_load(factura_screen, lambda: shell.select_module("factura"))
    assert factura_screen.open_create_form() is True
    factura_form = factura_screen.form_host.active_form
    assert isinstance(factura_form, FacturaFormViewModel)
    assert factura_screen.form_host.is_open is True

    run_action_and_wait_for_applied_load(recibo_screen, lambda: shell.select_module("recibo"))

    assert factura_screen.form_host.is_open is False
    assert factura_screen.form_host.active_form is None
    assert factura_screen.form_host.active_component == ""
    assert recibo_screen.form_host.is_open is False
    assert recibo_screen.form_host.active_form is None


def test_factura_and_recibo_open_readonly_detail_forms_from_catalog(
    session_factory,
    modelo_workflow,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente detalle {token}", ruc=f"DET-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-DET-{token}"
    factura = modelo_workflow.factura.create(factura_payload)
    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": f"REC-DET-{token}",
                "cliente_id": cliente.id,
                "monto": "100.00",
                "moneda": "NIO",
                "tasa_cambio": "1.0000",
            },
            "facturas": [{"factura_id": factura["id"], "monto": "100.00"}],
        }
    )

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog, workflow_service=modelo_workflow)

    factura_screen = shell._catalog_screens["factura"]
    recibo_screen = shell._catalog_screens["recibo"]

    assert factura_screen.open_record_detail(int(factura["id"])) is True
    factura_form = factura_screen.form_host.active_form
    assert isinstance(factura_form, FacturaFormViewModel)
    assert factura_form.mode == "view"
    assert factura_form.title == f"Detalle factura #{factura['id']}"
    assert factura_form.submit_form() is False

    assert recibo_screen.open_record_detail(int(recibo["id"])) is True
    recibo_form = recibo_screen.form_host.active_form
    assert isinstance(recibo_form, ReciboFormViewModel)
    assert recibo_form.mode == "view"
    assert recibo_form.title == f"Detalle recibo #{recibo['id']}"
    assert recibo_form.submit_form() is False


def test_circuito_module_uses_specialized_workflow_when_workflow_service_is_available(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(query_service, modelo_workflow.catalog, workflow_service=modelo_workflow)

    shell.select_module("circuito")

    assert shell.current_module_id == "circuito"
    assert shell.current_catalog_screen is None
    assert shell.current_workflow_module is not None
    assert shell.current_workflow_component == "CircuitoWorkflowPage.qml"
    assert shell.current_workflow_module.title == "Circuitos"
