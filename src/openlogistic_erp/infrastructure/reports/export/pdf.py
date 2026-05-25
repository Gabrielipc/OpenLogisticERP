"""PDF exporter for report payloads."""

from __future__ import annotations

from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter

from openlogistic_erp.domain.reports import ReportPayload, ReportTable

from .formatting import format_cell


class PdfReportExporter:
    def export(self, payload: ReportPayload, target_path: str | Path, currency_key: str = "") -> None:
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        document = QTextDocument()
        document.setHtml(_build_html(payload, currency_key))

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        document.print_(printer)
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"PDF export failed: output file is missing or empty: {path}")


def _build_html(payload: ReportPayload, currency_key: str) -> str:
    pieces = [
        "<html><head><meta charset='utf-8'>",
        "<style>",
        "body { font-family: sans-serif; font-size: 10pt; }",
        "h1 { font-size: 18pt; margin-bottom: 4px; }",
        "h2 { font-size: 13pt; margin-top: 20px; }",
        "table { border-collapse: collapse; width: 100%; margin-top: 8px; }",
        "th { background: #1f4e78; color: white; }",
        "th, td { border: 1px solid #888; padding: 4px 6px; }",
        "td.num { text-align: right; }",
        ".meta { color: #555; margin-bottom: 12px; }",
        "</style></head><body>",
        f"<h1>{escape(payload.title)}</h1>",
        f"<div class='meta'>Generado: {escape(payload.generated_at.strftime('%Y-%m-%d %H:%M'))}</div>",
    ]
    if payload.message:
        pieces.append(f"<p>{escape(payload.message)}</p>")

    for table in payload.tables:
        rows = _filtered_rows(table, currency_key)
        if not rows:
            continue
        pieces.append(_table_html(table, rows))

    pieces.append("</body></html>")
    return "".join(pieces)


def _table_html(table: ReportTable, rows: tuple[Mapping[str, Any], ...]) -> str:
    pieces = [f"<h2>{escape(table.title)}</h2><table><thead><tr>"]
    for column in table.columns:
        pieces.append(f"<th>{escape(column.label)}</th>")
    pieces.append("</tr></thead><tbody>")

    for row in rows:
        pieces.append("<tr>")
        for column in table.columns:
            css_class = " class='num'" if column.format in {"int", "float", "currency", "percent"} else ""
            currency = row.get(table.currency_field or "moneda") if column.format == "currency" else None
            pieces.append(f"<td{css_class}>{escape(format_cell(column, row.get(column.key), currency=currency))}</td>")
        pieces.append("</tr>")

    pieces.append("</tbody></table>")
    return "".join(pieces)


def _filtered_rows(table: ReportTable, currency_key: str) -> tuple[Mapping[str, Any], ...]:
    if not currency_key or not table.currency_field:
        return table.rows
    return tuple(row for row in table.rows if str(row.get(table.currency_field, "")) == currency_key)
