from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from openlogistic_erp.domain.reports import ReportFilterOption
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    EstadoFactura,
    EstadoRecibo,
    EstadoViaje,
    Factura,
    Moneda,
    Recibo,
)
from openlogistic_erp.infrastructure.persistence.reports.base import ReportReaderBase
from openlogistic_erp.infrastructure.persistence.reports.cuentas_por_cobrar import (
    CuentasPorCobrarAgingReportReader,
)
from openlogistic_erp.infrastructure.persistence.reports.estado_cuenta_cliente import (
    EstadoCuentaClienteReportReader,
)
from openlogistic_erp.infrastructure.persistence.reports.facturacion_por_cliente import (
    FacturacionPorClienteReportReader,
)
from openlogistic_erp.infrastructure.persistence.reports.options import ReportOptionsReader
from openlogistic_erp.infrastructure.persistence.reports.viajes_por_conductor import (
    ViajesPorConductorReportReader,
)
from tests.builders.modelo_seed import (
    build_factura_payload,
    build_viaje_export_payload,
    create_cliente,
    create_impuesto,
    seed_viaje_dependencies,
)


def test_reader_base_parses_date_range_end_of_day():
    start, end = ReportReaderBase.parse_date_range(("2026-05-01", "2026-05-06"))

    assert start == datetime(2026, 5, 1)
    assert end == datetime(2026, 5, 6, 23, 59, 59, 999999)


def test_reader_base_swaps_inverted_range():
    start, end = ReportReaderBase.parse_date_range(("2026-05-06", "2026-05-01"))

    assert start == datetime(2026, 5, 1)
    assert end == datetime(2026, 5, 6, 23, 59, 59, 999999)


def test_reader_base_parse_int_returns_none_for_empty_values():
    assert ReportReaderBase.parse_int("") is None
    assert ReportReaderBase.parse_int(None) is None
    assert ReportReaderBase.parse_int("42") == 42


def test_reader_base_parse_date_returns_none_for_invalid_values():
    assert ReportReaderBase.parse_date("") is None
    assert ReportReaderBase.parse_date(None) is None
    assert ReportReaderBase.parse_date("06-05-2026") is None
    assert ReportReaderBase.parse_date(("2026-05-06",)) is None


def test_reader_base_nombre_completo_falls_back_for_blank_names():
    assert ReportReaderBase.nombre_completo("", "") == "(Sin nombre)"
    assert ReportReaderBase.nombre_completo("Ada", "") == "Ada"
    assert ReportReaderBase.nombre_completo("", "Lovelace") == "Lovelace"
    assert ReportReaderBase.nombre_completo("Ada", "Lovelace") == "Ada Lovelace"


def test_options_reader_returns_static_enum_options_without_session():
    reader = ReportOptionsReader(session_factory=lambda: None)

    assert reader.estado_viaje() == [
        ReportFilterOption(value=estado.value, label=estado.value) for estado in EstadoViaje
    ]
    assert reader.estado_factura() == [
        ReportFilterOption(value=estado.value, label=estado.value) for estado in EstadoFactura
    ]
    assert reader.bucket_scheme() == [
        ReportFilterOption(value="30_60_90", label="0-30 / 31-60 / 61-90 / 91+ dias")
    ]


def test_options_reader_query_backed_options_return_empty_on_query_errors():
    def broken_session_factory():
        raise RuntimeError("database unavailable")

    reader = ReportOptionsReader(session_factory=broken_session_factory)

    assert reader.conductores() == []
    assert reader.clientes() == []


class FakeQuery:
    def __init__(self, records):
        self._records = records

    def order_by(self, *_args):
        return self

    def all(self):
        return self._records


class FakeSession:
    def __init__(self, records):
        self._records = records

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, _model):
        return FakeQuery(self._records)


def test_options_reader_conductores_composes_full_name_with_fallback():
    records = [
        SimpleNamespace(id=1, nombre="Ada", apellido="Lovelace"),
        SimpleNamespace(id=2, nombre="", apellido=""),
    ]
    reader = ReportOptionsReader(session_factory=lambda: FakeSession(records))

    assert reader.conductores() == [
        ReportFilterOption(value=1, label="Ada Lovelace"),
        ReportFilterOption(value=2, label="(Sin nombre)"),
    ]


