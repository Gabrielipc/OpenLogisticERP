"""Read-side application service for catalog screens."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ...domain.modelo.catalog_queries import (
    CatalogFilter,
    CatalogFilterOperator,
    CatalogPageResult,
    CatalogQueryRequest,
    CatalogSort,
)
from ...domain.modelo.dtos import CatalogSchemaDTO, ReferenceFieldDTO
from ...domain.modelo.repositories.catalog_queries import CatalogQueryRepository
from .contracts import InvalidIdentifierError, InvalidPayloadError
from .reference_service import ReferenceLookupService

_REFERENCE_FILTER_LOOKUP_LIMIT = 200
_REFERENCE_OPTION_LOOKUP_LIMIT = 20


@dataclass(frozen=True)
class ModeloCatalogQueryService:
    """Validates and dispatches catalog-oriented read requests."""

    query_repository: CatalogQueryRepository
    reference_lookup_service: ReferenceLookupService | None = None

    def get_schema(self, catalog_name: str) -> CatalogSchemaDTO:
        normalized = self._normalize_catalog_name(catalog_name)
        return self.query_repository.get_schema(normalized)

    @staticmethod
    def _normalize_catalog_name(catalog_name: str) -> str:
        if not isinstance(catalog_name, str) or not catalog_name.strip():
            raise InvalidPayloadError("catalog_name is required")
        return catalog_name.strip().lower()

    @staticmethod
    def _normalize_page(page: int) -> int:
        if not isinstance(page, int) or page < 0:
            raise InvalidIdentifierError("page debe ser entero no negativo")
        return page

    @staticmethod
    def _normalize_page_size(page_size: int) -> int:
        if not isinstance(page_size, int) or page_size <= 0:
            raise InvalidIdentifierError("page_size debe ser entero positivo")
        return page_size

    @staticmethod
    def _normalize_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("record_id debe ser entero positivo")
        return record_id

    @staticmethod
    def _normalize_sort(sort: CatalogSort | None) -> CatalogSort:
        if sort is None:
            return CatalogSort()
        if sort.field is not None and (not isinstance(sort.field, str) or not sort.field.strip()):
            raise InvalidPayloadError("sort.field invalido")
        field = sort.field.strip() if isinstance(sort.field, str) else None
        return CatalogSort(field=field, direction=sort.direction)

    @staticmethod
    def _normalize_filters(filters: tuple[CatalogFilter, ...] | list[CatalogFilter] | None) -> tuple[CatalogFilter, ...]:
        if filters is None:
            return ()
        if not isinstance(filters, (tuple, list)):
            raise InvalidPayloadError("filters debe ser una lista o tuple de CatalogFilter")
        normalized: list[CatalogFilter] = []
        for item in filters:
            if not isinstance(item, CatalogFilter):
                raise InvalidPayloadError("filters debe contener CatalogFilter")
            if not isinstance(item.field, str) or not item.field.strip():
                raise InvalidPayloadError("CatalogFilter.field es requerido")
            normalized.append(item)
        return tuple(normalized)

    @staticmethod
    def _normalize_search_text(search_text: str | None) -> str | None:
        if search_text is None:
            return None
        normalized = str(search_text).strip()
        return normalized or None

    @staticmethod
    def _normalize_search_fields(search_fields: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
        if search_fields is None:
            return ()
        if not isinstance(search_fields, (tuple, list)):
            raise InvalidPayloadError("search_fields debe ser una lista o tuple de strings")
        normalized: list[str] = []
        for field_name in search_fields:
            if not isinstance(field_name, str) or not field_name.strip():
                raise InvalidPayloadError("search_fields debe contener strings no vacios")
            normalized.append(field_name.strip())
        return tuple(normalized)

    def _normalize_request(self, request: CatalogQueryRequest) -> CatalogQueryRequest:
        return CatalogQueryRequest(
            catalog_name=self._normalize_catalog_name(request.catalog_name),
            page=self._normalize_page(request.page),
            page_size=self._normalize_page_size(request.page_size),
            sort=self._normalize_sort(request.sort),
            search_text=self._normalize_search_text(request.search_text),
            search_fields=self._normalize_search_fields(request.search_fields),
            search_filters=self._normalize_filters(request.search_filters),
            filters=self._normalize_filters(request.filters),
        )

    def query_page(self, request: CatalogQueryRequest) -> CatalogPageResult:
        if not isinstance(request, CatalogQueryRequest):
            raise InvalidPayloadError("CatalogQueryRequest requerido")
        normalized = self._normalize_request(request)
        resolved = self._resolve_request(normalized)
        return self.query_repository.query_page(resolved)

    def list_page(
        self,
        catalog_name: str,
        *,
        page: int = 0,
        page_size: int = 20,
        sort: CatalogSort | None = None,
        search_text: str | None = None,
        search_fields: tuple[str, ...] | list[str] | None = None,
        filters: tuple[CatalogFilter, ...] | list[CatalogFilter] | None = None,
    ) -> CatalogPageResult:
        return self.query_page(
            CatalogQueryRequest(
                catalog_name=catalog_name,
                page=page,
                page_size=page_size,
                sort=self._normalize_sort(sort),
                search_text=self._normalize_search_text(search_text),
                search_fields=self._normalize_search_fields(search_fields),
                filters=self._normalize_filters(filters),
            )
        )

    def locate_record_page(
        self,
        catalog_name: str,
        record_id: int,
        *,
        page_size: int = 20,
        sort: CatalogSort | None = None,
        search_text: str | None = None,
        search_fields: tuple[str, ...] | list[str] | None = None,
        filters: tuple[CatalogFilter, ...] | list[CatalogFilter] | None = None,
    ) -> int | None:
        normalized_request = self._resolve_request(
            CatalogQueryRequest(
                catalog_name=self._normalize_catalog_name(catalog_name),
                page=0,
                page_size=self._normalize_page_size(page_size),
                sort=self._normalize_sort(sort),
                search_text=self._normalize_search_text(search_text),
                search_fields=self._normalize_search_fields(search_fields),
                filters=self._normalize_filters(filters),
            )
        )
        return self.query_repository.locate_record_page(
            normalized_request.catalog_name,
            self._normalize_record_id(record_id),
            page_size=normalized_request.page_size,
            sort=normalized_request.sort,
            search_text=normalized_request.search_text,
            search_fields=normalized_request.search_fields,
            search_filters=normalized_request.search_filters,
            filters=normalized_request.filters,
        )

    def lookup_reference_options(
        self,
        catalog_name: str,
        field_name: str,
        term: str | None = None,
        *,
        limit: int = _REFERENCE_OPTION_LOOKUP_LIMIT,
    ) -> list[dict[str, Any]]:
        field_schema = self.get_schema(catalog_name).field(field_name)
        reference = field_schema.reference
        if reference is None:
            return []
        service = self._require_reference_lookup_service()
        normalized_term = self._normalize_search_text(term) or ""
        if len(normalized_term) < reference.min_search_chars:
            return []
        options = service.search(reference.lookup_key, normalized_term, max(1, int(limit)))
        return [
            {"id": option.value, "value": option.value, "label": option.label}
            for option in options
            if option.value is not None
        ]

    def _resolve_request(self, request: CatalogQueryRequest) -> CatalogQueryRequest:
        schema = self.get_schema(request.catalog_name)
        resolved_filters: list[CatalogFilter] = []
        for filter_spec in request.filters:
            resolved_filters.extend(self._resolve_filter(schema, filter_spec))

        search_fields = request.search_fields or schema.search_fields
        resolved_search_fields: list[str] = []
        resolved_search_filters: list[CatalogFilter] = list(request.search_filters)
        if request.search_text is not None:
            for field_name in search_fields:
                field_schema = schema.field(field_name)
                reference = field_schema.reference
                if reference is None:
                    resolved_search_fields.append(field_name)
                    continue
                reference_ids = self._lookup_reference_ids(
                    reference,
                    request.search_text,
                    limit=_REFERENCE_FILTER_LOOKUP_LIMIT,
                    overflow_error=f"Refina la busqueda para {field_schema.label}.",
                )
                if reference_ids:
                    resolved_search_filters.append(
                        CatalogFilter(
                            field=field_schema.name,
                            operator=CatalogFilterOperator.IN,
                            value=reference_ids,
                        )
                    )

        if request.search_text is not None and not resolved_search_fields and not resolved_search_filters:
            resolved_search_filters.append(
                CatalogFilter(
                    field=schema.primary_key,
                    operator=CatalogFilterOperator.IN,
                    value=(),
                )
            )

        return CatalogQueryRequest(
            catalog_name=request.catalog_name,
            page=request.page,
            page_size=request.page_size,
            sort=request.sort,
            search_text=request.search_text,
            search_fields=tuple(resolved_search_fields),
            search_filters=tuple(resolved_search_filters),
            filters=tuple(resolved_filters),
        )

    def _resolve_filter(self, schema: CatalogSchemaDTO, filter_spec: CatalogFilter) -> tuple[CatalogFilter, ...]:
        field_schema = schema.field(filter_spec.field)
        reference = field_schema.reference
        if reference is None or filter_spec.operator not in {
            CatalogFilterOperator.EQ,
            CatalogFilterOperator.IN,
            CatalogFilterOperator.CONTAINS,
        }:
            return (filter_spec,)

        direct_ids = self._coerce_reference_ids(filter_spec.value)
        if direct_ids:
            if len(direct_ids) == 1 and filter_spec.operator != CatalogFilterOperator.IN:
                return (
                    CatalogFilter(
                        field=field_schema.name,
                        operator=CatalogFilterOperator.EQ,
                        value=direct_ids[0],
                    ),
                )
            return (
                CatalogFilter(
                    field=field_schema.name,
                    operator=CatalogFilterOperator.IN,
                    value=direct_ids,
                ),
            )

        search_term = self._reference_search_term(filter_spec.value)
        if search_term is None:
            return ()

        reference_ids = self._lookup_reference_ids(
            reference,
            search_term,
            limit=_REFERENCE_FILTER_LOOKUP_LIMIT,
            overflow_error=f"Refina el filtro para {field_schema.label}.",
        )
        return (
            CatalogFilter(
                field=field_schema.name,
                operator=CatalogFilterOperator.IN,
                value=reference_ids,
            ),
        )

    def _lookup_reference_ids(
        self,
        reference: ReferenceFieldDTO,
        term: str,
        *,
        limit: int,
        overflow_error: str,
    ) -> tuple[int, ...]:
        direct_ids = self._coerce_reference_ids(term)
        if direct_ids:
            return direct_ids

        service = self._require_reference_lookup_service()
        normalized_term = self._normalize_search_text(term)
        if normalized_term is None:
            return ()
        options = service.search(reference.lookup_key, normalized_term, max(1, int(limit)) + 1)
        if len(options) > limit:
            raise InvalidPayloadError(overflow_error)

        resolved: list[int] = []
        for option in options:
            value = option.value
            if isinstance(value, bool) or value in (None, ""):
                continue
            resolved.append(int(str(value)))
        return tuple(resolved)

    def _require_reference_lookup_service(self) -> ReferenceLookupService:
        if self.reference_lookup_service is None:
            raise RuntimeError("ReferenceLookupService no configurado")
        return self.reference_lookup_service

    @staticmethod
    def _reference_search_term(value: Any) -> str | None:
        if isinstance(value, Mapping):
            label = value.get("label")
            if label is not None:
                normalized = str(label).strip()
                return normalized or None
            term = value.get("term")
            if term is not None:
                normalized = str(term).strip()
                return normalized or None
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    @staticmethod
    def _coerce_reference_ids(value: Any) -> tuple[int, ...]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            resolved: list[int] = []
            for item in value:
                resolved.extend(ModeloCatalogQueryService._coerce_reference_ids(item))
            return tuple(resolved)
        if isinstance(value, Mapping):
            candidate = value.get("id", value.get("value"))
            if candidate is None:
                return ()
            return ModeloCatalogQueryService._coerce_reference_ids(candidate)
        if isinstance(value, bool):
            return ()
        if isinstance(value, int):
            return (int(value),)
        if isinstance(value, str) and value.strip().isdigit():
            return (int(value.strip()),)
        return ()
