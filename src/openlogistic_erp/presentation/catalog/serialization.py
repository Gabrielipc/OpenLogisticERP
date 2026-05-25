"""Shared value normalization helpers for catalog QML surfaces."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Any

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?([+-]\d{2}:\d{2}|Z)?$"
)


def serialize_catalog_value(value: Any) -> Any:
    """Normalize Python values before exposing them to QML."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return serialize_catalog_value(value.value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def display_catalog_value(value: Any) -> str:
    """Return the lightweight display string expected by catalog tables."""
    if value is True:
        return "Si"
    if value is False:
        return "No"
    if value is None:
        return ""
    if isinstance(value, str):
        formatted = _format_iso_temporal_string(value)
        if formatted is not None:
            return formatted
    return str(value)


def display_money_value(value: Any, currency: Any = None) -> str:
    """Return a read-only money display string with currency symbol and grouping."""
    symbol = currency_symbol(currency)
    try:
        decimal_value = Decimal(str(value or "0").strip())
    except (InvalidOperation, ValueError, AttributeError):
        decimal_value = Decimal("0")
    return f"{symbol} {decimal_value:,.2f}"


def currency_symbol(currency: Any) -> str:
    code = str(getattr(currency, "value", currency) or "").strip().upper()
    if code == "USD":
        return "$"
    if code == "NIO":
        return "C$"
    return code or "$"


def _format_iso_temporal_string(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if _ISO_DATE_PATTERN.fullmatch(text):
        return date.fromisoformat(text).strftime("%d/%m/%Y")
    if not _ISO_DATETIME_PATTERN.fullmatch(text):
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    return datetime.fromisoformat(normalized).strftime("%d/%m/%Y %H:%M")
