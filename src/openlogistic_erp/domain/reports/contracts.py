"""Pure domain contracts for report definitions, requests, and payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ReportFormat(StrEnum):
    PREVIEW = "preview"
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"


@dataclass(frozen=True)
class ReportFilterOption:
    value: Any
    label: str

    def to_map(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label}


@dataclass(frozen=True)
class ReportFilterDefinition:
    key: str
    label: str
    type: str
    required: bool = False
    default: Any = None
    options: tuple[ReportFilterOption, ...] = ()

    def to_map(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "options": [option.to_map() for option in self.options],
        }


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    format: str = "text"
    decimals: int = 2

    def to_map(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "format": self.format,
            "decimals": self.decimals,
        }


@dataclass(frozen=True)
class ReportTable:
    key: str
    title: str
    columns: tuple[ReportColumn, ...] = ()
    rows: tuple[Mapping[str, Any], ...] = ()
    currency_field: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rows",
            tuple(MappingProxyType(dict(row)) for row in self.rows),
        )

    def to_map(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "columns": [column.to_map() for column in self.columns],
            "rows": [dict(row) for row in self.rows],
            "currency_field": self.currency_field,
        }


@dataclass(frozen=True)
class ReportPayload:
    title: str
    generated_at: datetime
    message: str = ""
    tables: tuple[ReportTable, ...] = ()
    currencies: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "currencies",
            tuple(MappingProxyType(dict(currency)) for currency in self.currencies),
        )

    def to_map(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "generated_at": self.generated_at.isoformat(),
            "tables": [table.to_map() for table in self.tables],
            "currencies": [dict(currency) for currency in self.currencies],
        }


@dataclass(frozen=True)
class ReportRequest:
    report_key: str
    params: Mapping[str, Any] = field(default_factory=dict)
    export_format: ReportFormat = ReportFormat.PREVIEW

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_key", str(self.report_key).strip())
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        if not isinstance(self.export_format, ReportFormat):
            object.__setattr__(self, "export_format", ReportFormat(str(self.export_format).strip().lower()))
