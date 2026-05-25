from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    EstadoFactura,
    EstadoFacturacion,
    EstadoViaje,
    Factura,
    Moneda,
    TarifaFlete,
    TipoViaje,
    Viaje,
)
from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.presentation import build_default_app_shell
from openlogistic_erp.infrastructure.persistence.session_identity import authenticated_user
from openlogistic_erp.presentation.catalog.table_preferences import InMemoryCatalogTablePreferencesStore
from openlogistic_erp.presentation.workflows.factura import FacturaFormViewModel
from openlogistic_erp.presentation.workflows.recibo import ReciboFormViewModel
from tests.builders.modelo_seed import (
    build_factura_payload,
    build_viaje_export_payload,
    create_cliente,
    create_ruta,
    seed_viaje_dependencies,
)
from tests.builders.security_seed import create_permission, create_role


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_factura_form_exposes_detail_field_layout_metadata(modelo_workflow, reference_lookup_service):
    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    fields = form.detail_fields

    assert [field["name"] for field in fields] == [
        "descripcion",
        "source_costo",
        "source_moneda",
        "costo",
        "conductor",
        "ruta"
    ]
    assert fields[0]["span"] == 2
    assert fields[0]["full_width"] is True


def test_factura_form_exposes_header_layout_sections(modelo_workflow, reference_lookup_service):
    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    layout_items = form.header_layout_items

    assert [item["type"] for item in layout_items] == ["section", "row", "row", "row", "row"]
    assert layout_items[0]["title"] == "Cabecera"
    assert [field["name"] for field in layout_items[1]["fields"]] == ["numero_factura", "fecha_emision"]
    assert layout_items[2]["fields"][0]["name"] == "cliente_id"
    assert layout_items[2]["fields"][0]["kind"] == "reference"
    assert layout_items[2]["fields"][0]["span"] == 2
    assert [field["name"] for field in layout_items[3]["fields"]] == ["dias_credito", "moneda"]
    assert layout_items[4]["fields"][0]["name"] == "tasa_cambio"
    assert layout_items[4]["fields"][0]["span"] == 2


def test_recibo_form_exposes_selected_factura_field_layout_metadata(modelo_workflow, reference_lookup_service):
    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    fields = form.selected_factura_fields

    assert [field["name"] for field in fields] == [
        "label",
        "applied_amount",
        "saldo_restante",
        "subtotal",
        "retenciones",
        "total",
        "estado",
        "moneda",
    ]
    assert fields[0]["span"] == 2
    assert fields[0]["full_width"] is True
    assert fields[1]["label"] == "Aplicado"
    assert fields[2]["label"] == "Saldo restante"
    assert fields[5]["kind"] == "money"
    assert fields[6]["read_only"] is True


def test_recibo_form_exposes_header_layout_sections(modelo_workflow, reference_lookup_service):
    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    layout_items = form.header_layout_items

    assert [item["type"] for item in layout_items] == ["section", "row", "row", "section", "row", "row"]
    assert layout_items[0]["title"] == "Cabecera"
    assert [field["name"] for field in layout_items[1]["fields"]] == ["referencia", "fecha_emision"]
    assert layout_items[2]["fields"][0]["name"] == "cliente_id"
    assert layout_items[2]["fields"][0]["kind"] == "reference"
    assert layout_items[2]["fields"][0]["span"] == 2
    assert layout_items[3]["title"] == "Pago"
    assert [field["name"] for field in layout_items[4]["fields"]] == ["monto", "moneda"]
    assert layout_items[5]["fields"][0]["name"] == "tasa_cambio"
    assert layout_items[5]["fields"][0]["span"] == 2


def test_recibo_qml_binds_exchange_rate_and_cross_currency_context():
    qml_source = (
        REPO_ROOT
        / "src"
        / "openlogistic_erp"
        / "ui"
        / "qml"
        / "workflows"
        / "recibo"
        / "ReciboWorkflowForm.qml"
    ).read_text(encoding="utf-8")

    assert "reciboTasaCambioField" in qml_source
    assert "currency_context_display" in qml_source
    assert "saldo_context_display" in qml_source
    assert "applied_context_display" in qml_source
    assert "reciboFacturaCollapseButton" in qml_source
    assert "facturaCollapsed" in qml_source
    assert "setAllFacturasCollapsed" in qml_source
    assert 'qsTr("Subtotal")' in qml_source
    assert 'qsTr("Retenciones")' in qml_source


