"""Declarative definitions used by catalog presentation components."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ...domain.modelo.catalog_queries import CatalogSort, CatalogSortDirection
from ...domain.modelo.dtos import (
    CatalogSchemaDTO,
    FieldKind,
    FieldOptionDTO,
    FieldSchemaDTO,
    ReferenceFieldDTO,
)
from ...domain.modelo.field_validation import field_display_format, field_precision
from .form_layout import FormLayoutDefinition
from .types import FormMode

FormViewModelFactory = Callable[[str, FormMode, Mapping[str, Any]], object]
FormMatcher = Callable[[str, Mapping[str, Any]], bool]


@dataclass(frozen=True)
class CatalogColumnDefinition:
    key: str
    header: str | None = None
    width: int | None = None
    min_width: int | None = None
    sortable: bool = True
    resizable: bool = True


@dataclass(frozen=True)
class FormFieldOption:
    value: Any
    label: str | None = None

    def display_label(self) -> str:
        return self.label or str(self.value)

    @classmethod
    def from_dto(cls, option: FieldOptionDTO) -> FormFieldOption:
        return cls(value=option.value, label=option.label)


@dataclass(frozen=True)
class GenericFormFieldDefinition:
    name: str
    label: str | None = None
    field_type: str = "text"
    kind: str | None = None
    required: bool = False
    default: Any = None
    editable: bool = True
    nullable: bool = True
    precision: int | None = None
    display_format: str | None = None
    options: tuple[FormFieldOption, ...] = ()
    load_transform: Callable[[Any], Any] | None = None
    submit_transform: Callable[[Any], Any] | None = None
    reference: ReferenceFieldDTO | None = None
    display_field_key: str | None = None

    def __post_init__(self) -> None:
        normalized_kind = str(self.kind or _kind_from_field_type(self.field_type)).strip().lower()
        resolved_field_type = str(self.field_type or "").strip().lower()
        if not resolved_field_type or (self.kind is not None and resolved_field_type == "text"):
            resolved_field_type = _field_type_from_kind_value(normalized_kind)
        object.__setattr__(self, "kind", normalized_kind)
        object.__setattr__(self, "field_type", resolved_field_type)
        if self.precision is None:
            object.__setattr__(self, "precision", field_precision(normalized_kind))
        if self.display_format is None:
            object.__setattr__(self, "display_format", field_display_format(normalized_kind))

    def resolve_default(self) -> Any:
        return self.default() if callable(self.default) else self.default

    @classmethod
    def from_schema(cls, field_schema: FieldSchemaDTO) -> GenericFormFieldDefinition:
        return cls(
            name=field_schema.name,
            label=field_schema.label,
            field_type=_field_type_from_kind(field_schema.kind),
            kind=field_schema.kind.value,
            required=field_schema.required,
            default=field_schema.default,
            editable=field_schema.editable and not field_schema.read_only,
            nullable=field_schema.nullable,
            precision=field_precision(field_schema.kind),
            display_format=field_display_format(field_schema.kind),
            options=tuple(FormFieldOption.from_dto(option) for option in field_schema.options),
            reference=field_schema.reference,
            display_field_key=field_schema.display_field_key,
        )


@dataclass(frozen=True)
class CatalogViewDefinition:
    catalog_name: str
    title: str | None = None
    columns: tuple[CatalogColumnDefinition, ...] = ()
    qml_component: str = "CatalogScreen.qml"
    form_id: str | None = None
    page_size: int = 20
    default_sort: CatalogSort = field(default_factory=CatalogSort)
    search_field: str | None = None
    search_fields: tuple[str, ...] = ()
    search_placeholder: str | None = None
    permissions: Mapping[str, bool] = field(
        default_factory=lambda: {"create": True, "edit": True, "delete": True}
    )
    schema_fields: tuple[FieldSchemaDTO, ...] = ()
    generic_form_fields: tuple[GenericFormFieldDefinition, ...] = ()
    form_layout: FormLayoutDefinition | None = None
    form_context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_search_fields = tuple(
            str(field_name).strip()
            for field_name in self.search_fields
            if isinstance(field_name, str) and field_name.strip()
        )
        normalized_search_field = (
            str(self.search_field).strip()
            if isinstance(self.search_field, str) and self.search_field.strip()
            else None
        )
        if normalized_search_field is None and normalized_search_fields:
            normalized_search_field = normalized_search_fields[0]
        if normalized_search_field is not None and normalized_search_field not in normalized_search_fields:
            normalized_search_fields = (normalized_search_field, *normalized_search_fields)
        object.__setattr__(self, "search_field", normalized_search_field)
        object.__setattr__(self, "search_fields", normalized_search_fields)

    @classmethod
    def from_schema(
        cls,
        schema: CatalogSchemaDTO,
        *,
        form_id: str | None = None,
        form_layout: FormLayoutDefinition | None = None,
        qml_component: str = "CatalogScreen.qml",
        page_size: int = 20,
        form_context: Mapping[str, Any] | None = None,
    ) -> CatalogViewDefinition:
        return cls(
            catalog_name=schema.catalog_name,
            title=schema.title,
            columns=tuple(
                CatalogColumnDefinition(
                    key=field_schema.name,
                    header=field_schema.label,
                    width=field_schema.list_width,
                    min_width=field_schema.min_width,
                    sortable=field_schema.sortable,
                    resizable=True,
                )
                for field_schema in schema.list_fields
            ),
            qml_component=qml_component,
            form_id=form_id,
            page_size=page_size,
            default_sort=CatalogSort(field=schema.default_sort, direction=CatalogSortDirection.DESC),
            search_field=schema.search_field,
            search_fields=schema.search_fields,
            search_placeholder=_build_search_placeholder(schema),
            permissions=dict(schema.permissions),
            schema_fields=tuple(schema.fields),
            generic_form_fields=tuple(
                GenericFormFieldDefinition.from_schema(field_schema)
                for field_schema in schema.form_fields
            ),
            form_layout=form_layout,
            form_context=dict(form_context or {}),
        )


@dataclass(frozen=True)
class FormDefinition:
    form_id: str
    qml_component: str
    view_model_factory: FormViewModelFactory
    presentation_mode: str = "drawer"
    navigation_title: str | None = None
    supported_modes: tuple[FormMode, ...] = (FormMode.CREATE, FormMode.EDIT, FormMode.VIEW)
    catalog_names: tuple[str, ...] = ()
    priority: int = 0
    applies_to: FormMatcher | None = None

    def supports(self, mode: FormMode) -> bool:
        return mode in self.supported_modes

    def matches(self, catalog_name: str, context: Mapping[str, Any]) -> bool:
        if self.catalog_names and catalog_name not in self.catalog_names:
            return False
        if self.applies_to is not None and not self.applies_to(catalog_name, context):
            return False
        return True


def _field_type_from_kind(kind: FieldKind) -> str:
    return _field_type_from_kind_value(kind.value)


def _field_type_from_kind_value(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized == FieldKind.MULTILINE.value:
        return "multiline"
    if normalized == FieldKind.BOOL.value:
        return "bool"
    if normalized == FieldKind.ENUM.value:
        return "enum"
    if normalized == FieldKind.REFERENCE.value:
        return "reference"
    if normalized in {
        FieldKind.INTEGER.value,
        FieldKind.NUMBER.value,
        FieldKind.MONEY.value,
        FieldKind.PERCENT.value,
    }:
        return "number"
    return "text"


def _kind_from_field_type(field_type: str) -> str:
    normalized = str(field_type or "text").strip().lower()
    if normalized == "multiline":
        return FieldKind.MULTILINE.value
    if normalized == "bool":
        return FieldKind.BOOL.value
    if normalized == "enum":
        return FieldKind.ENUM.value
    if normalized == "reference":
        return FieldKind.REFERENCE.value
    if normalized == "number":
        return FieldKind.NUMBER.value
    return FieldKind.TEXT.value


def _build_search_placeholder(schema: CatalogSchemaDTO) -> str | None:
    if not schema.search_fields:
        return None
    labels: list[str] = []
    for field_name in schema.search_fields[:2]:
        try:
            labels.append(schema.field(field_name).label.lower())
        except KeyError:
            labels.append(field_name.lower())
    if len(schema.search_fields) > 2:
        labels.append("otros campos")
    return f"Buscar en {', '.join(labels)}"
