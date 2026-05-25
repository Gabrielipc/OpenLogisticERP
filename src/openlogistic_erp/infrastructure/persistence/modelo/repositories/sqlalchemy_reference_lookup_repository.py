"""SQLAlchemy-backed secure lookup repository for FK display fields."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Integer

from .....domain.modelo.dtos import ReferenceOptionDTO, SimpleValue
from .....domain.modelo.repositories.reference_lookup import ReferenceLookupRepository
from ..reference_profiles import DEFAULT_REFERENCE_PROFILES, ReferenceFieldProfile, ReferenceProfileRegistry


class SqlAlchemyReferenceLookupRepository(ReferenceLookupRepository):
    """Executes explicitly registered lookup functions in PostgreSQL."""

    def __init__(
        self,
        session_factory,
        reference_registry: ReferenceProfileRegistry | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._reference_registry = reference_registry or DEFAULT_REFERENCE_PROFILES

    @contextmanager
    def _new_session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _with_session(self, session: Session | None, action):
        if session is not None:
            return action(session)
        with self._new_session() as active_session:
            return action(active_session)

    def search(
        self,
        lookup_key: str,
        term: str,
        limit: int = 20,
        context: Mapping[str, SimpleValue] | None = None,
        *,
        session: Session | None = None,
    ) -> tuple[ReferenceOptionDTO, ...]:
        profile = self._reference_registry.lookup_profile(lookup_key)
        normalized_term = str(term or "")
        normalized_limit = max(1, int(limit))
        normalized_context = self._normalize_search_context(profile, context)

        def _execute(active_session: Session) -> tuple[ReferenceOptionDTO, ...]:
            params = {"term": normalized_term, "limit": normalized_limit, **normalized_context}
            placeholders = [":term", ":limit", *[f":{key}" for key in normalized_context]]
            stmt = text(f"SELECT id, label FROM {profile.search_function_name}({', '.join(placeholders)})")
            rows = active_session.execute(
                stmt,
                params,
            ).mappings()
            return tuple(
                ReferenceOptionDTO(value=row["id"], label=str(row["label"]))
                for row in rows
            )

        return self._with_session(session, _execute)

    def resolve_ids(
        self,
        lookup_key: str,
        ids: Sequence[SimpleValue],
        *,
        session: Session | None = None,
    ) -> dict[SimpleValue, ReferenceOptionDTO]:
        profile = self._reference_registry.lookup_profile(lookup_key)
        normalized_ids: tuple[int, ...] = tuple(
            self._normalize_id(value)
            for value in ids
            if value is not None and value != ""
        )
        if not normalized_ids:
            return {}

        def _execute(active_session: Session) -> dict[SimpleValue, ReferenceOptionDTO]:
            stmt = text(
                f"SELECT id, label FROM {profile.resolve_function_name}(:ids)"
            ).bindparams(bindparam("ids", type_=ARRAY(Integer())))
            rows = active_session.execute(stmt, {"ids": list(normalized_ids)}).mappings()
            return {
                row["id"]: ReferenceOptionDTO(value=row["id"], label=str(row["label"]))
                for row in rows
            }

        return self._with_session(session, _execute)

    def profile_for_catalog_field(self, catalog_name: str, field_name: str) -> ReferenceFieldProfile | None:
        return self._reference_registry.field_profile(catalog_name, field_name)

    @staticmethod
    def _normalize_id(value: SimpleValue) -> int:
        if isinstance(value, bool):
            raise ValueError("Boolean no es un id de referencia valido")
        return int(str(value))

    @staticmethod
    def _normalize_search_context(
        profile: ReferenceFieldProfile,
        context: Mapping[str, SimpleValue] | None,
    ) -> dict[str, SimpleValue]:
        if not profile.search_context_keys:
            return {}
        if context is None:
            return {key: None for key in profile.search_context_keys}
        normalized: dict[str, SimpleValue] = {}
        for key in profile.search_context_keys:
            normalized[key] = context.get(key)
        return normalized