def test_client_debt_page_exposes_invoice_level_create_recibo_navigation():
    qml_source = (
        REPO_ROOT
        / "src"
        / "openlogistic_erp"
        / "ui"
        / "qml"
        / "catalog"
        / "ClientDebtPage.qml"
    ).read_text(encoding="utf-8")

    assert 'text: qsTr("Crear recibo")' in qml_source
    assert '"module_id": "recibo"' in qml_source
    assert '"target": "create_form_with_context"' in qml_source
    assert "readonly property var clientRow: modelData" in qml_source
    assert "readonly property var invoiceRow: modelData" in qml_source
    assert '"cliente_id": debtCard.clientRow.cliente_id' in qml_source
    assert '"cliente_label": debtCard.clientRow.cliente_label' in qml_source
    assert '"factura_id": rowCard.invoiceRow.id' in qml_source
    assert '"numero_factura": rowCard.invoiceRow.numero_factura' in qml_source
    assert '"search_term": rowCard.invoiceRow.numero_factura' in qml_source


def test_app_shell_routes_recibo_context_into_selected_factura(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Ruta {token}", ruc=f"REC-ROUTE-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-ROUTE-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )

    assert shell.navigate_to(
        {
            "module_id": "recibo",
            "target": "create_form_with_context",
            "workflow_context": {
                "cliente_id": cliente.id,
                "cliente_label": f"Cliente Ruta {token}",
                "factura_id": factura["id"],
                "numero_factura": factura["numero_factura"],
            },
        }
    ) is True

    recibo_screen = shell.current_catalog_screen
    assert recibo_screen is not None
    recibo_form = recibo_screen.form_host.active_form
    assert isinstance(recibo_form, ReciboFormViewModel)
    assert recibo_form.values["cliente_id"] == cliente.id
    assert [item["id"] for item in recibo_form.selected_facturas] == [factura["id"]]


def test_factura_form_recalculates_detail_costs_when_currency_context_changes(modelo_workflow):
    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.add_gasto_detail()
    form.set_detail_field(0, "source_costo", "10.00")
    form.set_detail_field(0, "source_moneda", "USD")

    assert form.details[0]["costo"] == "10.00"
    assert form.summary["subtotal"] == "10.00"
    assert form.details[0]["costo_display"] == "C$ 10.00"
    assert form.summary["subtotal_display"] == "C$ 10.00"

    form.set_field_value("tasa_cambio", "36.5000")

    assert form.details[0]["costo"] == "365.00"
    assert form.summary["subtotal"] == "365.00"
    assert form.details[0]["costo_display"] == "C$ 365.00"
    assert form.summary["subtotal_display"] == "C$ 365.00"

    form.set_field_value("moneda", "USD")

    assert form.details[0]["costo"] == "10.00"
    assert form.summary["subtotal"] == "10.00"
    assert form.details[0]["source_costo"] == "10.00"
    assert form.details[0]["costo_display"] == "$ 10.00"