def test_options_reader_clientes_uses_nombre_label():
    records = [SimpleNamespace(id=7, nombre="ACME")]
    reader = ReportOptionsReader(session_factory=lambda: FakeSession(records))

    assert reader.clientes() == [ReportFilterOption(value=7, label="ACME")]


def test_viajes_por_conductor_reader_returns_summary(session_factory, modelo_workflow):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = build_viaje_export_payload(
        deps,
        viaje={
            "referencia": "REP-VIAJE-001",
            "fecha_posicionamiento": datetime(2026, 5, 2, 8, 0, 0),
        },
        circuito={"fecha_inicio": datetime(2026, 5, 2, 7, 0, 0)},
    )
    modelo_workflow.viaje.create(payload)

    reader = ViajesPorConductorReportReader(session_factory)
    result = reader.generate({"rango_fechas": ("2026-05-01", "2026-05-31"), "incluir_detalle": True})

    assert result.tables[0].key == "resumen_conductor"
    assert [column.key for column in result.tables[0].columns][:3] == [
        "conductor",
        "total_viajes",
        "dias_ocupado",
    ]
    assert any(row["total_viajes"] >= 1 for row in result.tables[0].rows)


def test_viajes_por_conductor_includes_open_trip_started_before_range(session_factory, modelo_workflow):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = build_viaje_export_payload(
        deps,
        viaje={
            "referencia": "REP-VIAJE-OPEN",
            "fecha_posicionamiento": datetime(2026, 4, 28, 8, 0, 0),
        },
        circuito={"fecha_inicio": datetime(2026, 4, 28, 7, 0, 0)},
    )
    modelo_workflow.viaje.create(payload)

    reader = ViajesPorConductorReportReader(session_factory)
    result = reader.generate(
        {
            "rango_fechas": ("2026-05-01", "2026-05-03"),
            "conductor_id": deps["conductor_id"],
        }
    )

    rows = result.tables[0].rows
    assert len(rows) == 1
    assert rows[0]["conductor"] == "Juan Perez"
    assert rows[0]["total_viajes"] == 1
    assert rows[0]["dias_ocupado"] == 3


def test_cuentas_por_cobrar_reader_returns_aging_summary(session_factory, modelo_workflow):
    cliente_id = _seed_unpaid_factura(session_factory, modelo_workflow, "REP-CXC")

    reader = CuentasPorCobrarAgingReportReader(session_factory)
    result = reader.generate({"fecha_corte": "2026-05-06", "cliente_id": cliente_id})

    assert result.tables[0].key == "aging_resumen"
    assert [column.key for column in result.tables[0].columns][:6] == [
        "cliente",
        "saldo_total",
        "1_30",
        "31_60",
        "61_90",
        "91_plus",
    ]
    assert result.tables[0].rows[0]["saldo_total"] > 0


def test_cuentas_por_cobrar_includes_invoices_issued_later_on_cutoff_date(session_factory, modelo_workflow):
    cliente_id = _seed_unpaid_factura(
        session_factory,
        modelo_workflow,
        "REP-CXC-CUT-FAC",
        fecha_emision=datetime(2026, 5, 6, 15, 30, 0),
        total="1000.00",
    )

    reader = CuentasPorCobrarAgingReportReader(session_factory)
    result = reader.generate({"fecha_corte": "2026-05-06", "cliente_id": cliente_id})

    assert result.tables[0].rows[0]["saldo_total"] == 1000.0
    assert result.tables[1].rows[0]["numero"] == "REP-CXC-CUT-FAC-001"


