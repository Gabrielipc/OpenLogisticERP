"""Typed DTOs and schema contracts for Modelo catalogs."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

SimpleValue = str | int | float | bool | None


class FieldKind(StrEnum):
    TEXT = "text"
    MULTILINE = "multiline"
    INTEGER = "integer"
    NUMBER = "number"
    BOOL = "bool"
    ENUM = "enum"
    REFERENCE = "reference"
    DATE = "date"
    DATETIME = "datetime"
    MONEY = "money"
    PERCENT = "percent"


@dataclass(frozen=True)
class FieldOptionDTO:
    value: SimpleValue
    label: str


@dataclass(frozen=True)
class ReferenceOptionDTO:
    value: SimpleValue
    label: str


@dataclass(frozen=True)
class ReferenceFieldDTO:
    lookup_key: str
    min_search_chars: int = 2
    page_size: int = 20
    value_field: str = "id"
    label_field: str = "label"


@dataclass(frozen=True)
class FieldSchemaDTO:
    name: str
    label: str
    kind: FieldKind = FieldKind.TEXT
    required: bool = False
    editable: bool = True
    default: SimpleValue = None
    options: tuple[FieldOptionDTO, ...] = ()
    nullable: bool = True
    read_only: bool = False
    list_visible: bool = True
    form_visible: bool = True
    list_width: int = 160
    min_width: int = 96
    sortable: bool = True
    filterable: bool = True
    reference: ReferenceFieldDTO | None = None
    display_field_key: str | None = None
    searchable: bool = True
    supported_operators: tuple[str, ...] = ()
    multi_value: bool = False

    def __post_init__(self) -> None:
        operators = tuple(
            str(operator).strip().lower()
            for operator in self.supported_operators
            if str(operator).strip()
        )
        object.__setattr__(self, "supported_operators", operators)


@dataclass(frozen=True)
class CatalogSchemaDTO:
    catalog_name: str
    title: str
    primary_key: str = "id"
    fields: tuple[FieldSchemaDTO, ...] = ()
    default_sort: str | None = None
    search_field: str | None = None
    search_fields: tuple[str, ...] = ()
    permissions: Mapping[str, bool] = field(
        default_factory=lambda: {"create": True, "edit": True, "delete": True}
    )

    def __post_init__(self) -> None:
        normalized_search_fields = tuple(
            str(field_name).strip()
            for field_name in self.search_fields
            if isinstance(field_name, str) and field_name.strip()
        )
        if self.search_field and not normalized_search_fields:
            normalized_search_fields = (str(self.search_field).strip(),)
        normalized_search_field = (
            str(self.search_field).strip()
            if isinstance(self.search_field, str) and self.search_field.strip()
            else None
        )
        if normalized_search_field is None and normalized_search_fields:
            normalized_search_field = normalized_search_fields[0]
        object.__setattr__(self, "search_field", normalized_search_field)
        object.__setattr__(self, "search_fields", normalized_search_fields)

    def field(self, name: str) -> FieldSchemaDTO:
        normalized = str(name or "")
        for field_schema in self.fields:
            if field_schema.name == normalized:
                return field_schema
        raise KeyError(f"Field not found in schema {self.catalog_name!r}: {name!r}")

    @property
    def list_fields(self) -> tuple[FieldSchemaDTO, ...]:
        return tuple(field_schema for field_schema in self.fields if field_schema.list_visible)

    @property
    def form_fields(self) -> tuple[FieldSchemaDTO, ...]:
        return tuple(field_schema for field_schema in self.fields if field_schema.form_visible)


@dataclass(frozen=True)
class CatalogRecordDTO(Mapping[str, SimpleValue]):
    catalog_name: str
    values: Mapping[str, SimpleValue]

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, key: str) -> SimpleValue:
        return self.values[key]

    def get(self, key: str, default: SimpleValue = None) -> SimpleValue:
        return self.values.get(key, default)

    def to_dict(self) -> dict[str, SimpleValue]:
        return dict(self.values)

    def with_values(self, **updates: SimpleValue) -> CatalogRecordDTO:
        data = self.to_dict()
        data.update(updates)
        return CatalogRecordDTO(catalog_name=self.catalog_name, values=data)


@dataclass(frozen=True)
class CatalogPageDTO:
    rows: tuple[CatalogRecordDTO, ...]
    total_count: int
    page: int
    page_size: int

    @property
    def has_more(self) -> bool:
        return (self.page + 1) * self.page_size < self.total_count

    @classmethod
    def from_iterable(
        cls,
        rows: Iterable[CatalogRecordDTO],
        *,
        total_count: int,
        page: int,
        page_size: int,
    ) -> CatalogPageDTO:
        return cls(
            rows=tuple(rows),
            total_count=int(total_count),
            page=int(page),
            page_size=int(page_size),
        )
