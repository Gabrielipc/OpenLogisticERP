from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

import openlogistic_erp.presentation.dashboard as dashboard_module
from openlogistic_erp.application.dashboard import DashboardService
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    Camion,
    Circuito,
    EstadoCamion,
    EstadoCircuito,
    EstadoConductor,
    EstadoFactura,
    EstadoFacturacion,
    EstadoRecibo,
    EstadoViaje,
    Factura,
    Moneda,
    Recibo,
    ReciboFactura,
    Viaje,
)
from openlogistic_erp.presentation.dashboard import DashboardViewModel
from tests.builders.modelo_seed import (
    build_viaje_export_payload,
    create_camion,
    create_cliente,
    create_conductor,
    create_furgon,
    create_ruta,
    create_thermo,
    seed_viaje_dependencies,
)


def test_dashboard_service_returns_zero_kpis_without_data(session_factory):
    class EmptyQuery:
        def filter(self, *_args):
            return self

        def options(self, *_args):
            return self

        def group_by(self, *_args):
            return self

        def scalar(self):
            return 0

        def all(self):
            return []

    class EmptySession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def query(self, *_args):
            return EmptyQuery()

    service = DashboardService(lambda: EmptySession())

    assert service.get_kpis() == {
        "viajes_activos": 0,
        "circuitos_en_progreso": 0,
        "camiones_disponibles": 0,
        "camiones_en_viaje": 0,
        "cuentas_por_cobrar_clientes": 0,
        "facturacion_pendiente": 0,
        "facturas_atrasadas": 0,
        "fleet_status": {
            "camiones_disponibles": 0,
            "camiones_en_viaje": 0,
            "camiones_mantenimiento": 0,
            "camiones_baja": 0,
            "camiones_vendidos": 0,
            "camiones_agregados": 0,
        },
        "driver_status": {
            "conductores_disponibles": 0,
            "conductores_en_viaje": 0,
            "conductores_instrucciones": 0,
            "conductores_baja": 0,
            "conductores_agregados": 0,
        },
        "summary": {
            "circuitos_en_progreso": 0,
            "viajes_en_progreso": 0,
        },
        "finance": {
            "facturacion_pendiente": 0,
            "cuentas_por_cobrar_clientes": 0,
            "facturas_atrasadas": 0,
        },
    }