def test_cuentas_por_cobrar_applies_receipts_later_on_cutoff_date(session_factory, modelo_workflow):
    cliente_id = _seed_unpaid_factura(
        session_factory,
        modelo_workflow,
        "REP-CXC-CUT-REC",
        fecha_emision=datetime(2026, 5, 1, 9, 0, 0),
        total="1000.00",
    )
    factura_id = _factura_id_by_number(session_factory, "REP-CXC-CUT-REC-001")
    _seed_recibo(
        modelo_workflow,
        factura_id=factura_id,
        cliente_id=cliente_id,
        referencia="REP-CXC-CUT-REC-ACT",
        fecha_emision=datetime(2026, 5, 6, 18, 15, 0),
        monto="200.00",
    )
    anulled_recibo_id = _seed_recibo(
        modelo_workflow,
        factura_id=factura_id,
        cliente_id=cliente_id,
        referencia="REP-CXC-CUT-REC-ANU",
        fecha_emision=datetime(2026, 5, 5, 10, 0, 0),
        monto="300.00",
    )
    with session_factory() as session:
        recibo = session.get(Recibo, anulled_recibo_id)
        assert recibo is not None
        recibo.estado = EstadoRecibo.ANULADO
        session.commit()

    reader = CuentasPorCobrarAgingReportReader(session_factory)
    result = reader.generate({"fecha_corte": "2026-05-06", "cliente_id": cliente_id})

    assert result.tables[0].rows[0]["saldo_total"] == 800.0
    assert result.tables[1].rows[0]["saldo"] == 800.0


def test_cuentas_por_cobrar_rejects_malformed_required_fecha_corte(session_factory):
    reader = CuentasPorCobrarAgingReportReader(session_factory)

    with pytest.raises(ValueError, match="fecha de corte"):
        reader.generate({"fecha_corte": "06-05-2026"})


def test_facturacion_por_cliente_reader_returns_customer_totals(session_factory, modelo_workflow):
    cliente_id = _seed_unpaid_factura(session_factory, modelo_workflow, "REP-FAC")

    reader = FacturacionPorClienteReportReader(session_factory)
    result = reader.generate(
        {
            "rango_fechas": ("2026-01-01", "2026-01-31"),
            "cliente_id": cliente_id,
            "incluir_detalle": True,
        }
    )

    assert result.tables[0].key == "facturacion_cliente"
    assert [column.key for column in result.tables[0].columns][:4] == [
        "cliente",
        "total_facturado",
        "total_pagado",
        "saldo",
    ]
    assert result.tables[0].rows[0]["total_facturado"] > 0


def test_estado_cuenta_cliente_reader_returns_summary_and_invoices(session_factory, modelo_workflow):
    cliente_id = _seed_unpaid_factura(session_factory, modelo_workflow, "REP-EST")

    reader = EstadoCuentaClienteReportReader(session_factory)
    result = reader.generate({"cliente_id": cliente_id, "rango_fechas": ("2026-01-01", "2026-01-31")})

    assert result.tables[0].key == "estado_cuenta_resumen"
    assert result.tables[1].key == "estado_cuenta_facturas"


def test_estado_cuenta_cliente_payment_rows_use_invoice_currency_for_applied_amount(
    session_factory,
    modelo_workflow,
):
    cliente_id = _seed_unpaid_factura(
        session_factory,
        modelo_workflow,
        "REP-EST-CROSS",
        moneda=Moneda.USD,
        tasa_cambio="36.5000",
        total="1000.00",
    )
    factura_id = _factura_id_by_number(session_factory, "REP-EST-CROSS-001")
    _seed_recibo(
        modelo_workflow,
        factura_id=factura_id,
        cliente_id=cliente_id,
        referencia="REP-EST-CROSS-REC",
        fecha_emision=datetime(2026, 1, 25, 11, 0, 0),
        monto="36500.00",
        moneda=Moneda.NIO,
        tasa_cambio="36.5000",
        monto_factura="1000.00",
    )

    reader = EstadoCuentaClienteReportReader(session_factory)
    result = reader.generate({"cliente_id": cliente_id, "rango_fechas": ("2026-01-01", "2026-01-31")})

    pagos_table = next(table for table in result.tables if table.key == "estado_cuenta_pagos")
    assert pagos_table.rows[0]["monto"] == 1000.0
    assert pagos_table.rows[0]["moneda"] == "USD"
    assert pagos_table.rows[0]["moneda_key"] == "USD"


