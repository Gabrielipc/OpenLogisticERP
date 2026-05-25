"""XLSX exporter for report payloads."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import xlsxwriter

from openlogistic_erp.domain.reports import ReportColumn, ReportPayload, ReportTable

from .formatting import currency_symbol, format_cell


class XlsxReportExporter:
    def export(self, payload: ReportPayload, target_path: str | Path, currency_key: str = "") -> None:
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        workbook = xlsxwriter.Workbook(str(path), {"strings_to_formulas": False})
        try:
            formats = _build_formats(workbook)
            _write_cover_sheet(workbook, payload, formats)
            used_names = {"Portada"}
            for table in payload.tables:
                rows = _filtered_rows(table, currency_key)
                if not rows:
                    continue
                _write_table_sheet(workbook, table, rows, used_names, formats)
        finally:
            workbook.close()


def _build_formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    return {
        "_workbook": workbook,
        "_number_cache": {},
        "title": workbook.add_format({"bold": True, "font_size": 16}),
        "label": workbook.add_format({"bold": True}),
        "header": workbook.add_format(
            {"bold": True, "bg_color": "#1F4E78", "font_color": "#FFFFFF", "border": 1}
        ),
        "text": workbook.add_format({"border": 1}),
        "int": workbook.add_format({"num_format": "#,##0", "border": 1}),
        "date": workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1}),
        "datetime": workbook.add_format({"num_format": "yyyy-mm-dd hh:mm", "border": 1}),
    }


def _write_cover_sheet(workbook: xlsxwriter.Workbook, payload: ReportPayload, formats: dict[str, Any]) -> None:
    sheet = workbook.add_worksheet("Portada")
    sheet.write_string(0, 0, payload.title, formats["title"])
    sheet.write_string(2, 0, "Generado", formats["label"])
    sheet.write_string(2, 1, payload.generated_at.strftime("%Y-%m-%d %H:%M"))
    if payload.message:
        sheet.write_string(4, 0, "Mensaje", formats["label"])
        sheet.write_string(4, 1, payload.message)
    sheet.set_column(0, 0, 16)
    sheet.set_column(1, 1, max(24, len(payload.title) + 2))


def _write_table_sheet(
    workbook: xlsxwriter.Workbook,
    table: ReportTable,
    rows: tuple[Mapping[str, Any], ...],
    used_names: set[str],
    formats: dict[str, Any],
) -> None:
    sheet = workbook.add_worksheet(_unique_sheet_name(table.title or table.key, used_names))
    widths = [len(column.label) for column in table.columns]

    for col_index, column in enumerate(table.columns):
        sheet.write_string(0, col_index, column.label, formats["header"])

    for row_index, row in enumerate(rows, start=1):
        for col_index, column in enumerate(table.columns):
            value = row.get(column.key)
            currency = row.get(table.currency_field or "moneda") if column.format == "currency" else None
            widths[col_index] = max(widths[col_index], len(format_cell(column, value, currency=currency)))
            _write_value(sheet, row_index, col_index, column, value, formats, currency=currency)

    for col_index, width in enumerate(widths):
        sheet.set_column(col_index, col_index, min(max(width + 2, 10), 48))
    sheet.freeze_panes(1, 0)
    sheet.autofilter(0, 0, len(rows), max(len(table.columns) - 1, 0))


def _write_value(
    sheet: Any,
    row_index: int,
    col_index: int,
    column: ReportColumn,
    value: Any,
    formats: dict[str, Any],
    *,
    currency: Any = None,
) -> None:
    if value is None:
        sheet.write_blank(row_index, col_index, None, formats["text"])
        return

    if column.format == "date" and isinstance(value, (date, datetime)):
        dt_value = value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)
        sheet.write_datetime(row_index, col_index, dt_value, formats["date"])
        return
    if column.format == "datetime" and isinstance(value, datetime):
        sheet.write_datetime(row_index, col_index, value, formats["datetime"])
        return
    if column.format in {"int", "float", "currency", "percent"}:
        try:
            number = float(value)
        except (TypeError, ValueError):
            _write_text(sheet, row_index, col_index, format_cell(column, value), formats["text"])
            return
        cell_format = (
            formats["int"]
            if column.format == "int"
            else _number_format(formats, column, currency=currency if column.format == "currency" else None)
        )
        sheet.write_number(row_index, col_index, number, cell_format)
        return

    _write_text(sheet, row_index, col_index, format_cell(column, value), formats["text"])


def _write_text(sheet: Any, row_index: int, col_index: int, text: str, cell_format: Any = None) -> None:
    if text:
        sheet.write_string(row_index, col_index, text, cell_format)
    else:
        sheet.write_blank(row_index, col_index, None, cell_format)


def _number_format(formats: dict[str, Any], column: ReportColumn, *, currency: Any = None) -> Any:
    kind = "percent" if column.format == "percent" else "currency" if currency is not None else "float"
    decimals = max(column.decimals, 0)
    symbol = currency_symbol(currency) if kind == "currency" else ""
    cache_key = (kind, decimals, symbol)
    cache = formats["_number_cache"]
    if cache_key not in cache:
        cache[cache_key] = formats["_workbook"].add_format(
            {"num_format": _number_format_pattern(kind, decimals, symbol=symbol), "border": 1}
        )
    return cache[cache_key]


def _number_format_pattern(kind: str, decimals: int, *, symbol: str = "") -> str:
    suffix = f".{'0' * decimals}" if decimals else ""
    if kind == "percent":
        return f"0{suffix}%"
    if kind == "currency":
        return f'"{symbol}" #,##0{suffix}'
    return f"#,##0{suffix}"


def _filtered_rows(table: ReportTable, currency_key: str) -> tuple[Mapping[str, Any], ...]:
    if not currency_key or not table.currency_field:
        return table.rows
    return tuple(row for row in table.rows if str(row.get(table.currency_field, "")) == currency_key)


def _unique_sheet_name(raw_name: str, used_names: set[str]) -> str:
    base = _sanitize_sheet_name(raw_name)[:31] or "Reporte"
    name = base
    counter = 2
    while name in used_names:
        suffix = f" {counter}"
        name = f"{base[: 31 - len(suffix)]}{suffix}"
        counter += 1
    used_names.add(name)
    return name


def _sanitize_sheet_name(name: str) -> str:
    invalid_chars = set('[]:*?/\\')
    sanitized = "".join("_" if char in invalid_chars else char for char in str(name)).strip()
    return sanitized or "Reporte"