def test_dashboard_service_returns_legacy_kpi_counts(session_factory, modelo_workflow):
    service = DashboardService(session_factory)
    baseline = service.get_kpis()

    with session_factory() as session:
        active_deps = _seed_unique_viaje_dependencies(session, "DASH-ACT")
    active_trip = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            active_deps,
            viaje={"referencia": "DASH-ACTIVE-TRIP"},
        )
    )

    with session_factory() as session:
        viaje = session.get(Viaje, active_trip["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.ENCURSO
        camion = session.get(type(viaje.camion), viaje.camion_id)
        assert camion is not None
        camion.estado = EstadoCamion.ACTIVO
        create_camion(session, placa="DASH-FREE-CAMION", chasis="DASH-FREE-CAMION-CH", estado=EstadoCamion.ACTIVO)
        create_camion(session, placa="DASH-MAINT-CAMION", chasis="DASH-MAINT-CAMION-CH", estado=EstadoCamion.MANTENIMIENTO)
        create_conductor(
            session,
            nombre="DASH",
            apellido="Driver Disponible",
            cedula="DASH-DRIVER-DISP",
            licencia="DASH-DRIVER-DISP",
            estado=EstadoConductor.DISPONIBLE,
        )
        create_conductor(
            session,
            nombre="DASH",
            apellido="Driver Instrucciones",
            cedula="DASH-DRIVER-INST",
            licencia="DASH-DRIVER-INST",
            estado=EstadoConductor.INSTRUCCIONES,
        )
        session.commit()

    with session_factory() as session:
        billing_deps = _seed_unique_viaje_dependencies(session, "DASH-BILL")
    billing_trip = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            billing_deps,
            viaje={"referencia": "DASH-BILLING-TRIP"},
        )
    )

    with session_factory() as session:
        viaje = session.get(Viaje, billing_trip["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        circuito = session.get(Circuito, viaje._circuito_id)
        assert circuito is not None
        circuito.estado = EstadoCircuito.FINALIZADO

        priority_cliente = create_cliente(session, ruc="DASH-PRIORITY-RUC")
        session.add(
            Factura(
                numero_factura="DASH-OVERDUE-001",
                fecha_emision=datetime(2026, 1, 10, 8, 0, 0),
                cliente_id=priority_cliente.id,
                dias_credito=10,
                moneda=Moneda.USD,
                _subtotal=Decimal("100.00"),
                _total=Decimal("100.00"),
                tasa_cambio=Decimal("1.0000"),
                estado=EstadoFactura.ATRASADA,
            )
        )
        session.commit()

    result = service.get_kpis()

    assert {
        key: result[key]
        for key in (
            "viajes_activos",
            "circuitos_en_progreso",
            "camiones_en_viaje",
            "cuentas_por_cobrar_clientes",
            "facturacion_pendiente",
            "facturas_atrasadas",
        )
    } == {
        "viajes_activos": baseline["viajes_activos"] + 1,
        "circuitos_en_progreso": baseline["circuitos_en_progreso"] + 1,
        "camiones_en_viaje": baseline["camiones_en_viaje"] + 1,
        "cuentas_por_cobrar_clientes": baseline["cuentas_por_cobrar_clientes"] + 1,
        "facturacion_pendiente": baseline["facturacion_pendiente"] + 1,
        "facturas_atrasadas": baseline["facturas_atrasadas"] + 1,
    }
    with session_factory() as session:
        active_trucks = int(
            session.query(func.count(Camion.id)).filter(Camion.estado == EstadoCamion.ACTIVO).scalar() or 0
        )
    assert result["camiones_disponibles"] == active_trucks
    assert result["fleet_status"]["camiones_disponibles"] == result["camiones_disponibles"]
    assert result["fleet_status"]["camiones_en_viaje"] == result["camiones_en_viaje"]
    assert result["fleet_status"]["camiones_mantenimiento"] >= 1
    assert result["driver_status"]["conductores_disponibles"] >= 1
    assert result["driver_status"]["conductores_instrucciones"] >= 1
    assert result["driver_status"]["conductores_en_viaje"] >= 1
    assert result["summary"]["circuitos_en_progreso"] == result["circuitos_en_progreso"]
    assert result["finance"]["facturacion_pendiente"] == result["facturacion_pendiente"]
    assert result["finance"]["cuentas_por_cobrar_clientes"] == result["cuentas_por_cobrar_clientes"]
    assert result["finance"]["facturas_atrasadas"] == result["facturas_atrasadas"]


def test_dashboard_service_never_returns_negative_available_trucks(session_factory, modelo_workflow):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    trip = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    with session_factory() as session:
        viaje = session.get(Viaje, trip["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.ENCURSO
        camion = session.get(type(viaje.camion), viaje.camion_id)
        assert camion is not None
        camion.estado = EstadoCamion.ENVIAJE
        session.commit()

    service = DashboardService(session_factory)

    assert service.get_kpis()["camiones_disponibles"] == 0


def test_dashboard_service_counts_clients_with_open_debt_ignoring_canceled_receipts(session_factory):
    with session_factory() as session:
        open_cliente = create_cliente(session, ruc="DASH-DEBT-OPEN")
        paid_cliente = create_cliente(session, ruc="DASH-DEBT-PAID")
        canceled_receipt_cliente = create_cliente(session, ruc="DASH-DEBT-CANCELED-RECEIPT")
        annulled_cliente = create_cliente(session, ruc="DASH-DEBT-ANNULLED")

        open_factura = _create_factura(session, open_cliente.id, "DASH-DEBT-OPEN-001", Decimal("100.00"))
        paid_factura = _create_factura(session, paid_cliente.id, "DASH-DEBT-PAID-001", Decimal("100.00"))
        canceled_receipt_factura = _create_factura(
            session,
            canceled_receipt_cliente.id,
            "DASH-DEBT-CANCELED-001",
            Decimal("100.00"),
        )
        _create_factura(
            session,
            annulled_cliente.id,
            "DASH-DEBT-ANNULLED-001",
            Decimal("100.00"),
            estado=EstadoFactura.ANULADA,
        )

        _apply_payment(session, paid_factura, Decimal("100.00"), EstadoRecibo.ACTIVO)
        _apply_payment(session, canceled_receipt_factura, Decimal("100.00"), EstadoRecibo.ANULADO)
        session.commit()

    result = DashboardService(session_factory).get_kpis()

    assert result["cuentas_por_cobrar_clientes"] >= 2
    assert result["finance"]["cuentas_por_cobrar_clientes"] == result["cuentas_por_cobrar_clientes"]
    assert open_factura.id is not None


def test_dashboard_service_returns_all_client_debt_rows_without_priority_mode(session_factory):
    with session_factory() as session:
        overdue_client = create_cliente(session, ruc="DASH-DEBT-ROWS-OVERDUE")
        open_client = create_cliente(session, ruc="DASH-DEBT-ROWS-OPEN")
        overdue = _create_factura(session, overdue_client.id, "DASH-DEBT-ROWS-001", Decimal("100.00"), estado=EstadoFactura.ATRASADA)
        second_overdue = _create_factura(
            session,
            overdue_client.id,
            "DASH-DEBT-ROWS-003",
            Decimal("75.00"),
            estado=EstadoFactura.ATRASADA,
        )
        _create_factura(session, open_client.id, "DASH-DEBT-ROWS-002", Decimal("50.00"))
        session.commit()

    service = DashboardService(session_factory)

    all_rows = service.get_client_debt_rows()

    assert {row["cliente_id"] for row in all_rows}.issuperset({overdue_client.id, open_client.id})
    overdue_row = next(row for row in all_rows if row["cliente_id"] == overdue_client.id)
    assert [row["cliente_id"] for row in all_rows].count(overdue_client.id) == 1
    assert {
        (invoice["id"], invoice["numero_factura"])
        for invoice in overdue_row["facturas"]
    } == {
        (overdue.id, "DASH-DEBT-ROWS-001"),
        (second_overdue.id, "DASH-DEBT-ROWS-003"),
    }
    assert {
        invoice["id"]: invoice
        for invoice in overdue_row["facturas"]
    } == {
        overdue.id: {
            "id": overdue.id,
            "numero_factura": "DASH-DEBT-ROWS-001",
            "estado": EstadoFactura.ATRASADA.value,
            "moneda": "USD",
            "saldo": "100.00",
            "saldo_display": "$ 100.00",
        },
        second_overdue.id: {
            "id": second_overdue.id,
            "numero_factura": "DASH-DEBT-ROWS-003",
            "estado": EstadoFactura.ATRASADA.value,
            "moneda": "USD",
            "saldo": "75.00",
            "saldo_display": "$ 75.00",
        },
    }


def test_dashboard_service_formats_client_debt_balances_by_currency(session_factory):
    with session_factory() as session:
        mixed_client = create_cliente(session, ruc="DASH-DEBT-MIXED-CURRENCY")
        usd_invoice = _create_factura(
            session,
            mixed_client.id,
            "DASH-DEBT-MIXED-USD",
            Decimal("100.00"),
            moneda=Moneda.USD,
        )
        nio_invoice = _create_factura(
            session,
            mixed_client.id,
            "DASH-DEBT-MIXED-NIO",
            Decimal("2500.00"),
            moneda=Moneda.NIO,
        )
        session.commit()

    rows = DashboardService(session_factory).get_client_debt_rows()

    row = next(item for item in rows if item["cliente_id"] == mixed_client.id)
    assert row["saldo_total_display"] == "$ 100.00 / C$ 2,500.00"
    assert row["saldos_por_moneda"] == [
        {"moneda": "USD", "saldo": "100.00", "saldo_display": "$ 100.00"},
        {"moneda": "NIO", "saldo": "2500.00", "saldo_display": "C$ 2,500.00"},
    ]
    assert {
        invoice["id"]: invoice
        for invoice in row["facturas"]
        if invoice["id"] in {usd_invoice.id, nio_invoice.id}
    } == {
        usd_invoice.id: {
            "id": usd_invoice.id,
            "numero_factura": "DASH-DEBT-MIXED-USD",
            "estado": EstadoFactura.PENDIENTE.value,
            "moneda": "USD",
            "saldo": "100.00",
            "saldo_display": "$ 100.00",
        },
        nio_invoice.id: {
            "id": nio_invoice.id,
            "numero_factura": "DASH-DEBT-MIXED-NIO",
            "estado": EstadoFactura.PENDIENTE.value,
            "moneda": "NIO",
            "saldo": "2500.00",
            "saldo_display": "C$ 2,500.00",
        },
    }


def test_dashboard_service_returns_monthly_billing_timeline_by_currency(session_factory):
    with session_factory() as session:
        usd_client = create_cliente(session, ruc="DASH-TL-USD")
        nio_client = create_cliente(session, ruc="DASH-TL-NIO")
        usd_invoice = _create_factura(
            session,
            usd_client.id,
            "DASH-TL-USD-001",
            Decimal("120.00"),
            moneda=Moneda.USD,
        )
        nio_invoice = _create_factura(
            session,
            nio_client.id,
            "DASH-TL-NIO-001",
            Decimal("2400.00"),
            moneda=Moneda.NIO,
        )
        usd_invoice.fecha_emision = datetime(2036, 5, 4, 9, 0, 0)
        nio_invoice.fecha_emision = datetime(2036, 4, 18, 9, 0, 0)
        _apply_payment_on_date(
            session,
            usd_invoice,
            Decimal("75.00"),
            EstadoRecibo.ACTIVO,
            datetime(2036, 5, 20, 9, 0, 0),
        )
        _apply_payment_on_date(
            session,
            nio_invoice,
            Decimal("900.00"),
            EstadoRecibo.ACTIVO,
            datetime(2036, 3, 7, 9, 0, 0),
        )
        session.commit()

    rows = DashboardService(session_factory).get_billing_timeline(reference_date=datetime(2036, 5, 22))

    usd_rows = [row for row in rows if row["moneda"] == "USD"]
    nio_rows = [row for row in rows if row["moneda"] == "NIO"]
    assert len(usd_rows) == 12
    assert len(nio_rows) == 12
    assert [row["period_key"] for row in usd_rows][:2] == ["2035-06", "2035-07"]
    assert [row["period_key"] for row in usd_rows][-1] == "2036-05"

    usd_may = next(row for row in usd_rows if row["period_key"] == "2036-05")
    nio_april = next(row for row in nio_rows if row["period_key"] == "2036-04")
    nio_march = next(row for row in nio_rows if row["period_key"] == "2036-03")

    assert usd_may["facturado"] == "120.00"
    assert usd_may["pagado"] == "75.00"
    assert usd_may["facturas_count"] == 1
    assert usd_may["recibos_count"] == 1
    assert usd_may["facturado_display"] == "$ 120.00"
    assert usd_may["pagado_display"] == "$ 75.00"

    assert nio_april["facturado"] == "2400.00"
    assert nio_april["pagado"] == "0.00"
    assert nio_march["facturado"] == "0.00"
    assert nio_march["pagado"] == "900.00"
    assert nio_march["pagado_display"] == "C$ 900.00"


def test_dashboard_service_billing_timeline_ignores_canceled_documents(session_factory):
    with session_factory() as session:
        client = create_cliente(session, ruc="DASH-TL-CANCEL")
        canceled_invoice = _create_factura(
            session,
            client.id,
            "DASH-TL-CANCEL-INVOICE",
            Decimal("100.00"),
            estado=EstadoFactura.ANULADA,
        )
        active_invoice = _create_factura(
            session,
            client.id,
            "DASH-TL-ACTIVE-INVOICE",
            Decimal("200.00"),
        )
        canceled_invoice.fecha_emision = datetime(2037, 5, 8, 9, 0, 0)
        active_invoice.fecha_emision = datetime(2037, 5, 9, 9, 0, 0)
        _apply_payment_on_date(
            session,
            active_invoice,
            Decimal("50.00"),
            EstadoRecibo.ANULADO,
            datetime(2037, 5, 10, 9, 0, 0),
        )
        session.commit()

    rows = DashboardService(session_factory).get_billing_timeline(reference_date=datetime(2037, 5, 22))

    may = next(row for row in rows if row["moneda"] == "USD" and row["period_key"] == "2037-05")
    assert may["facturado"] == "200.00"
    assert may["pagado"] == "0.00"
    assert may["facturas_count"] == 1
    assert may["recibos_count"] == 0


def test_dashboard_service_billing_timeline_returns_empty_without_activity(session_factory):
    rows = DashboardService(session_factory).get_billing_timeline(reference_date=datetime(2040, 5, 22))

    activity_rows = [
        row for row in rows
        if row["facturado"] != "0.00" or row["pagado"] != "0.00"
    ]
    assert activity_rows == []


def test_dashboard_view_model_refresh_maps_service_kpis_to_metric_cards(qapp):
    class StubService:
        def get_kpis(self):
            return {
                "viajes_activos": 2,
                "circuitos_en_progreso": 3,
                "camiones_disponibles": 4,
                "camiones_en_viaje": 5,
                "cuentas_por_cobrar_clientes": 6,
                "facturacion_pendiente": 7,
                "facturas_atrasadas": 8,
                "fleet_status": {
                    "camiones_disponibles": 4,
                    "camiones_en_viaje": 5,
                    "camiones_mantenimiento": 1,
                    "camiones_baja": 0,
                    "camiones_vendidos": 0,
                    "camiones_agregados": 0,
                },
                "driver_status": {
                    "conductores_disponibles": 9,
                    "conductores_en_viaje": 10,
                    "conductores_instrucciones": 11,
                    "conductores_baja": 0,
                    "conductores_agregados": 0,
                },
                "summary": {
                    "circuitos_en_progreso": 3,
                },
                "finance": {
                    "facturacion_pendiente": 7,
                    "cuentas_por_cobrar_clientes": 6,
                    "facturas_atrasadas": 8,
                },
            }

    view_model = DashboardViewModel(StubService())
    emitted = {"metrics": 0, "busy": []}
    view_model.metricsChanged.connect(lambda: emitted.__setitem__("metrics", emitted["metrics"] + 1))
    view_model.busyChanged.connect(lambda value: emitted["busy"].append(value))

    assert view_model.refresh() is True

    metrics_by_key = {metric["key"]: metric for metric in view_model.metrics}
    assert metrics_by_key["viajes_activos"]["value"] == "2"
    assert metrics_by_key["facturacion_pendiente"]["value"] == "7"
    assert metrics_by_key["cuentas_por_cobrar_clientes"]["moduleId"] == "cliente"
    assert [metric["key"] for metric in view_model.metrics] == [
        "viajes_activos",
        "circuitos_en_progreso",
        "camiones_disponibles",
        "camiones_en_viaje",
        "cuentas_por_cobrar_clientes",
        "facturacion_pendiente",
        "facturas_atrasadas",
    ]
    assert [metric["key"] for metric in view_model.fleetStatusMetrics] == [
        "camiones_disponibles",
        "camiones_en_viaje",
        "camiones_mantenimiento",
        "camiones_baja",
        "camiones_vendidos",
        "camiones_agregados",
    ]
    assert view_model.fleetStatusMetrics[0]["value"] == 4
    assert view_model.fleetStatusMetrics[0]["moduleId"] == "camion"
    assert view_model.driverStatusMetrics[2]["key"] == "conductores_instrucciones"
    assert view_model.driverStatusMetrics[2]["value"] == 11
    assert view_model.summaryMetrics == [
        {
            "key": "circuitos_en_progreso",
            "title": "Circuitos abiertos",
            "value": "3",
            "caption": "",
            "accentTone": "primary",
            "monogram": "CI",
            "iconSource": "",
            "moduleId": "circuito",
            "target": "filtered_list",
            "filters": [{"field": "estado", "operator": "eq", "value": "ENPROGRESO"}],
        },
        {
            "key": "viajes_en_progreso",
            "title": "Viajes en progreso",
            "value": "0",
            "caption": "",
            "accentTone": "warning",
            "monogram": "VP",
            "iconSource": "",
            "moduleId": "viaje",
            "target": "filtered_list",
            "filters": [{"field": "estado", "operator": "eq", "value": "ENCURSO"}],
        },
    ]
    assert [metric["key"] for metric in view_model.financeMetrics] == [
        "facturacion_pendiente",
        "cuentas_por_cobrar_clientes",
        "facturas_atrasadas",
    ]
    assert view_model.financeMetrics[-1]["value"] == "8"
    assert view_model.financeMetrics[-1]["moduleId"] == "factura"
    assert view_model.financeMetrics[-1]["iconSource"] == ""
    assert view_model.financeMetrics[0]["target"] == "subpage"
    assert view_model.financeMetrics[0]["subpage"] == "unbilled_trips"
    assert view_model.financeMetrics[1]["subpage"] == "client_debt"
    assert "subpageContext" not in view_model.financeMetrics[1]
    assert view_model.financeMetrics[2]["target"] == "filtered_list"
    assert view_model.financeMetrics[2]["filters"] == [{"field": "estado", "operator": "eq", "value": "Atrasada"}]
    assert view_model.fleetStatusMetrics[0]["filters"] == [{"field": "estado", "operator": "eq", "value": "ACTIVO"}]
    assert emitted["metrics"] == 1
    assert emitted["busy"] == [True, False]
    assert view_model.error_message == ""


def test_dashboard_view_model_filters_status_metrics_by_visibility(qapp):
    class StubService:
        def get_kpis(self):
            return {
                "fleet_status": {
                    "camiones_disponibles": 4,
                    "camiones_en_viaje": 5,
                    "camiones_mantenimiento": 1,
                    "camiones_baja": 2,
                    "camiones_vendidos": 3,
                    "camiones_agregados": 6,
                },
                "driver_status": {
                    "conductores_disponibles": 9,
                    "conductores_en_viaje": 10,
                    "conductores_instrucciones": 11,
                    "conductores_baja": 12,
                    "conductores_agregados": 13,
                },
            }

    view_model = DashboardViewModel(StubService())
    assert view_model.refresh() is True

    assert view_model.setStatusMetricVisible("fleet", "camiones_agregados", False) is True
    assert [metric["key"] for metric in view_model.fleetStatusMetrics] == [
        "camiones_disponibles",
        "camiones_en_viaje",
        "camiones_mantenimiento",
        "camiones_baja",
        "camiones_vendidos",
    ]
    assert [metric["key"] for metric in view_model.driverStatusMetrics] == [
        "conductores_disponibles",
        "conductores_en_viaje",
        "conductores_instrucciones",
        "conductores_baja",
        "conductores_agregados",
    ]
    fleet_options = {option["key"]: option for option in view_model.fleetStatusVisibilityOptions}
    assert fleet_options["camiones_agregados"]["visible"] is False
    assert view_model.driverStatusVisibilityOptions[-1]["visible"] is True

    assert view_model.setStatusMetricVisible("fleet", "camiones_agregados", True) is True
    assert view_model.fleetStatusMetrics[-1]["key"] == "camiones_agregados"


def test_dashboard_view_model_hides_metric_cards_without_required_permissions(qapp):
    class StubService:
        def get_kpis(self):
            return {
                "viajes_activos": 2,
                "circuitos_en_progreso": 3,
                "camiones_disponibles": 4,
                "camiones_en_viaje": 5,
                "cuentas_por_cobrar_clientes": 6,
                "facturacion_pendiente": 7,
                "facturas_atrasadas": 8,
                "fleet_status": {
                    "camiones_disponibles": 4,
                    "camiones_en_viaje": 5,
                    "camiones_mantenimiento": 1,
                    "camiones_baja": 2,
                    "camiones_vendidos": 3,
                    "camiones_agregados": 6,
                },
                "driver_status": {
                    "conductores_disponibles": 9,
                    "conductores_en_viaje": 10,
                    "conductores_instrucciones": 11,
                    "conductores_baja": 12,
                    "conductores_agregados": 13,
                },
                "summary": {
                    "circuitos_en_progreso": 3,
                    "viajes_en_progreso": 2,
                },
                "finance": {
                    "facturacion_pendiente": 7,
                    "cuentas_por_cobrar_clientes": 6,
                    "facturas_atrasadas": 8,
                },
            }

    class StubAuthorization:
        def __init__(self, grants):
            self._grants = set(grants)

        def can(self, resource, action):
            return (str(resource), str(action)) in self._grants

    authorization = StubAuthorization(
        {
            ("viaje", "read"),
            ("circuito", "read"),
            ("camion", "read"),
            ("factura", "read"),
        }
    )
    view_model = DashboardViewModel(StubService(), authorization_service=authorization)

    assert view_model.refresh() is True

    assert [metric["key"] for metric in view_model.metrics] == [
        "viajes_activos",
        "circuitos_en_progreso",
        "camiones_disponibles",
        "camiones_en_viaje",
        "facturas_atrasadas",
    ]
    assert [metric["key"] for metric in view_model.fleetStatusMetrics] == [
        "camiones_disponibles",
        "camiones_en_viaje",
        "camiones_mantenimiento",
        "camiones_baja",
        "camiones_vendidos",
        "camiones_agregados",
    ]
    assert view_model.driverStatusMetrics == []
    assert [metric["key"] for metric in view_model.summaryMetrics] == [
        "circuitos_en_progreso",
        "viajes_en_progreso",
    ]
    assert [metric["key"] for metric in view_model.financeMetrics] == ["facturas_atrasadas"]


def test_dashboard_view_model_shows_composite_finance_cards_only_with_all_required_permissions(qapp):
    class StubService:
        def get_kpis(self):
            return {
                "finance": {
                    "facturacion_pendiente": 7,
                    "cuentas_por_cobrar_clientes": 6,
                    "facturas_atrasadas": 8,
                }
            }

    class StubAuthorization:
        def __init__(self, grants):
            self._grants = set(grants)

        def can(self, resource, action):
            return (str(resource), str(action)) in self._grants

    authorization = StubAuthorization(
        {
            ("viaje", "create"),
            ("factura", "read"),
            ("cliente", "read"),
            ("recibo", "read"),
        }
    )
    view_model = DashboardViewModel(StubService(), authorization_service=authorization)

    assert view_model.refresh() is True

    assert [metric["key"] for metric in view_model.financeMetrics] == [
        "facturacion_pendiente",
        "cuentas_por_cobrar_clientes",
        "facturas_atrasadas",
    ]


def test_dashboard_view_model_exposes_billing_timeline_rows_and_currencies(qapp):
    class StubService:
        def get_kpis(self):
            return {
                "finance": {
                    "facturacion_pendiente": 0,
                    "cuentas_por_cobrar_clientes": 0,
                    "facturas_atrasadas": 0,
                }
            }

        def get_billing_timeline(self, **kwargs):
            return [
                {
                    "period_key": "2026-04",
                    "period_label": "Abr 2026",
                    "moneda": "USD",
                    "facturado": "100.00",
                    "pagado": "80.00",
                    "facturado_display": "$ 100.00",
                    "pagado_display": "$ 80.00",
                    "facturas_count": 1,
                    "recibos_count": 1,
                    "max_value": "100.00",
                },
                {
                    "period_key": "2026-04",
                    "period_label": "Abr 2026",
                    "moneda": "NIO",
                    "facturado": "2500.00",
                    "pagado": "0.00",
                    "facturado_display": "C$ 2,500.00",
                    "pagado_display": "C$ 0.00",
                    "facturas_count": 1,
                    "recibos_count": 0,
                    "max_value": "2500.00",
                },
            ]

    view_model = DashboardViewModel(StubService())
    emitted = {"timeline": 0, "currency": [], "receipts": []}
    view_model.billingTimelineChanged.connect(lambda: emitted.__setitem__("timeline", emitted["timeline"] + 1))
    view_model.billingTimelineCurrencyChanged.connect(lambda value: emitted["currency"].append(value))
    view_model.billingTimelineReceiptsVisibilityChanged.connect(lambda value: emitted["receipts"].append(value))

    assert view_model.refresh() is True

    assert view_model.billingTimelineCurrencies == [
        {"key": "", "label": "Todas"},
        {"key": "USD", "label": "USD"},
        {"key": "NIO", "label": "NIO"},
    ]
    assert [row["moneda"] for row in view_model.billingTimelineRows] == ["USD", "NIO"]

    assert view_model.selectBillingTimelineCurrency("USD") is True
    assert [row["moneda"] for row in view_model.billingTimelineRows] == ["USD"]
    assert view_model.selectedBillingTimelineCurrency == "USD"
    assert emitted["currency"] == ["USD"]

    assert view_model.setBillingTimelineReceiptsVisible(True) is True
    assert view_model.showBillingTimelineReceipts is True
    assert emitted["receipts"] == [True]
    assert emitted["timeline"] >= 2


def test_dashboard_view_model_handles_billing_timeline_refresh_error(qapp):
    class BrokenTimelineService:
        def get_kpis(self):
            return {"finance": {}}

        def get_billing_timeline(self, **kwargs):
            raise RuntimeError("timeline unavailable")

    view_model = DashboardViewModel(BrokenTimelineService())

    assert view_model.refresh() is False
    assert view_model.billingTimelineRows == []
    assert view_model.billingTimelineCurrencies == [{"key": "", "label": "Todas"}]
    assert view_model.error_message == "timeline unavailable"


def test_dashboard_view_model_hides_billing_timeline_without_invoice_read_permission(qapp):
    class StubService:
        def __init__(self):
            self.timeline_calls = []

        def get_kpis(self):
            return {"finance": {}}

        def get_billing_timeline(self, **kwargs):
            self.timeline_calls.append(kwargs)
            return [{"moneda": "USD", "facturado": "100.00"}]

    class StubAuthorization:
        def can(self, resource, action):
            return False

    service = StubService()
    view_model = DashboardViewModel(service, authorization_service=StubAuthorization())

    assert view_model.refresh() is True

    assert view_model.canViewBillingTimeline is False
    assert view_model.canCompareBillingTimelineReceipts is False
    assert view_model.billingTimelineRows == []
    assert view_model.billingTimelineCurrencies == [{"key": "", "label": "Todas"}]
    assert service.timeline_calls == []


def test_dashboard_view_model_loads_billing_timeline_without_receipts_when_receipt_read_is_denied(qapp):
    class StubService:
        def __init__(self):
            self.timeline_calls = []

        def get_kpis(self):
            return {"finance": {}}

        def get_billing_timeline(self, **kwargs):
            self.timeline_calls.append(kwargs)
            return [
                {
                    "period_key": "2026-04",
                    "period_label": "Abr 2026",
                    "moneda": "USD",
                    "facturado": "100.00",
                    "pagado": "0.00",
                    "facturado_display": "$ 100.00",
                    "pagado_display": "$ 0.00",
                    "facturas_count": 1,
                    "recibos_count": 0,
                    "max_value": "100.00",
                }
            ]

    class StubAuthorization:
        def can(self, resource, action):
            return (str(resource), str(action)) == ("factura", "read")

    service = StubService()
    view_model = DashboardViewModel(service, authorization_service=StubAuthorization())

    assert view_model.refresh() is True

    assert view_model.canViewBillingTimeline is True
    assert view_model.canCompareBillingTimelineReceipts is False
    assert service.timeline_calls == [{"include_receipts": False}]
    assert view_model.billingTimelineRows[0]["pagado"] == "0.00"
    assert view_model.setBillingTimelineReceiptsVisible(True) is False
    assert view_model.showBillingTimelineReceipts is False


def test_dashboard_view_model_enables_billing_receipt_comparison_with_invoice_and_receipt_read(qapp):
    class StubService:
        def __init__(self):
            self.timeline_calls = []

        def get_kpis(self):
            return {"finance": {}}

        def get_billing_timeline(self, **kwargs):
            self.timeline_calls.append(kwargs)
            return [
                {
                    "period_key": "2026-04",
                    "period_label": "Abr 2026",
                    "moneda": "USD",
                    "facturado": "100.00",
                    "pagado": "80.00",
                    "facturado_display": "$ 100.00",
                    "pagado_display": "$ 80.00",
                    "facturas_count": 1,
                    "recibos_count": 1,
                    "max_value": "100.00",
                }
            ]

    class StubAuthorization:
        def __init__(self, grants):
            self._grants = set(grants)

        def can(self, resource, action):
            return (str(resource), str(action)) in self._grants

    service = StubService()
    view_model = DashboardViewModel(
        service,
        authorization_service=StubAuthorization({("factura", "read"), ("recibo", "read")}),
    )

    assert view_model.refresh() is True

    assert view_model.canViewBillingTimeline is True
    assert view_model.canCompareBillingTimelineReceipts is True
    assert service.timeline_calls == [{"include_receipts": True}]
    assert view_model.setBillingTimelineReceiptsVisible(True) is True
    assert view_model.showBillingTimelineReceipts is True


def test_dashboard_service_billing_timeline_can_skip_receipts(session_factory):
    with session_factory() as session:
        client = create_cliente(session, ruc="DASH-TL-NO-REC")
        invoice = _create_factura(
            session,
            client.id,
            "DASH-TL-NO-REC-001",
            Decimal("100.00"),
            moneda=Moneda.USD,
        )
        invoice.fecha_emision = datetime(2038, 5, 4, 9, 0, 0)
        _apply_payment_on_date(
            session,
            invoice,
            Decimal("80.00"),
            EstadoRecibo.ACTIVO,
            datetime(2038, 5, 20, 9, 0, 0),
        )
        session.commit()

    rows = DashboardService(session_factory).get_billing_timeline(
        reference_date=datetime(2038, 5, 22),
        include_receipts=False,
    )

    may = next(row for row in rows if row["moneda"] == "USD" and row["period_key"] == "2038-05")
    assert may["facturado"] == "100.00"
    assert may["pagado"] == "0.00"
    assert may["recibos_count"] == 0


def test_dashboard_view_model_preserves_configured_qrc_icon_sources(qapp, monkeypatch):
    class StubService:
        def get_kpis(self):
            return {"summary": {"viajes_en_progreso": 4}}

    monkeypatch.setattr(
        dashboard_module,
        "SUMMARY_DEFINITIONS",
        (
            dashboard_module.DashboardMetricDefinition(
                "viajes_en_progreso",
                "Viajes en progreso",
                "",
                "VP",
                "warning",
                "viaje",
                icon_source="qrc:/icons/dashboard/viaje.svg",
            ),
        ),
    )

    view_model = DashboardViewModel(StubService())

    assert view_model.refresh() is True
    assert view_model.summaryMetrics == [
        {
            "key": "viajes_en_progreso",
            "title": "Viajes en progreso",
            "value": "4",
            "caption": "",
            "accentTone": "warning",
            "monogram": "VP",
            "iconSource": "qrc:/icons/dashboard/viaje.svg",
            "moduleId": "viaje",
            "target": "list",
        },
    ]


def test_dashboard_view_model_surfaces_refresh_errors(qapp):
    class BrokenService:
        def get_kpis(self):
            raise RuntimeError("dashboard unavailable")

    view_model = DashboardViewModel(BrokenService())

    assert view_model.refresh() is False
    assert view_model.error_message == "dashboard unavailable"
    assert view_model.is_busy is False


def _seed_unique_viaje_dependencies(session, prefix: str) -> dict[str, int]:
    cliente = create_cliente(session, ruc=f"{prefix}-RUC")
    ruta = create_ruta(session)
    camion = create_camion(session, placa=f"{prefix}-CAMION", chasis=f"{prefix}-CAMION-CH")
    furgon = create_furgon(session, placa=f"{prefix}-FURGON", chasis=f"{prefix}-FURGON-CH")
    thermo = create_thermo(session, codigo=f"{prefix}-THERMO")
    conductor = create_conductor(
        session,
        nombre=prefix,
        apellido="Conductor",
        cedula=f"{prefix}-CEDULA",
        licencia=f"{prefix}-LICENCIA",
        pasaporte=f"{prefix}-PASAPORTE",
        telefono=f"{prefix}-TEL",
    )
    session.commit()
    return {
        "cliente_id": int(cliente.id),
        "ruta_id": int(ruta.id),
        "origen_id": int(ruta.origen_id),
        "destino_id": int(ruta.destino_id),
        "camion_id": int(camion.id),
        "furgon_id": int(furgon.id),
        "thermo_id": int(thermo.id),
        "conductor_id": int(conductor.id),
    }


def _create_factura(
    session,
    cliente_id: object,
    numero: str,
    total: Decimal,
    *,
    estado: EstadoFactura = EstadoFactura.PENDIENTE,
    moneda: Moneda = Moneda.USD,
) -> Factura:
    factura = Factura(
        numero_factura=numero,
        fecha_emision=datetime(2026, 1, 10, 8, 0, 0),
        cliente_id=cliente_id,
        dias_credito=10,
        moneda=moneda,
        _subtotal=total,
        _total=total,
        tasa_cambio=Decimal("1.0000"),
        estado=estado,
    )
    session.add(factura)
    session.flush()
    return factura


def _apply_payment(session, factura: Factura, amount: Decimal, estado: EstadoRecibo) -> None:
    recibo = Recibo(
        referencia=f"REC-{factura.numero_factura}",
        fecha_emision=datetime(2026, 1, 12, 8, 0, 0),
        cliente_id=factura.cliente_id,
        monto=amount,
        estado=estado,
        moneda=factura.moneda,
        tasa_cambio=Decimal("1.0000"),
    )
    session.add(recibo)
    session.flush()
    session.add(ReciboFactura(recibo_id=recibo.id, factura_id=factura.id, monto_pagado=amount))


def _apply_payment_on_date(
    session,
    factura: Factura,
    amount: Decimal,
    estado: EstadoRecibo,
    fecha_emision: datetime,
) -> None:
    recibo = Recibo(
        referencia=f"REC-{factura.numero_factura}-{fecha_emision:%Y%m%d}",
        fecha_emision=fecha_emision,
        cliente_id=factura.cliente_id,
        monto=amount,
        estado=estado,
        moneda=factura.moneda,
        tasa_cambio=Decimal("1.0000"),
    )
    session.add(recibo)
    session.flush()
    session.add(ReciboFactura(recibo_id=recibo.id, factura_id=factura.id, monto_pagado=amount))