def test_factura_form_recalculates_viaje_detail_costs_when_currency_context_changes(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"viaje moneda {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    assert form.add_viaje_detail(int(created["id"])) is True
    assert form.details[0]["source_moneda"] == "USD"
    assert form.details[0]["costo"] == "100.00"

    form.set_field_value("tasa_cambio", "36.5000")

    assert form.details[0]["costo"] == "3650.00"
    assert form.summary["subtotal"] == "3650.00"

    form.set_field_value("moneda", "USD")

    assert form.details[0]["costo"] == "100.00"


def test_factura_form_keeps_trip_context_on_details_and_reload(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"contexto factura {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_field_value("numero_factura", f"FAC-CTX-{token}")
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    assert form.add_viaje_detail(int(created["id"])) is True
    detail = form.details[0]
    assert detail["conductor_label"] == "Juan Perez"
    assert detail["ruta_label"]
    assert detail["fecha_posicionamiento"] == "15/01/2026 08:00"
    assert detail["tipo_viaje"] == TipoViaje.EXPOR.value

    saved = form.submit()
    assert saved is not None

    reloaded = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    reloaded.load(int(saved["id"]))

    reloaded_detail = reloaded.details[0]
    assert reloaded_detail["conductor_label"] == "Juan Perez"
    assert reloaded_detail["ruta_label"] == detail["ruta_label"]
    assert reloaded_detail["fecha_posicionamiento"] == "15/01/2026 08:00"
    assert reloaded_detail["tipo_viaje"] == TipoViaje.EXPOR.value


def test_recibo_form_auto_assigns_partial_amount_then_reassigns_when_amount_matches_total(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("monto", "100.00")
    form.search_factura_candidates(str(factura["numero_factura"]))

    assert len(form.factura_candidates) == 1
    assert form.add_factura(int(factura["id"])) is True
    assert form.allocation_editor_open is False
    assert form.selected_facturas[0]["applied_amount"] == "100.00"
    assert form.summary["saldo_disponible"] == "0.00"

    form.set_field_value("monto", "150.00")

    assert form.allocation_editor_open is False
    assert form.selected_facturas[0]["applied_amount"] == "150.00"
    assert form.selected_facturas[0]["applied_amount_display"] == "C$ 150.00"
    assert form.summary["total_aplicado"] == "150.00"
    assert form.summary["total_aplicado_display"] == "$ 150.00"
    assert form.values["monto"] == "150.00"
    assert form.summary["saldo_disponible"] == "0.00"


def test_recibo_form_auto_distributes_partial_amount_across_selected_facturas_in_order(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-AUTO-{token}")
        session.commit()

    first_payload = build_factura_payload(cliente.id, [])
    first_payload["factura"]["numero_factura"] = f"FAC-400-{token}"
    first_factura = modelo_workflow.factura.create(first_payload)

    second_payload = build_factura_payload(cliente.id, [])
    second_payload["factura"]["numero_factura"] = f"FAC-600-{token}"
    second_factura = modelo_workflow.factura.create(second_payload)

    third_payload = build_factura_payload(cliente.id, [])
    third_payload["factura"]["numero_factura"] = f"FAC-200-{token}"
    third_factura = modelo_workflow.factura.create(third_payload)

    with session_factory() as session:
        first_row = session.get(Factura, first_factura["id"])
        second_row = session.get(Factura, second_factura["id"])
        third_row = session.get(Factura, third_factura["id"])
        assert first_row is not None
        assert second_row is not None
        assert third_row is not None
        first_row._total = Decimal("400.00")
        second_row._total = Decimal("600.00")
        third_row._total = Decimal("200.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )

    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("monto", "1000.00")
    form.search_factura_candidates(token)

    assert form.add_factura(int(first_factura["id"])) is True
    assert form.add_factura(int(second_factura["id"])) is True
    assert form.add_factura(int(third_factura["id"])) is True

    assert form.allocation_editor_open is False
    assert [item["applied_amount"] for item in form.selected_facturas] == ["400.00", "600.00", "0.00"]
    assert form.summary["total_aplicado"] == "1000.00"
    assert form.summary["saldo_disponible"] == "0.00"


def test_recibo_form_manual_allocation_edit_does_not_reset_selected_factura_model(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FOCUS-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-FOCUS-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("monto", "200.00")
    form.search_factura_candidates(str(factura["numero_factura"]))

    assert form.add_factura(int(factura["id"])) is True

    selected_facturas_signal_count = 0
    summary_signal_count = 0
    allocation_draft_signal_count = 0

    def count_selected_facturas_signal() -> None:
        nonlocal selected_facturas_signal_count
        selected_facturas_signal_count += 1

    def count_summary_signal() -> None:
        nonlocal summary_signal_count
        summary_signal_count += 1

    def count_allocation_draft_signal() -> None:
        nonlocal allocation_draft_signal_count
        allocation_draft_signal_count += 1

    form.selectedFacturasChanged.connect(count_selected_facturas_signal)
    form.summaryChanged.connect(count_summary_signal)
    form.allocationDraftFacturasChanged.connect(count_allocation_draft_signal)

    original_applied_amount = form.selected_facturas[0]["applied_amount"]
    original_total_aplicado = form.summary["total_aplicado"]

    form.open_allocation_editor()
    selected_facturas_signal_count = 0
    summary_signal_count = 0
    allocation_draft_signal_count = 0

    form.set_factura_applied_amount(0, "125.50")

    assert form.allocation_draft_facturas[0]["applied_amount"] == "125.50"
    assert form.selected_facturas[0]["applied_amount"] == original_applied_amount
    assert form.summary["total_aplicado"] == original_total_aplicado
    assert summary_signal_count == 0
    assert selected_facturas_signal_count == 0
    assert allocation_draft_signal_count == 0

    assert form.apply_allocation_editor() is True

    assert form.allocation_editor_open is False
    assert form.selected_facturas[0]["applied_amount"] == "125.50"
    assert form.summary["total_aplicado"] == "125.50"
    assert summary_signal_count >= 1
    assert selected_facturas_signal_count == 1


def test_recibo_form_auto_distributes_nio_receipt_to_usd_invoice_using_rate(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FORM-X-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-USD-FORM-{token}"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal("1000.00")
        factura_row._total = Decimal("1000.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("referencia", f"REC-FORM-X-{token}")
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("moneda", "NIO")
    form.set_field_value("tasa_cambio", "36.5000")
    form.set_field_value("monto", "36500.00")
    form.search_factura_candidates(token)

    assert form.add_factura(int(factura["id"])) is True

    assert form.selected_facturas[0]["applied_amount"] == "1000.00"
    assert form.summary["monto_recibo"] == "36500.00"
    assert form.summary["total_aplicado"] == "36500.00"
    assert form.summary["saldo_disponible"] == "0.00"

    payload, errors = form._build_submit_payload()
    assert errors == {}
    assert payload["recibo"]["tasa_cambio"] == "36.5000"
    assert payload["facturas"] == [{"factura_id": int(factura["id"]), "monto": "1000.00"}]


def test_recibo_form_auto_distributes_usd_receipt_to_nio_invoice_using_rate(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FORM-USD-NIO-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-NIO-FORM-{token}"
    factura_payload["factura"]["moneda"] = Moneda.NIO
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal("36500.00")
        factura_row._total = Decimal("36500.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("referencia", f"REC-FORM-USD-NIO-{token}")
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("moneda", "USD")
    form.set_field_value("tasa_cambio", "36.5000")
    form.set_field_value("monto", "1000.00")
    form.search_factura_candidates(token)

    assert form.add_factura(int(factura["id"])) is True

    assert form.selected_facturas[0]["applied_amount"] == "36500.00"
    assert form.summary["monto_recibo"] == "1000.00"
    assert form.summary["total_aplicado"] == "1000.00"
    assert form.summary["saldo_disponible"] == "0.00"

    payload, errors = form._build_submit_payload()
    assert errors == {}
    assert payload["recibo"]["tasa_cambio"] == "36.5000"
    assert payload["facturas"] == [{"factura_id": int(factura["id"]), "monto": "36500.00"}]


def test_recibo_form_auto_distributes_partial_nio_receipt_to_usd_invoice_without_overapplying(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FORM-PART-X-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-USD-PART-{token}"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal("1000.00")
        factura_row._total = Decimal("1000.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("referencia", f"REC-FORM-PART-X-{token}")
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("moneda", "NIO")
    form.set_field_value("tasa_cambio", "36.5000")
    form.set_field_value("monto", "1000.00")
    form.search_factura_candidates(token)

    assert form.add_factura(int(factura["id"])) is True

    assert form.selected_facturas[0]["applied_amount"] == "27.39"
    assert form.summary["total_aplicado"] == "999.74"
    assert form.summary["saldo_disponible"] == "0.26"
    assert form.summary["faltante"] == "0.00"


def test_recibo_form_revalidates_when_exchange_rate_changes(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FORM-RATE-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-RATE-FORM-{token}"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal("1000.00")
        factura_row._total = Decimal("1000.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("moneda", "NIO")
    form.set_field_value("monto", "36500.00")
    form.set_field_value("tasa_cambio", "36.5000")
    form.search_factura_candidates(token)
    assert form.add_factura(int(factura["id"])) is True

    form.set_field_value("tasa_cambio", "40.0000")

    assert form.selected_facturas[0]["applied_amount"] == "912.50"
    assert form.summary["total_aplicado"] == "36500.00"


def test_recibo_form_exposes_cross_currency_context_for_selected_invoices(
    modelo_workflow,
    session_factory,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-FORM-CTX-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-CTX-FORM-{token}"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal("1000.00")
        factura_row._total = Decimal("1000.00")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
    )
    form.load(None)
    form.set_field_value("cliente_id", cliente.id)
    form.set_field_value("moneda", "NIO")
    form.set_field_value("tasa_cambio", "36.5000")
    form.set_field_value("monto", "36500.00")
    form.search_factura_candidates(token)

    assert form.add_factura(int(factura["id"])) is True

    selected = form.selected_facturas[0]
    assert selected["moneda"] == "USD"
    assert selected["recibo_moneda"] == "NIO"
    assert selected["cross_currency"] is True
    assert selected["saldo_restante_display"] == "$ 1,000.00"
    assert selected["saldo_restante_recibo_display"] == "C$ 36,500.00"
    assert selected["currency_context_display"] == "Factura USD -> recibo NIO @ 36.5000"
    assert selected["saldo_context_display"] == "$ 1,000.00 / C$ 36,500.00"
    assert selected["applied_amount_display"] == "$ 1,000.00"
    assert selected["applied_amount_recibo_display"] == "C$ 36,500.00"
    assert selected["applied_context_display"] == "$ 1,000.00 / C$ 36,500.00"
    assert form.summary["currency_context_display"] == "Recibo NIO con facturas en USD @ 36.5000"


def test_factura_form_exposes_cliente_lookup_with_canonical_label_and_real_id(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Lookup {token}", ruc=f"FAC-LK-{token}")
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente.id, f"Cliente Lookup {token}")
    options = form.lookup_options("cliente_id")

    matched_option = next(option for option in options if option["value"] == cliente.id)
    assert matched_option["label"] == f"Cliente Lookup {token}"

    assert form.values["cliente_id"] == cliente.id
    assert any(option["value"] == cliente.id and "Cliente Lookup" in option["label"] for option in form.lookup_options("cliente_id"))


def test_factura_form_primes_cliente_options_on_create(
    modelo_workflow,
    session_factory,
    auth_service,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Prime {token}", ruc=f"FAC-PR-{token}")
        cliente_read = create_permission(session, "cliente", "leer")
        factura_create = create_permission(session, "factura", "crear")
        role = create_role(session, name=uuid4().hex[:10], permissions=[cliente_read, factura_create])
        session.commit()

    user = auth_service.create_user(
        username=f"factura_prime_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    with authenticated_user(user.id):
        form.load(None)

        assert any(
            option["value"] == cliente.id and option["label"] == f"Cliente Prime {token}"
            for option in form.lookup_options("cliente_id")
        )


def test_factura_form_searches_viaje_candidates_as_lookup_options_with_metadata(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente = create_cliente(session, nombre=f"Cliente Viaje {token}", ruc=f"VIAJE-LK-{token}")
        session.commit()
        deps["cliente_id"] = cliente.id

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            viaje={
                "descripcion": f"Viaje lookup {token}",
            },
        )
    )
    assert created is not None

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente.id, f"Cliente Viaje {token}")
    form.set_include_non_finalized(1)

    form.search_lookup_options("viaje_id", token)
    options = form.lookup_options("viaje_id")

    assert len(options) == 1
    option = options[0]
    assert option["value"] == created["id"]
    assert option["label"] == f"Viaje #{created['id']}"
    assert option["descripcion"] == f"Viaje lookup {token}"
    assert "ruta_label" in option
    assert "tiene_tarifa" in option

    assert form.add_viaje_detail(int(option["value"])) is False
    assert form.pending_tarifa["viaje_id"] == created["id"]
    assert form.pending_tarifa["referencia"] == f"Viaje #{created['id']}"


def test_factura_viaje_search_filters_registered_finalized_trips_by_default(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    finalized = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            viaje={"descripcion": f"finalizado {token}"},
            detalle_operacion={"descarga": {"fecha_descarga": datetime(2026, 1, 18, 8, 0, 0)}},
        )
    )
    non_finalized = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"pendiente {token}"})
    )
    with session_factory() as session:
        finalized_row = session.get(Viaje, finalized["id"])
        assert finalized_row is not None
        circuito_id = int(finalized_row._circuito_id)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()
    empty_trip = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "_circuito_id": circuito_id,
                "descripcion": f"vacio {token}",
            }
        }
    )

    with session_factory() as session:
        finalized_row = session.get(Viaje, finalized["id"])
        assert finalized_row is not None
        finalized_row.estado = EstadoViaje.FINALIZADO
        finalized_row._estado_facturacion = EstadoFacturacion.REGISTRADO
        non_finalized_row = session.get(Viaje, non_finalized["id"])
        assert non_finalized_row is not None
        non_finalized_row.estado = EstadoViaje.PENDIENTE
        non_finalized_row._estado_facturacion = EstadoFacturacion.REGISTRADO
        empty_row = session.get(Viaje, empty_trip["id"])
        assert empty_row is not None
        empty_row.estado = EstadoViaje.FINALIZADO
        empty_row._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")

    form.search_lookup_options("viaje_id", token)
    options = form.lookup_options("viaje_id")

    assert [option["value"] for option in options] == [finalized["id"]]
    option = options[0]
    assert option["fecha_posicionamiento"] == "15/01/2026 08:00"
    assert option["tipo_viaje"] == TipoViaje.EXPOR.value
    assert option["dias_viajados"] == 3
    assert len(option["tarifas"]) == 1

    form.set_include_non_finalized(1)
    form.search_lookup_options("viaje_id", token)

    values = {option["value"] for option in form.lookup_options("viaje_id")}
    assert values == {finalized["id"], non_finalized["id"]}


def test_factura_form_hydrates_navigation_context_with_prefilled_client_and_selected_trip(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"context route {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente_id,
            "cliente_label": "Cliente Demo",
            "viaje_id": created["id"],
            "search_term": token,
        }
    ) is True

    assert form.values["cliente_id"] == cliente_id
    assert form.selected_viaje_candidate_ids == [created["id"]]
    assert form.details == []


def test_recibo_form_hydrates_navigation_context_with_prefilled_client_and_selected_factura(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-CTX-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-REC-CTX-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente.id,
            "cliente_label": "Cliente Contexto",
            "factura_id": factura["id"],
            "search_term": token,
        }
    ) is True

    assert form.values["cliente_id"] == cliente.id
    assert [item["id"] for item in form.selected_facturas] == [factura["id"]]


def test_recibo_form_hydrates_navigation_context_without_search_term_for_older_collectible_factura(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-OLD-{token}")
        session.commit()

    target_payload = build_factura_payload(cliente.id, [])
    target_payload["factura"]["numero_factura"] = f"FAC-REC-OLD-TARGET-{token}"
    target_factura = modelo_workflow.factura.create(target_payload)
    for index in range(20):
        newer_payload = build_factura_payload(cliente.id, [])
        newer_payload["factura"]["numero_factura"] = f"FAC-REC-OLD-{index:02d}-{token}"
        modelo_workflow.factura.create(newer_payload)

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente.id,
            "cliente_label": "Cliente Contexto",
            "factura_id": target_factura["id"],
        }
    ) is True

    assert [item["id"] for item in form.selected_facturas] == [target_factura["id"]]


def test_recibo_form_rejects_malformed_navigation_context_factura_id(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-BAD-{token}")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente.id,
            "cliente_label": "Cliente Contexto",
            "factura_id": "not-an-id",
        }
    ) is False

    assert form.values["cliente_id"] == ""
    assert form.selected_facturas == []
    assert form.error_message == "Se requiere una factura valida para precargar el recibo."


def test_recibo_form_rejects_non_positive_navigation_context_factura_id(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-NONPOS-{token}")
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente.id,
            "cliente_label": "Cliente Contexto",
            "factura_id": 0,
        }
    ) is False

    assert form.values["cliente_id"] == ""
    assert form.selected_facturas == []
    assert form.error_message == "Se requiere una factura valida para precargar el recibo."


def test_recibo_form_keeps_client_loaded_when_navigation_context_factura_is_no_longer_collectible(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"REC-STALE-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-REC-STALE-{token}"
    factura = modelo_workflow.factura.create(factura_payload)
    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row.estado = EstadoFactura.PAGADA
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    assert form.apply_navigation_context(
        {
            "cliente_id": cliente.id,
            "cliente_label": "Cliente Contexto",
            "factura_id": factura["id"],
            "search_term": token,
        }
    ) is False

    assert form.values["cliente_id"] == cliente.id
    assert form.selected_facturas == []
    assert form.error_message == "La factura ya no esta disponible para crear recibo."


def test_factura_form_requires_tarifa_choice_when_selected_trip_has_multiple_tarifas(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        session.add(
            TarifaFlete(
                cliente_id=deps["cliente_id"],
                ruta_id=deps["ruta_id"],
                costo=Decimal("125.00"),
                moneda=Moneda.USD,
                descripcion="Alterna",
            )
        )
        session.commit()

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"multi tarifa {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", deps["cliente_id"], "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    option = form.lookup_options("viaje_id")[0]
    assert option["tarifa_count"] == 2
    assert [tarifa["costo"] for tarifa in option["tarifas"]] == ["100.00", "125.00"]

    form.toggle_viaje_candidate_selection(int(option["value"]), 1)
    assert form.add_selected_viajes() is False
    assert len(form.pending_tarifa_choices) == 1
    assert form.details == []

    form.set_pending_tarifa_selection(int(option["value"]), int(option["tarifas"][1]["id"]))
    assert form.confirm_pending_tarifa_choices() is True

    assert len(form.details) == 1
    assert form.details[0]["tarifa_id"] == option["tarifas"][1]["id"]
    assert form.details[0]["source_costo"] == "125.00"


def test_factura_form_batch_adds_single_tarifa_trips_and_prompts_for_ambiguous_ones(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        other_route_row = create_ruta(session)
        other_route = dict(deps)
        other_route["ruta_id"] = other_route_row.id
        other_route["origen_id"] = other_route_row.origen_id
        other_route["destino_id"] = other_route_row.destino_id
        session.add(
            TarifaFlete(
                cliente_id=deps["cliente_id"],
                ruta_id=other_route["ruta_id"],
                costo=Decimal("100.00"),
                moneda=Moneda.USD,
            )
        )
        session.add(
            TarifaFlete(
                cliente_id=deps["cliente_id"],
                ruta_id=deps["ruta_id"],
                costo=Decimal("150.00"),
                moneda=Moneda.USD,
                descripcion="Alterna lote",
            )
        )
        session.commit()

    single = modelo_workflow.viaje.create(
        build_viaje_export_payload(other_route, viaje={"descripcion": f"lote unico {token}"})
    )
    ambiguous = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"lote multiple {token}"})
    )
    with session_factory() as session:
        for viaje_id in (single["id"], ambiguous["id"]):
            viaje = session.get(Viaje, viaje_id)
            assert viaje is not None
            viaje.estado = EstadoViaje.FINALIZADO
            viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", deps["cliente_id"], "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    for option in form.lookup_options("viaje_id"):
        form.toggle_viaje_candidate_selection(int(option["value"]), 1)

    assert form.add_selected_viajes() is False
    assert [detail["viaje_id"] for detail in form.details] == [single["id"]]
    assert [choice["viaje_id"] for choice in form.pending_tarifa_choices] == [ambiguous["id"]]


def test_factura_candidate_model_tracks_lookup_resets_and_selection_state(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"modelo candidato {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    assert form.viaje_candidate_model.rowCount() == 1
    assert form.viaje_candidate_model.columnCount() == 7
    assert [column["key"] for column in form.viaje_candidate_model.columns()] == [
        "selected",
        "referencia",
        "conductor_label",
        "ruta_label",
        "fecha_posicionamiento",
        "tipo_viaje",
        "dias_viajados",
    ]
    assert form.viaje_candidate_model.row_data(0)["value"] == created["id"]
    assert form.viaje_candidate_model.cell_data(0, 1) == f"Viaje #{created['id']}"

    form.toggle_viaje_candidate_selection(int(created["id"]), 1)
    assert form.viaje_candidate_model.cell_data(0, 0) is True

    form.set_lookup_field_value("cliente_id", "", "")

    assert form.viaje_candidate_model.rowCount() == 0
    assert form.selected_viaje_candidate_ids == []


def test_factura_candidate_model_exposes_stable_table_view_roles(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"roles tabla {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")
    form.search_lookup_options("viaje_id", token)

    role_names = {bytes(name).decode("ascii") for name in form.viaje_candidate_model.roleNames().values()}

    assert {"cellValue", "rowData", "selected"}.issubset(role_names)

    row_index = form.viaje_candidate_model.index(0, 0)
    row_data_role = next(role for role, name in form.viaje_candidate_model.roleNames().items() if name == b"rowData")
    selected_role = next(role for role, name in form.viaje_candidate_model.roleNames().items() if name == b"selected")

    assert form.viaje_candidate_model.data(row_index, row_data_role)["value"] == created["id"]
    assert form.viaje_candidate_model.data(row_index, selected_role) is False

    form.toggle_viaje_candidate_selection(int(created["id"]), 1)

    assert form.viaje_candidate_model.data(row_index, selected_role) is True


def test_factura_viaje_selector_persists_candidate_column_widths(modelo_workflow, reference_lookup_service):
    store = InMemoryCatalogTablePreferencesStore()
    form = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
        table_preferences_store=store,
    )

    form.set_viaje_candidate_column_width("ruta_label", 340)

    reloaded = FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
        table_preferences_store=store,
    )

    column_by_key = {column["key"]: column for column in reloaded.viaje_candidate_model.columns()}
    assert column_by_key["ruta_label"]["width"] == 340


def test_recibo_form_searches_factura_candidates_as_lookup_options_with_metadata(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Recibo {token}", ruc=f"REC-LK-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-LK-{token}"
    factura = modelo_workflow.factura.create(factura_payload)
    assert factura is not None

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente.id, f"Cliente Recibo {token}")
    form.search_lookup_options("factura_id", token)
    options = form.lookup_options("factura_id")

    assert len(options) == 1
    option = options[0]
    assert option["value"] == factura["id"]
    assert option["label"] == f"FAC-LK-{token}"
    assert option["numero_factura"] == f"FAC-LK-{token}"
    assert "saldo_restante" in option
    assert option["saldo_restante_display"].startswith("C$ ")
    assert "estado" in option
    assert option["moneda"] in {"USD", "NIO"}

    assert form.add_factura(int(option["value"])) is True
    assert form.selected_facturas[0]["id"] == factura["id"]
    assert form.selected_facturas[0]["label"] == f"FAC-LK-{token}"


def test_recibo_form_loads_exchange_rate_from_saved_recibo(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
):
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente tasa recibo {token}", ruc=f"REC-TASA-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-TASA-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    created = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": f"REC-TASA-{token}",
                "cliente_id": cliente.id,
                "monto": "150.00",
                "moneda": "NIO",
                "tasa_cambio": "36.5000",
            },
            "facturas": [{"factura_id": factura["id"], "monto": "150.00"}],
        }
    )

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(int(created["id"]))

    assert form.values["tasa_cambio"] == "36.5000"


