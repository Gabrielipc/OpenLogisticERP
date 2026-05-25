"""Cell formatting helpers for report exporters."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from openlogistic_erp.domain.reports import ReportColumn


def format_cell(column: ReportColumn, value: Any, *, currency: Any = None) -> str:
    if value is None:
        return ""

    match column.format:
        case "int":
            return _format_number(value, ",.0f")
        case "float":
            return _format_number(value, f",.{column.decimals}f")
        case "currency":
            formatted = _format_number(value, f",.{column.decimals}f")
            if currency is None or formatted == str(value):
                return formatted
            return f"{currency_symbol(currency)} {formatted}"
        case "percent":
            return _format_percent(value, column.decimals)
        case "date":
            if isinstance(value, datetime):
                return value.date().isoformat()
            if isinstance(value, date):
                return value.isoformat()
        case "datetime":
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M")

    return str(value)


def _format_number(value: Any, spec: str, *, suffix: str = "") -> str:
    try:
        return f"{float(value):{spec}}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def currency_symbol(currency: Any) -> str:
    code = str(getattr(currency, "value", currency) or "").strip().upper()
    if code == "USD":
        return "$"
    if code == "NIO":
        return "C$"
    return code or "$"


def _format_percent(value: Any, decimals: int) -> str:
    try:
        percent = float(value) * 100
    except (TypeError, ValueError):
        return str(value)
    return f"{percent:,.{decimals}f}%"
