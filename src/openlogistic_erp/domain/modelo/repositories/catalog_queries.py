"""Repository contracts for catalog query/read operations."""

from __future__ import annotations

from typing import Protocol

from ..catalog_queries import CatalogFilter, CatalogPageResult, CatalogQueryRequest, CatalogSort
from ..dtos import CatalogSchemaDTO


class CatalogQueryRepository(Protocol):
    """Read-side contract for paginated catalog queries."""

    def query_page(self, request: CatalogQueryRequest) -> CatalogPageResult:
        ...

    def get_schema(self, catalog_name: str) -> CatalogSchemaDTO:
        ...

    def locate_record_page(
        self,
        catalog_name: str,
        record_id: int,
        *,
        page_size: int,
        sort: CatalogSort | None = None,
        search_text: str | None = None,
        search_fields: tuple[str, ...] | list[str] | None = None,
        search_filters: tuple[CatalogFilter, ...] | list[CatalogFilter] | None = None,
        filters: tuple[CatalogFilter, ...] | list[CatalogFilter] | None = None,
    ) -> int | None:
        ...
