from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openlogistic_erp.application.reports import (
    ReportCatalogService,
    ReportDefinition,
    ReportExportService,
    ReportGenerationService,
)
from openlogistic_erp.domain.reports import ReportColumn, ReportFormat, ReportPayload, ReportTable
from openlogistic_erp.presentation.qt import Qt
from openlogistic_erp.presentation.reports import ReportTableModel, ReportsModuleViewModel


class FakeReader:
    def __init__(self, payload: ReportPayload | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._payload = payload

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        self.calls.append(dict(params))
        return self._payload or sample_payload()


class FakeExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[ReportPayload, str, str]] = []

    def export(self, payload: ReportPayload, target_path: str | Path, currency_key: str = "") -> None:
        self.calls.append((payload, str(target_path), currency_key))


def sample_payload() -> ReportPayload:
    return ReportPayload(
        title="Reporte fake",
        generated_at=datetime(2026, 5, 6, 10, 30),
        tables=(
            ReportTable(
                key="summary",
                title="Resumen",
                columns=(
                    ReportColumn("viajes", "Viajes", "int"),
                    ReportColumn("total", "Total", "currency", decimals=2),
                ),
                rows=({"viajes": 3, "total": 1234.5},),
            ),
        ),
        currencies=({"key": "USD", "label": "USD"}, {"key": "NIO", "label": "Cordoba"}),
    )


def build_view_model() -> tuple[ReportsModuleViewModel, FakeReader, FakeExporter, FakeExporter]:
    definitions = {
        "fake": ReportDefinition(
            key="fake",
            title="Fake",
            summary="Reporte fake",
            filters=(
                {
                    "key": "cliente_id",
                    "label": "Cliente",
                    "type": "select",
                    "option_source": "clientes",
                },
            ),
        )
    }
    reader = FakeReader()
    pdf_exporter = FakeExporter()
    xlsx_exporter = FakeExporter()
    view_model = ReportsModuleViewModel(
        catalog_service=ReportCatalogService(
            definitions,
            option_provider={"clientes": [{"value": 1, "label": "Acme"}]},
        ),
        generation_service=ReportGenerationService(definitions, {"fake": reader}),
        export_service=ReportExportService(
            {
                ReportFormat.PDF: pdf_exporter,
                ReportFormat.XLSX: xlsx_exporter,
            }
        ),
    )
    return view_model, reader, pdf_exporter, xlsx_exporter


def build_multi_report_view_model() -> tuple[ReportsModuleViewModel, FakeReader, FakeReader, FakeExporter]:
    definitions = {
        "fake": ReportDefinition(key="fake", title="Fake", summary="Reporte fake", filters=()),
        "other": ReportDefinition(key="other", title="Other", summary="Otro reporte", filters=()),
    }
    fake_reader = FakeReader()
    other_reader = FakeReader(
        ReportPayload(
            title="Otro reporte",
            generated_at=datetime(2026, 5, 6, 11, 0),
        )
    )
    pdf_exporter = FakeExporter()
    view_model = ReportsModuleViewModel(
        catalog_service=ReportCatalogService(definitions),
        generation_service=ReportGenerationService(definitions, {"fake": fake_reader, "other": other_reader}),
        export_service=ReportExportService({ReportFormat.PDF: pdf_exporter}),
    )
    return view_model, fake_reader, other_reader, pdf_exporter


def currency_payload() -> ReportPayload:
    return ReportPayload(
        title="Reporte monedas",
        generated_at=datetime(2026, 5, 6, 12, 0),
        tables=(
            ReportTable(
                key="detalle",
                title="Detalle",
                currency_field="moneda",
                columns=(
                    ReportColumn("cliente", "Cliente"),
                    ReportColumn("moneda", "Moneda"),
                    ReportColumn("monto", "Monto", "currency", decimals=2),
                ),
                rows=(
                    {"cliente": "Acme", "moneda": "USD", "monto": 10},
                    {"cliente": "Beta", "moneda": "NIO", "monto": 365},
                    {"cliente": "Delta", "moneda": "USD", "monto": 20},
                ),
            ),
        ),
        currencies=({"key": "USD", "label": "USD"}, {"key": "NIO", "label": "Cordoba"}),
    )


