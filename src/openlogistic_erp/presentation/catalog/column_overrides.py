"""Presentation-only overrides for generated catalog table columns."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from .definitions import CatalogColumnDefinition, CatalogViewDefinition


@dataclass(frozen=True)
class CatalogColumnOverride:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    order: tuple[str, ...] = ()
    headers: Mapping[str, str] | None = None
    widths: Mapping[str, int] | None = None
    min_widths: Mapping[str, int] | None = None
    sortable: Mapping[str, bool] | None = None
    resizable: Mapping[str, bool] | None = None


CATALOG_COLUMN_OVERRIDES: Mapping[str, CatalogColumnOverride] = {
    "viaje": CatalogColumnOverride(
        exclude=(
            "circuito_label",
            "temperatura",
            "viaticos_monto",
            "viaticos_moneda",
        ),
    ),
}


def apply_catalog_column_overrides(
    view_definition: CatalogViewDefinition,
    *,
    overrides: Mapping[str, CatalogColumnOverride] | None = None,
) -> CatalogViewDefinition:
    active_overrides = CATALOG_COLUMN_OVERRIDES if overrides is None else overrides
    override = active_overrides.get(view_definition.catalog_name)
    if override is None:
        return view_definition

    columns_by_key = {column.key: column for column in view_definition.columns}
    _validate_override_keys(view_definition.catalog_name, columns_by_key, override)

    if override.include:
        columns = [columns_by_key[key] for key in override.include]
    else:
        excluded = set(override.exclude)
        columns = [column for column in view_definition.columns if column.key not in excluded]
        if override.order:
            ordered_keys = [key for key in override.order if key not in excluded]
            ordered = [columns_by_key[key] for key in ordered_keys]
            ordered_set = set(ordered_keys)
            ordered.extend(column for column in columns if column.key not in ordered_set)
            columns = ordered

    resolved_columns = tuple(_apply_property_overrides(column, override) for column in columns)
    return replace(view_definition, columns=resolved_columns)


def _validate_override_keys(
    catalog_name: str,
    columns_by_key: Mapping[str, CatalogColumnDefinition],
    override: CatalogColumnOverride,
) -> None:
    known_keys = set(columns_by_key)
    referenced_keys: set[str] = set(override.include)
    referenced_keys.update(override.exclude)
    referenced_keys.update(override.order)
    for mapping in (
        override.headers,
        override.widths,
        override.min_widths,
        override.sortable,
        override.resizable,
    ):
        if mapping:
            referenced_keys.update(mapping)

    unknown = sorted(referenced_keys - known_keys)
    if unknown:
        available = ", ".join(sorted(known_keys)) or "(none)"
        invalid = ", ".join(unknown)
        raise ValueError(
            f"Invalid column override for catalog {catalog_name!r}: {invalid}. "
            f"Available columns: {available}."
        )


def _apply_property_overrides(
    column: CatalogColumnDefinition,
    override: CatalogColumnOverride,
) -> CatalogColumnDefinition:
    key = column.key
    updates: dict[str, object] = {}
    if override.headers and key in override.headers:
        updates["header"] = override.headers[key]
    if override.widths and key in override.widths:
        updates["width"] = int(override.widths[key])
    if override.min_widths and key in override.min_widths:
        updates["min_width"] = int(override.min_widths[key])
    if override.sortable and key in override.sortable:
        updates["sortable"] = bool(override.sortable[key])
    if override.resizable and key in override.resizable:
        updates["resizable"] = bool(override.resizable[key])
    if not updates:
        return column
    return replace(column, **updates)
