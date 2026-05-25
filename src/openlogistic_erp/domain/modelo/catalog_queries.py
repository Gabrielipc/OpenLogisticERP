"""Query contracts and DTOs for catalog-oriented reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .dtos import CatalogPageDTO


class CatalogSortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class CatalogFilterOperator(StrEnum):
    EQ = "eq"
    CONTAINS = "contains"
    IN = "in"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"


@dataclass(frozen=True)
class CatalogFilter:
    field: str
    operator: CatalogFilterOperator = CatalogFilterOperator.EQ
    value: Any = None
    value_to: Any = None
    is_hidden: bool = False


@dataclass(frozen=True)
class CatalogSort:
    field: str | None = None
    direction: CatalogSortDirection = CatalogSortDirection.ASC


@dataclass(frozen=True)
class CatalogQueryRequest:
    catalog_name: str
    page: int = 0
    page_size: int = 20
    sort: CatalogSort = field(default_factory=CatalogSort)
    search_text: str | None = None
    search_fields: tuple[str, ...] = ()
    search_filters: tuple[CatalogFilter, ...] = ()
    filters: tuple[CatalogFilter, ...] = ()


CatalogPageResult = CatalogPageDTO
