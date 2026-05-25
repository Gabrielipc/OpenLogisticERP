"""Application service for secure FK display lookups."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ...domain.modelo.dtos import ReferenceOptionDTO, SimpleValue
from ...domain.modelo.repositories.reference_lookup import ReferenceLookupRepository
from .contracts import InvalidPayloadError


@dataclass(frozen=True)
class ReferenceLookupService:
    """Application facade for secure FK lookups."""

    repository: ReferenceLookupRepository

    @staticmethod
    def _normalize_lookup_key(lookup_key: str) -> str:
        if not isinstance(lookup_key, str) or not lookup_key.strip():
            raise InvalidPayloadError("lookup_key is required")
        return lookup_key.strip().lower()

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        if not isinstance(limit, int) or limit <= 0:
            raise InvalidPayloadError("limit debe ser entero positivo")
        return limit

    def search(
        self,
        lookup_key: str,
        term: str,
        limit: int = 20,
        context: Mapping[str, SimpleValue] | None = None,
    ) -> tuple[ReferenceOptionDTO, ...]:
        normalized_key = self._normalize_lookup_key(lookup_key)
        normalized_term = str(term or "")
        normalized_limit = self._normalize_limit(limit)
        normalized_context = self._normalize_context(context)
        return self.repository.search(normalized_key, normalized_term, normalized_limit, normalized_context)

    @staticmethod
    def _normalize_context(context: Mapping[str, SimpleValue] | None) -> dict[str, SimpleValue] | None:
        if context is None:
            return None
        if not isinstance(context, Mapping):
            raise InvalidPayloadError("context debe ser mapping o None")
        normalized: dict[str, SimpleValue] = {}
        for key, value in context.items():
            normalized_key = str(key or "").strip()
            if not normalized_key:
                raise InvalidPayloadError("context contiene clave invalida")
            normalized[normalized_key] = value
        return normalized

    def resolve_ids(
        self,
        lookup_key: str,
        ids: tuple[SimpleValue, ...] | list[SimpleValue],
    ) -> dict[SimpleValue, ReferenceOptionDTO]:
        normalized_key = self._normalize_lookup_key(lookup_key)
        if not isinstance(ids, (tuple, list)):
            raise InvalidPayloadError("ids debe ser lista o tuple")
        normalized_ids = tuple(item for item in ids if item is not None)
        if not normalized_ids:
            return {}
        return self.repository.resolve_ids(normalized_key, normalized_ids)
