from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from openlogistic_erp.application.reports import (
    ReportCatalogService,
    ReportGenerationService,
    ReportNotFoundError,
    ReportValidationError,
    build_default_report_definitions,
)
from openlogistic_erp.domain.reports import ReportFilterOption, ReportPayload, ReportRequest


class FakeReader:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        self.calls.append(params)
        return ReportPayload(title="Fake", generated_at=datetime(2026, 5, 6, 12, 0))


class FakeOptionProvider:
    def conductores(self) -> list[ReportFilterOption]:
        return [ReportFilterOption(value=1, label="Ada")]


def test_default_report_definitions_have_expected_keys():
    definitions = build_default_report_definitions()

    assert list(definitions) == [
        "viajes_por_conductor",
        "cuentas_por_cobrar_aging",
        "facturacion_por_cliente",
        "estado_cuenta_cliente",
    ]


def test_catalog_service_returns_qml_safe_maps_with_filter_order_and_options():
    service = ReportCatalogService(
        build_default_report_definitions(),
        option_provider=FakeOptionProvider(),
    )

    mapped = service.list_definitions()

    assert mapped[0]["key"] == "viajes_por_conductor"
    assert mapped[0]["filters"][0]["key"] == "rango_fechas"
    assert service.options_for("conductores") == [{"value": 1, "label": "Ada"}]


def test_generation_service_dispatches_registered_reader_with_mutable_param_copy():
    reader = FakeReader()
    service = ReportGenerationService(
        build_default_report_definitions(),
        readers={"viajes_por_conductor": reader},
    )
    request = ReportRequest(
        report_key="viajes_por_conductor",
        params={"rango_fechas": ["2026-05-01", "2026-05-31"]},
    )

    payload = service.generate(request)

    assert payload.title == "Fake"
    assert reader.calls == [{"rango_fechas": ["2026-05-01", "2026-05-31"]}]
    assert reader.calls[0] is not request.params


def test_generation_service_raises_for_unknown_report():
    service = ReportGenerationService(build_default_report_definitions(), readers={})

    with pytest.raises(ReportNotFoundError):
        service.generate(ReportRequest(report_key="desconocido"))


def test_generation_service_raises_for_missing_required_param():
    service = ReportGenerationService(
        build_default_report_definitions(),
        readers={"estado_cuenta_cliente": FakeReader()},
    )

    with pytest.raises(ReportValidationError):
        service.generate(ReportRequest(report_key="estado_cuenta_cliente", params={}))


@pytest.mark.parametrize(
    "rango_fechas",
    [
        ["", ""],
        [None, None],
        ["2026-05-01", ""],
        ["", "2026-05-31"],
    ],
)
def test_generation_service_raises_for_empty_required_date_range_endpoints(rango_fechas):
    service = ReportGenerationService(
        build_default_report_definitions(),
        readers={"viajes_por_conductor": FakeReader()},
    )

    with pytest.raises(ReportValidationError):
        service.generate(
            ReportRequest(
                report_key="viajes_por_conductor",
                params={"rango_fechas": rango_fechas},
            )
        )
