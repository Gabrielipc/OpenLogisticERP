"""Catalog schema extraction and record serialization for SQLAlchemy models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, String, Text
from sqlalchemy import Enum as SqlEnum

from ....domain.modelo.dtos import (
    CatalogRecordDTO,
    CatalogSchemaDTO,
    FieldKind,
    FieldOptionDTO,
    FieldSchemaDTO,
    SimpleValue,
)
from .reference_profiles import DEFAULT_REFERENCE_PROFILES, ReferenceProfileRegistry

_TITLE_OVERRIDES: dict[str, str] = {
    "cliente": "Gestión de Clientes",
    "ubicacion": "Gestión de Destinos",
    "impuesto": "Gestión de Impuestos",
    "camion": "Gestión de Camiones",
    "conductor": "Gestión de Conductores",
    "furgon": "Gestión de Furgones",
    "thermo": "Gestión de Thermos",
}

_SEARCH_FIELD_OVERRIDES: dict[str, str] = {
    "cliente": "nombre",
    "ubicacion": "descripcion",
    "impuesto": "codigo",
    "camion": "placa",
    "conductor": "nombre",
    "furgon": "placa",
    "thermo": "codigo",
}

_MULTILINE_FIELDS = {"direccion", "descripcion"}
_PERCENT_FIELDS = {"porcentaje"}
_MONEY_FIELDS = {"monto", "subtotal", "total", "saldo_restante", "saldo_disponible", "costo"}
_SHORT_CODE_FIELDS = {"codigo", "ruc", "placa", "numero", "serie"}
_NAME_FIELDS = {"nombre", "titulo"}
_LONG_TEXT_FIELDS = {"descripcion", "direccion"}
_CIRCUITO_DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("conductor_label", "Conductor"),
    ("ruta_ida_label", "Ruta Ida"),
    ("ruta_vuelta_label", "Ruta Vuelta"),
)


def build_catalog_schema(
    model_cls: type,
    *,
    catalog_name: str | None = None,
    reference_registry: ReferenceProfileRegistry | None = None,
) -> CatalogSchemaDTO:
    normalized_name = str(catalog_name or getattr(model_cls, "__tablename__", model_cls.__name__)).lower()
    active_registry = reference_registry or DEFAULT_REFERENCE_PROFILES
    search_fields = _resolve_search_fields(normalized_name, model_cls, active_registry)
    fields = _build_catalog_fields(
        normalized_name,
        model_cls.__table__.columns,
        active_registry,
        search_fields=search_fields,
    )
    if normalized_name == "circuito":
        fields.extend(_build_circuito_derived_fields())
    primary_key = next((column.key for column in model_cls.__table__.primary_key.columns), "id")
    return CatalogSchemaDTO(
        catalog_name=normalized_name,
        title=_TITLE_OVERRIDES.get(normalized_name, normalized_name.replace("_", " ").title()),
        primary_key=primary_key,
        fields=tuple(fields),
        default_sort=primary_key,
        search_field=_SEARCH_FIELD_OVERRIDES.get(normalized_name),
        search_fields=search_fields,
    )


def row_to_record(model_name: str, row: Any) -> CatalogRecordDTO:
    mapper = row.__mapper__
    data = {column.key: _serialize_value(getattr(row, column.key)) for column in mapper.columns}
    return CatalogRecordDTO(catalog_name=model_name, values=data)


def deserialize_record_input(model_cls: type, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for column in model_cls.__table__.columns:
        if column.key not in payload:
            continue
        normalized[column.key] = _deserialize_value(column.type, payload[column.key])
    return normalized


def _build_catalog_fields(
    catalog_name: str,
    columns,
    reference_registry: ReferenceProfileRegistry,
    *,
    search_fields: tuple[str, ...],
) -> list[FieldSchemaDTO]:
    fields: list[FieldSchemaDTO] = []
    for column in columns:
        profile = reference_registry.field_profile(catalog_name, str(column.key))
        fields.append(_build_field_schema(column, profile=profile, search_fields=search_fields))
        if profile is None:
            continue
        list_width = _default_list_width(profile.display_field_key, String())
        fields.append(
            FieldSchemaDTO(
                name=profile.display_field_key,
                label=profile.label,
                kind=FieldKind.TEXT,
                required=False,
                editable=False,
                nullable=True,
                read_only=True,
                list_visible=True,
                form_visible=False,
                list_width=list_width,
                min_width=_default_min_width(profile.display_field_key, list_width),
                sortable=False,
                filterable=False,
                searchable=False,
                supported_operators=(),
                multi_value=False,
            )
        )
    return fields


def _build_circuito_derived_fields() -> list[FieldSchemaDTO]:
    return [
        FieldSchemaDTO(
            name=field_name,
            label=label,
            kind=FieldKind.TEXT,
            required=False,
            editable=False,
            nullable=True,
            read_only=True,
            list_visible=True,
            form_visible=False,
            list_width=220,
            min_width=160,
            sortable=False,
            filterable=False,
            searchable=True,
            supported_operators=("contains", "eq"),
            multi_value=False,
        )
        for field_name, label in _CIRCUITO_DERIVED_FIELDS
    ]


def _build_field_schema(
    column,
    *,
    profile=None,
    search_fields: tuple[str, ...],
) -> FieldSchemaDTO:
    field_name = str(column.key)
    is_primary_key = bool(column.primary_key)
    if profile is not None:
        list_width = _default_list_width(field_name, column.type)
        return FieldSchemaDTO(
            name=field_name,
            label=profile.label,
            kind=FieldKind.REFERENCE,
            required=not bool(column.nullable) and not is_primary_key,
            editable=not is_primary_key,
            default=_serialize_value(_default_value(column.default.arg if column.default is not None else None)),
            nullable=bool(column.nullable),
            read_only=is_primary_key,
            list_visible=False,
            form_visible=not is_primary_key,
            list_width=list_width,
            min_width=_default_min_width(field_name, list_width),
            sortable=True,
            filterable=not is_primary_key,
            reference=profile.to_reference_dto(),
            display_field_key=profile.display_field_key,
            searchable=field_name in search_fields,
            supported_operators=_supported_operators(FieldKind.REFERENCE),
            multi_value=True,
        )

    kind = _field_kind_for_column(field_name, column.type)
    list_width = _default_list_width(field_name, column.type)
    return FieldSchemaDTO(
        name=field_name,
        label=_label_for_field(field_name),
        kind=kind,
        required=not bool(column.nullable) and not is_primary_key,
        editable=not is_primary_key,
        default=_serialize_value(_default_value(column.default.arg if column.default is not None else None)),
        options=_enum_options(column.type),
        nullable=bool(column.nullable),
        read_only=is_primary_key,
        list_visible=not is_primary_key,
        form_visible=not is_primary_key,
        list_width=list_width,
        min_width=_default_min_width(field_name, list_width),
        sortable=True,
        filterable=not is_primary_key,
        searchable=field_name in search_fields,
        supported_operators=_supported_operators(kind),
        multi_value=kind == FieldKind.ENUM,
    )


def _label_for_field(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def _field_kind_for_column(field_name: str, column_type) -> FieldKind:
    normalized_field_name = field_name.lstrip("_")
    if normalized_field_name in _PERCENT_FIELDS:
        return FieldKind.PERCENT
    if normalized_field_name in _MONEY_FIELDS:
        return FieldKind.MONEY
    if normalized_field_name in _MULTILINE_FIELDS:
        return FieldKind.MULTILINE
    if isinstance(column_type, Boolean):
        return FieldKind.BOOL
    if isinstance(column_type, Integer):
        return FieldKind.INTEGER
    if isinstance(column_type, (Numeric, Float)):
        return FieldKind.NUMBER
    if isinstance(column_type, DateTime):
        return FieldKind.DATETIME
    if isinstance(column_type, Date):
        return FieldKind.DATE
    if isinstance(column_type, SqlEnum):
        return FieldKind.ENUM
    return FieldKind.TEXT


def _supported_operators(kind: FieldKind) -> tuple[str, ...]:
    if kind == FieldKind.REFERENCE:
        return ("eq", "in", "contains")
    if kind in {FieldKind.TEXT, FieldKind.MULTILINE}:
        return ("contains", "eq")
    if kind == FieldKind.ENUM:
        return ("eq", "in")
    if kind == FieldKind.BOOL:
        return ("eq",)
    if kind in {
        FieldKind.INTEGER,
        FieldKind.NUMBER,
        FieldKind.MONEY,
        FieldKind.PERCENT,
        FieldKind.DATE,
        FieldKind.DATETIME,
    }:
        return ("eq", "gte", "lte", "between")
    return ("eq",)


def _default_list_width(field_name: str, column_type) -> int:
    normalized = str(field_name).lower()
    normalized_without_prefix = normalized.lstrip("_")
    if normalized == "id":
        return 80
    if normalized_without_prefix in _LONG_TEXT_FIELDS:
        return 280
    if normalized_without_prefix in _NAME_FIELDS:
        return 200
    if normalized_without_prefix in _SHORT_CODE_FIELDS:
        return 140
    if normalized_without_prefix in _PERCENT_FIELDS or normalized_without_prefix in _MONEY_FIELDS:
        return 130
    if isinstance(column_type, Boolean):
        return 90
    if isinstance(column_type, (Date, DateTime, Integer, Numeric, Float, SqlEnum)):
        return 130
    return 160


def _default_min_width(field_name: str, list_width: int) -> int:
    normalized = str(field_name).lower()
    if normalized == "id":
        return 72
    if normalized in _LONG_TEXT_FIELDS:
        return 180
    return min(max(int(list_width * 0.65), 84), list_width)


def _enum_options(column_type) -> tuple[FieldOptionDTO, ...]:
    if not isinstance(column_type, SqlEnum):
        return ()
    enum_cls = getattr(column_type, "enum_class", None)
    if enum_cls is None:
        return tuple(FieldOptionDTO(value=str(value), label=str(value)) for value in column_type.enums)
    return tuple(
        FieldOptionDTO(value=_serialize_value(member.value), label=str(member.value))
        for member in enum_cls
    )


def _resolve_search_fields(
    catalog_name: str,
    model_cls: type,
    reference_registry: ReferenceProfileRegistry,
) -> tuple[str, ...]:
    prioritized: list[str] = []
    override = _SEARCH_FIELD_OVERRIDES.get(catalog_name)
    if override is not None:
        prioritized.append(str(override))

    for column in model_cls.__table__.columns:
        if bool(column.primary_key):
            continue
        if reference_registry.field_profile(catalog_name, str(column.key)) is not None:
            prioritized.append(str(column.key))
            continue
        if column.foreign_keys:
            continue
        if isinstance(column.type, (String, Text, SqlEnum)):
            prioritized.append(str(column.key))

    if catalog_name == "circuito":
        prioritized.extend(field_name for field_name, _label in _CIRCUITO_DERIVED_FIELDS)

    return _unique_preserving_order(prioritized)


def _unique_preserving_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return tuple(unique)


def _default_value(value: Any) -> Any:
    if callable(value):
        try:
            return value()
        except TypeError:
            return None
    return value


def _serialize_value(value: Any) -> SimpleValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        serialized = value.value
        return serialized if isinstance(serialized, (bool, int, float, str)) else str(serialized)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def _deserialize_value(column_type, value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(column_type, SqlEnum):
        enum_cls = getattr(column_type, "enum_class", None)
        if enum_cls is None or isinstance(value, enum_cls):
            return value
        for member in enum_cls:
            if member.value == value or member.name == value:
                return member
        return value
    if isinstance(column_type, Boolean):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "si", "yes", "on"}
        return bool(value)
    if isinstance(column_type, Integer):
        return int(value)
    if isinstance(column_type, Float):
        return float(value)
    if isinstance(column_type, Numeric):
        return Decimal(str(value))
    if isinstance(column_type, DateTime):
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if isinstance(column_type, Date):
        return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value))
    return value