def test_recibo_form_batch_adds_selected_facturas_and_excludes_paid_candidates(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Recibo Drawer {token}", ruc=f"REC-DRW-{token}")
        session.commit()

    pending_payload = build_factura_payload(cliente.id, [])
    pending_payload["factura"]["numero_factura"] = f"FAC-PEND-{token}"
    pending_factura = modelo_workflow.factura.create(pending_payload)

    partial_payload = build_factura_payload(cliente.id, [])
    partial_payload["factura"]["numero_factura"] = f"FAC-PARC-{token}"
    partial_factura = modelo_workflow.factura.create(partial_payload)

    paid_payload = build_factura_payload(cliente.id, [])
    paid_payload["factura"]["numero_factura"] = f"FAC-PAG-{token}"
    paid_factura = modelo_workflow.factura.create(paid_payload)

    with session_factory() as session:
        pending_row = session.get(Factura, pending_factura["id"])
        partial_row = session.get(Factura, partial_factura["id"])
        paid_row = session.get(Factura, paid_factura["id"])
        assert pending_row is not None
        assert partial_row is not None
        assert paid_row is not None
        partial_row.estado = EstadoFactura.PAGADAPAR
        paid_row.estado = EstadoFactura.PAGADA
        session.commit()

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente.id, f"Cliente Recibo Drawer {token}")

    assert form.factura_selector_open is False
    form.open_factura_selector()
    assert form.factura_selector_open is True

    form.search_factura_candidates(token)
    options = form.factura_candidates

    assert {option["value"] for option in options} == {pending_factura["id"], partial_factura["id"]}
    assert paid_factura["id"] not in {option["value"] for option in options}

    for option in options:
        form.toggle_factura_candidate_selection(int(option["value"]), 1)

    assert form.add_selected_facturas() is True
    assert form.factura_selector_open is True
    assert {item["id"] for item in form.selected_facturas} == {pending_factura["id"], partial_factura["id"]}
    assert form.factura_candidates == []


def test_recibo_candidate_model_tracks_lookup_resets_and_selection_state(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Recibo Model {token}", ruc=f"REC-MDL-{token}")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = f"FAC-MDL-{token}"
    factura = modelo_workflow.factura.create(factura_payload)

    form = ReciboFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente.id, f"Cliente Recibo Model {token}")
    form.search_lookup_options("factura_id", token)

    assert form.factura_candidate_model.rowCount() == 1
    assert form.factura_candidate_model.columnCount() == 4
    assert [column["key"] for column in form.factura_candidate_model.columns()] == [
        "selected",
        "label",
        "estado",
        "saldo_restante_display",
    ]
    assert form.factura_candidate_model.row_data(0)["value"] == factura["id"]
    assert form.factura_candidate_model.cell_data(0, 1) == f"FAC-MDL-{token}"
    assert form.factura_candidate_model.cell_data(0, 3).startswith("C$ ")

    form.toggle_factura_candidate_selection(int(factura["id"]), 1)
    assert form.factura_candidate_model.cell_data(0, 0) is True

    form.set_lookup_field_value("cliente_id", "", "")

    assert form.factura_candidate_model.rowCount() == 0
    assert form.selected_factura_candidate_ids == []