def test_reports_view_model_selects_report_generates_payload_map_and_exports(qapp, tmp_path):
    del qapp
    view_model, reader, pdf_exporter, xlsx_exporter = build_view_model()

    view_model.select_report("fake")
    generated = view_model.generate({"cliente_id": 1})
    pdf_path = tmp_path / "fake.pdf"
    xlsx_path = tmp_path / "fake.xlsx"

    assert generated is True
    assert reader.calls == [{"cliente_id": 1}]
    assert view_model.error_message == ""
    assert view_model.selected_report_key == "fake"
    assert view_model.selected_report["key"] == "fake"
    assert view_model.filters[0]["key"] == "cliente_id"
    assert view_model.options_for("clientes") == [{"value": 1, "label": "Acme"}]
    assert view_model.payload["title"] == "Reporte fake"
    assert view_model.tables[0]["key"] == "summary"
    assert view_model.currencies == [
        {"key": "", "label": "Todas"},
        {"key": "USD", "label": "USD"},
        {"key": "NIO", "label": "Cordoba"},
    ]
    assert view_model.selected_currency_key == ""
    assert view_model.active_table_model.display_data(0, 0) == "3"
    assert view_model.export_pdf(str(pdf_path)) is True
    assert view_model.export_xlsx(str(xlsx_path)) is True
    assert pdf_exporter.calls == [(view_model.latest_payload, str(pdf_path), "")]
    assert xlsx_exporter.calls == [(view_model.latest_payload, str(xlsx_path), "")]


def test_reports_view_model_materializes_filter_options_before_notifying_qml(qapp):
    del qapp
    view_model, _reader, _pdf_exporter, _xlsx_exporter = build_view_model()

    view_model.select_report("fake")

    assert view_model.filters[0]["options"] == [{"value": 1, "label": "Acme"}]


def test_report_table_model_exposes_roles_rows_columns_and_formatted_display(qapp):
    del qapp
    table = sample_payload().tables[0]
    model = ReportTableModel()

    model.set_report_table(table)

    assert model.rowCount() == 1
    assert model.columnCount() == 2
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Viajes"
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "3"
    assert model.data(model.index(0, 1), Qt.ItemDataRole.DisplayRole) == "1,234.50"
    assert model.data(model.index(0, 0), model._ROW_DATA_ROLE) == {"viajes": 3, "total": 1234.5}
    assert model.data(model.index(0, 1), model._COLUMN_KEY_ROLE) == "total"
    assert model.display_data(0, 1) == "1,234.50"
    assert model.row_data(0) == {"viajes": 3, "total": 1234.5}
    assert model.column_data(1) == {
        "key": "total",
        "label": "Total",
        "format": "currency",
        "decimals": 2,
    }


def test_reports_view_model_clears_generated_payload_when_report_changes(qapp, tmp_path):
    del qapp
    view_model, fake_reader, other_reader, pdf_exporter = build_multi_report_view_model()

    view_model.select_report("fake")
    assert view_model.generate({}) is True

    view_model.select_report("other")
    exported = view_model.export_pdf(str(tmp_path / "stale.pdf"))

    assert exported is False
    assert fake_reader.calls == [{}]
    assert other_reader.calls == []
    assert pdf_exporter.calls == []
    assert view_model.latest_payload is None
    assert view_model.payload == {}
    assert view_model.error_message == "No hay reporte generado para exportar"