def test_estado_cuenta_cliente_range_excludes_later_payments_from_invoice_totals(
    session_factory,
    modelo_workflow,
):
    cliente_id = _seed_unpaid_factura(
        session_factory,
        modelo_workflow,
        "REP-EST-CUT",
        fecha_emision=datetime(2026, 1, 20, 10, 0, 0),
        total="1000.00",
    )
    factura_id = _factura_id_by_number(session_factory, "REP-EST-CUT-001")
    _seed_recibo(
        modelo_workflow,
        factura_id=factura_id,
        cliente_id=cliente_id,
        referencia="REP-EST-CUT-FEB",
        fecha_emision=datetime(2026, 2, 5, 10, 0, 0),
        monto="250.00",
    )

    reader = EstadoCuentaClienteReportReader(session_factory)
    result = reader.generate({"cliente_id": cliente_id, "rango_fechas": ("2026-01-01", "2026-01-31")})

    resumen_row = result.tables[0].rows[0]
    factura_row = result.tables[1].rows[0]
    assert resumen_row["total_facturado"] == 1000.0
    assert resumen_row["total_pagado"] == 0.0
    assert resumen_row["saldo"] == 1000.0
    assert factura_row["pagado"] == 0.0
    assert factura_row["saldo"] == 1000.0
    assert factura_row["ultimo_pago"] is None
    assert all(table.key != "estado_cuenta_pagos" for table in result.tables)


@pytest.mark.parametrize(
    "rango_fechas",
    [
        ("31-01-2026", "2026-01-31"),
        ("2026-01-01", "31-01-2026"),
    ],
)
def test_estado_cuenta_cliente_rejects_malformed_optional_rango_fechas_endpoint(
    session_factory,
    rango_fechas,
):
    reader = EstadoCuentaClienteReportReader(session_factory)

    with pytest.raises(ValueError, match="rango de fechas"):
        reader.generate({"cliente_id": 1, "rango_fechas": rango_fechas})


def test_viajes_por_conductor_rejects_malformed_required_rango_fechas_endpoint(session_factory):
    reader = ViajesPorConductorReportReader(session_factory)

    with pytest.raises(ValueError, match="rango de fechas"):
        reader.generate({"rango_fechas": ("2026-05-01", "31-05-2026")})


def _seed_unpaid_factura(
    session_factory,
    modelo_workflow,
    prefix: str,
    *,
    fecha_emision: datetime = datetime(2026, 1, 20, 10, 0, 0),
    moneda: Moneda = Moneda.NIO,
    tasa_cambio: str = "1.0000",
    total: str = "1000.00",
) -> int:
    with session_factory() as session:
        cliente = create_cliente(session, ruc=f"{prefix}-RUC")
        impuesto = create_impuesto(session, codigo=f"{prefix}-IVA")
        session.commit()
        cliente_id = int(cliente.id)
        impuesto_id = int(impuesto.id)

    payload = build_factura_payload(cliente_id, [impuesto_id])
    payload["factura"]["numero_factura"] = f"{prefix}-001"
    payload["factura"]["fecha_emision"] = fecha_emision
    payload["factura"]["moneda"] = moneda
    payload["factura"]["tasa_cambio"] = Decimal(tasa_cambio)
    factura = modelo_workflow.factura.create(payload)

    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        assert factura_row is not None
        factura_row._subtotal = Decimal(total)
        factura_row._total = Decimal(total)
        session.commit()

    return cliente_id


def _factura_id_by_number(session_factory, numero_factura: str) -> int:
    with session_factory() as session:
        factura = session.query(Factura).filter(Factura.numero_factura == numero_factura).one()
        return int(factura.id)


def _seed_recibo(
    modelo_workflow,
    *,
    factura_id: int,
    cliente_id: int,
    referencia: str,
    fecha_emision: datetime,
    monto: str,
    moneda: Moneda = Moneda.NIO,
    tasa_cambio: str = "1.0000",
    monto_factura: str | None = None,
) -> int:
    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": referencia,
                "fecha_emision": fecha_emision,
                "cliente_id": cliente_id,
                "monto": Decimal(monto),
                "moneda": moneda,
                "tasa_cambio": Decimal(tasa_cambio),
            },
            "facturas": [{"factura_id": factura_id, "monto": Decimal(monto_factura or monto)}],
        }
    )
    return int(recibo["id"])
