"""Shared field normalization rules for catalog schemas and form UIs."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .dtos import FieldKind, SimpleValue

DATE_DISPLAY_FORMAT = "DD/MM/YYYY"
DATETIME_DISPLAY_FORMAT = "DD/MM/YYYY HH:MM"

_TRUE_VALUES = {"1", "true", "si", "sí", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def field_precision(kind: FieldKind | str) -> int | None:
    normalized = _coerce_kind(kind)
    if normalized == FieldKind.MONEY:
        return 2
    if normalized == FieldKind.PERCENT:
        return 4
    return None


def field_display_format(kind: FieldKind | str) -> str | None:
    normalized = _coerce_kind(kind)
    if normalized == FieldKind.DATE:
        return DATE_DISPLAY_FORMAT
    if normalized == FieldKind.DATETIME:
        return DATETIME_DISPLAY_FORMAT
    return None


def validate_field_value(
    *,
    kind: FieldKind | str,
    value: Any,
    required: bool = False,
    nullable: bool = True,
    options: Iterable[Any] = (),
) -> str | None:
    try:
        normalize_field_value(
            kind=kind,
            value=value,
            required=required,
            nullable=nullable,
            options=options,
        )
    except ValueError as exc:
        return str(exc)
    return None


def normalize_field_value(
    *,
    kind: FieldKind | str,
    value: Any,
    required: bool = False,
    nullable: bool = True,
    options: Iterable[Any] = (),
) -> SimpleValue:
    normalized_kind = _coerce_kind(kind)
    normalized_value = _normalize_empty(value)
    if normalized_value is None:
        if required:
            raise ValueError("Este campo es obligatorio.")
        if not nullable:
            raise ValueError("Este campo no admite valores vacios.")
        return None

    if normalized_kind == FieldKind.BOOL:
        return _normalize_bool(normalized_value)
    if normalized_kind == FieldKind.ENUM:
        return _normalize_enum(normalized_value, options)
    if normalized_kind == FieldKind.REFERENCE:
        return _normalize_integer(normalized_value)
    if normalized_kind == FieldKind.INTEGER:
        return _normalize_integer(normalized_value)
    if normalized_kind in {FieldKind.NUMBER, FieldKind.MONEY, FieldKind.PERCENT}:
        precision = field_precision(normalized_kind)
        return _normalize_decimal(normalized_value, precision=precision)
    if normalized_kind == FieldKind.DATE:
        return _normalize_date(normalized_value)
    if normalized_kind == FieldKind.DATETIME:
        return _normalize_datetime(normalized_value)
    return _normalize_text(normalized_value)


def format_field_value_for_ui(
    *,
    kind: FieldKind | str,
    value: Any,
    precision: int | None = None,
) -> Any:
    normalized_kind = _coerce_kind(kind)
    if value is None:
        return False if normalized_kind == FieldKind.BOOL else ""
    if normalized_kind == FieldKind.BOOL:
        return bool(value)
    if normalized_kind == FieldKind.ENUM:
        return str(value)
    if normalized_kind == FieldKind.REFERENCE:
        return int(value)
    if normalized_kind == FieldKind.INTEGER:
        return str(int(value))
    if normalized_kind in {FieldKind.NUMBER, FieldKind.MONEY, FieldKind.PERCENT}:
        return _format_decimal_for_ui(value, precision=precision or field_precision(normalized_kind))
    if normalized_kind == FieldKind.DATE:
        return _format_date_for_ui(value)
    if normalized_kind == FieldKind.DATETIME:
        return _format_datetime_for_ui(value)
    return str(value)


def _coerce_kind(kind: FieldKind | str) -> FieldKind:
    if isinstance(kind, FieldKind):
        return kind
    return FieldKind(str(kind or FieldKind.TEXT.value).strip().lower())


def _normalize_empty(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_text(value: Any) -> str:
    return str(value)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_VALUES:
            return True
        if normalized in _FALSE_VALUES:
            return False
    raise ValueError("Debe ser un valor booleano valido.")


def _normalize_enum(value: Any, options: Iterable[Any]) -> SimpleValue:
    option_values = [_option_value(option) for option in options]
    if value in option_values:
        return value
    for option_value in option_values:
        if str(option_value) == str(value):
            return option_value
    raise ValueError("Debe seleccionar una opcion valida.")


def _normalize_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Debe ser un numero entero.")
    try:
        if isinstance(value, int):
            return value
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Debe ser un numero entero.") from exc


def _normalize_decimal(value: Any, *, precision: int | None) -> str:
    if isinstance(value, bool):
        raise ValueError("Debe ser un numero valido.")
    try:
        decimal_value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Debe ser un numero valido.") from exc
    if precision is not None:
        quantum = Decimal("1").scaleb(-precision)
        decimal_value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
        return format(decimal_value, f".{precision}f")
    normalized = format(decimal_value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _normalize_date(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat()


def _normalize_datetime(value: Any) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%Y-%m-%dT%H:%M")


def _format_decimal_for_ui(value: Any, *, precision: int | None) -> str:
    try:
        decimal_value = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return str(value)
    if precision is not None:
        quantum = Decimal("1").scaleb(-precision)
        decimal_value = decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)
        return format(decimal_value, f".{precision}f")
    normalized = format(decimal_value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _format_date_for_ui(value: Any) -> str:
    return _parse_date(value).strftime("%d/%m/%Y")


def _format_datetime_for_ui(value: Any) -> str:
    return _parse_datetime(value).strftime("%d/%m/%Y %H:%M")


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y").date()
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Debe usar el formato {DATE_DISPLAY_FORMAT}.") from exc


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        if "/" in text:
            return datetime.strptime(text, "%d/%m/%Y %H:%M")
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Debe usar el formato {DATETIME_DISPLAY_FORMAT}.") from exc


def _option_value(option: Any) -> SimpleValue:
    if hasattr(option, "value"):
        return option.value
    if isinstance(option, dict):
        return option.get("value")
    return option
