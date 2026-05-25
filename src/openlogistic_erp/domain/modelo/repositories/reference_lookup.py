"""Repository contracts for secure FK display lookups."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from ..dtos import ReferenceOptionDTO, SimpleValue


class ReferenceLookupRepository(Protocol):
    """Read-only contract for secure FK display lookups."""

    def search(
        self,
        lookup_key: str,
        term: str,
        limit: int = 20,
        context: Mapping[str, SimpleValue] | None = None,
    ) -> tuple[ReferenceOptionDTO, ...]:
        ...

    def resolve_ids(
        self,
        lookup_key: str,
        ids: tuple[SimpleValue, ...] | list[SimpleValue],
    ) -> dict[SimpleValue, ReferenceOptionDTO]:
        ...