def test_reports_view_model_filters_active_table_when_currency_changes(qapp):
    del qapp
    definitions = {"fake": ReportDefinition(key="fake", title="Fake", summary="Reporte fake", filters=())}
    reader = FakeReader(currency_payload())
    view_model = ReportsModuleViewModel(
        catalog_service=ReportCatalogService(definitions),
        generation_service=ReportGenerationService(definitions, {"fake": reader}),
        export_service=ReportExportService({}),
    )

    view_model.select_report("fake")
    assert view_model.generate({}) is True

    assert view_model.selected_currency_key == ""
    assert view_model.active_table_model.rowCount() == 3
    assert view_model.active_table_model.display_data(0, 0) == "Acme"
    assert view_model.active_table_model.display_data(1, 0) == "Beta"
    assert view_model.active_table_model.display_data(2, 0) == "Delta"

    view_model.select_currency("NIO")

    assert view_model.active_table_model.rowCount() == 1
    assert view_model.active_table_model.display_data(0, 0) == "Beta"
    assert view_model.active_table_model.display_data(0, 2) == "C$ 365.00"


def test_reports_view_model_adds_all_currency_option_and_defaults_to_all(qapp, tmp_path):
    del qapp
    definitions = {"fake": ReportDefinition(key="fake", title="Fake", summary="Reporte fake", filters=())}
    reader = FakeReader(currency_payload())
    pdf_exporter = FakeExporter()
    view_model = ReportsModuleViewModel(
        catalog_service=ReportCatalogService(definitions),
        generation_service=ReportGenerationService(definitions, {"fake": reader}),
        export_service=ReportExportService({ReportFormat.PDF: pdf_exporter}),
    )

    view_model.select_report("fake")
    assert view_model.generate({}) is True

    assert view_model.currencies == [
        {"key": "", "label": "Todas"},
        {"key": "USD", "label": "USD"},
        {"key": "NIO", "label": "Cordoba"},
    ]
    assert view_model.selected_currency_key == ""
    assert view_model.active_table_model.rowCount() == 3

    pdf_path = tmp_path / "all.pdf"
    assert view_model.export_pdf(str(pdf_path)) is True
    assert pdf_exporter.calls == [(view_model.latest_payload, str(pdf_path), "")]


def test_report_table_model_formats_currency_values_with_row_currency(qapp):
    del qapp
    model = ReportTableModel()

    model.set_report_table(currency_payload().tables[0])

    assert model.display_data(0, 2) == "$ 10.00"
    assert model.display_data(1, 2) == "C$ 365.00"


def test_report_table_model_builds_tsv_for_display_range(qapp):
    del qapp
    model = ReportTableModel()
    model.set_report_table(
        ReportTable(
            key="detalle",
            title="Detalle",
            columns=(
                ReportColumn("cliente", "Cliente"),
                ReportColumn("nota", "Nota"),
                ReportColumn("monto", "Monto", "currency", decimals=2),
            ),
            rows=(
                {"cliente": "Acme", "nota": "Linea\tuno", "monto": 10},
                {"cliente": "Beta", "nota": "Linea\ndos", "monto": 20},
            ),
        )
    )

    assert model.display_range_as_tsv(1, 2, 0, 1) == "Linea uno\t10.00\nLinea dos\t20.00"


def test_report_table_model_toggles_sort_by_column_preserving_raw_row_values(qapp):
    del qapp
    model = ReportTableModel()
    model.set_report_table(
        ReportTable(
            key="detalle",
            title="Detalle",
            columns=(
                ReportColumn("cliente", "Cliente"),
                ReportColumn("monto", "Monto", "currency", decimals=2),
            ),
            rows=(
                {"cliente": "Beta", "monto": 30},
                {"cliente": "Acme", "monto": 10},
                {"cliente": "Delta", "monto": 20},
            ),
        )
    )

    assert model.sort_field == ""
    assert model.sort_direction == ""

    model.toggle_sort("cliente")

    assert model.sort_field == "cliente"
    assert model.sort_direction == "asc"
    assert [model.display_data(row, 0) for row in range(model.rowCount())] == ["Acme", "Beta", "Delta"]

    model.toggle_sort("cliente")

    assert model.sort_direction == "desc"
    assert [model.display_data(row, 0) for row in range(model.rowCount())] == ["Delta", "Beta", "Acme"]

    model.toggle_sort("monto")

    assert model.sort_field == "monto"
    assert model.sort_direction == "asc"
    assert [model.row_data(row)["monto"] for row in range(model.rowCount())] == [10, 20, 30]
