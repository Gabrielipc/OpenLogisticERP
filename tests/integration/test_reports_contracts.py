from __future__ import annotations

from datetime import datetime

import pytest

from openlogistic_erp.domain.reports import (
    ReportColumn,
    ReportFilterDefinition,
    ReportFilterOption,
    ReportFormat,
    ReportPayload,
    ReportRequest,
    ReportTable,
)


def test_report_payload_to_map_is_qml_safe():
    payload = ReportPayload(
        title="Viajes",
        generated_at=datetime(2026, 5, 6, 12, 30),
        tables=(
            ReportTable(
                key="summary",
                title="Resumen",
                columns=(ReportColumn(key="total", label="Total", format="int"),),
                rows=({"total": 3},),
            ),
        ),
        currencies=({"key": "USD", "label": "USD"},),
    )

    assert payload.to_map() == {
        "title": "Viajes",
        "message": "",
        "generated_at": "2026-05-06T12:30:00",
        "tables": [
            {
                "key": "summary",
                "title": "Resumen",
                "columns": [{"key": "total", "label": "Total", "format": "int", "decimals": 2}],
                "rows": [{"total": 3}],
                "currency_field": "",
            }
        ],
        "currencies": [{"key": "USD", "label": "USD"}],
    }


def test_filter_definition_to_map_includes_options():
    definition = ReportFilterDefinition(
        key="estado_viaje",
        label="Estado",
        type="select",
        required=False,
        options=(ReportFilterOption(value="ACTIVO", label="Activo"),),
    )

    assert definition.to_map()["options"] == [{"value": "ACTIVO", "label": "Activo"}]


def test_report_request_normalizes_format_and_params():
    request = ReportRequest(report_key=" viajes_por_conductor ", params={"a": 1}, export_format=ReportFormat.PDF)

    assert request.report_key == "viajes_por_conductor"
    assert request.params == {"a": 1}
    assert request.export_format is ReportFormat.PDF


def test_report_payload_snapshots_caller_owned_rows_and_currencies():
    row = {"total": 3}
    currency = {"key": "USD", "label": "USD"}
    payload = ReportPayload(
        title="Viajes",
        generated_at=datetime(2026, 5, 6, 12, 30),
        tables=(
            ReportTable(
                key="summary",
                title="Resumen",
                rows=(row,),
            ),
        ),
        currencies=(currency,),
    )

    row["total"] = 99
    currency["label"] = "US Dollar"

    mapped = payload.to_map()
    assert mapped["tables"][0]["rows"] == [{"total": 3}]
    assert mapped["currencies"] == [{"key": "USD", "label": "USD"}]


def test_report_request_params_reject_in_place_mutation():
    request = ReportRequest(report_key="viajes", params={"estado": "ACTIVO"})

    with pytest.raises(TypeError):
        request.params["estado"] = "CERRADO"


def test_report_request_coerces_string_export_format():
    request = ReportRequest(report_key="viajes", export_format=" PDF ")

    assert request.export_format is ReportFormat.PDF


def test_report_request_rejects_invalid_export_format():
    with pytest.raises(ValueError):
        ReportRequest(report_key="viajes", export_format="docx")
