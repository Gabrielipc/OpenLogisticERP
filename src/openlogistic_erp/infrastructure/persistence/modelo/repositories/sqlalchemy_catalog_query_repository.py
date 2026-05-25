"""SQLAlchemy query repository for catalog list screens."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import String, cast, false, func, or_, select
from sqlalchemy.orm import RelationshipProperty, joinedload
from sqlalchemy.orm.attributes import InstrumentedAttribute

from .....domain.modelo.catalog_queries import (
    CatalogFilter,
    CatalogFilterOperator,
    CatalogPageResult,
    CatalogQueryRequest,
    CatalogSort,
    CatalogSortDirection,
)
from .....domain.modelo.dtos import CatalogRecordDTO, CatalogSchemaDTO
from .....domain.modelo.repositories.catalog_queries import CatalogQueryRepository
from ..catalog_schema import build_catalog_schema, deserialize_record_input, row_to_record
from ..models import Base
from ..reference_profiles import DEFAULT_REFERENCE_PROFILES, ReferenceProfileRegistry
from .sqlalchemy_reference_lookup_repository import SqlAlchemyReferenceLookupRepository
from .circuito_catalog import circuito_synthetic_search_clause, serialize_circuito_catalog_row


@dataclass(frozen=True)
class CatalogQueryProfile:
    """Infrastructure-only query profile for a catalog."""

    eager_load_paths: tuple[str, ...] = ()
    allowed_filter_fields: frozenset[str] | None = None
    allowed_sort_fields: frozenset[str] | None = None
    row_transformer: Callable[[Any], dict[str, Any]] | None = None
    visible_columns: tuple[str, ...] | None = None
    synthetic_search_clause_factory: Callable[[str, str], Any | None] | None = None


@dataclass(frozen=True)
class _ResolvedCatalogProfile:
    model_cls: type
    eager_load_paths: tuple[str, ...]
    allowed_filter_fields: frozenset[str] | None
    allowed_sort_fields: frozenset[str] | None
    row_transformer: Callable[[Any], dict[str, Any]] | None
    visible_columns: tuple[str, ...] | None
    synthetic_search_clause_factory: Callable[[str, str], Any | None] | None


class _UnknownCatalogError(LookupError):
    pass


class SqlAlchemyCatalogQueryRepository(CatalogQueryRepository):
    def __init__(
        self,
        session_factory,
        profiles: Mapping[str, CatalogQueryProfile] | None = None,
        reference_registry: ReferenceProfileRegistry | None = None,
        reference_lookup_repository: SqlAlchemyReferenceLookupRepository | None = None,
    ):
        self._session_factory = session_factory
        self._profiles = {
            **_default_catalog_query_profiles(),
            **{str(key).lower(): value for key, value in (profiles or {}).items()},
        }
        self._reference_registry = reference_registry or DEFAULT_REFERENCE_PROFILES
        self._reference_lookup_repository = reference_lookup_repository or SqlAlchemyReferenceLookupRepository(
            session_factory,
            reference_registry=self._reference_registry,
        )

    def query_page(self, request: CatalogQueryRequest) -> CatalogPageResult:
        with self._new_session() as session:
            profile = self._resolve_profile(request.catalog_name)
            stmt = select(profile.model_cls)
            stmt = self._apply_loader_options(stmt, profile)
            stmt = self._apply_search(stmt, profile, request)
            stmt = self._apply_filters(stmt, profile, request.filters)

            total_count = session.execute(
                select(func.count()).select_from(stmt.order_by(None).subquery())
            ).scalar_one()

            stmt = self._apply_sort(stmt, profile, request)
            stmt = stmt.offset(request.page * request.page_size).limit(request.page_size)
            rows = session.execute(stmt).unique().scalars().all()
            resolved_labels = self._resolve_reference_labels(session, request.catalog_name, rows)
            serialized = tuple(
                self._serialize_row(profile, request.catalog_name, row, resolved_labels=resolved_labels)
                for row in rows
            )

            return CatalogPageResult(
                rows=serialized,
                total_count=int(total_count),
                page=request.page,
                page_size=request.page_size,
            )

    def get_schema(self, catalog_name: str) -> CatalogSchemaDTO:
        profile = self._resolve_profile(catalog_name)
        return build_catalog_schema(
            profile.model_cls,
            catalog_name=str(catalog_name).lower(),
            reference_registry=self._reference_registry,
        )

    def locate_record_page(
        self,
        catalog_name: str,
        record_id: int,
        *,
        page_size: int,
        sort: CatalogSort | None = None,
        search_text: str | None = None,
        search_fields: Sequence[str] | None = None,
        search_filters: Sequence[CatalogFilter] | None = None,
        filters: Sequence[CatalogFilter] | None = None,
    ) -> int | None:
        request = CatalogQueryRequest(
            catalog_name=str(catalog_name).lower(),
            page=0,
            page_size=int(page_size),
            sort=sort or CatalogSort(),
            search_text=str(search_text).strip() if isinstance(search_text, str) and search_text.strip() else None,
            search_fields=tuple(str(field_name).strip() for field_name in (search_fields or ()) if str(field_name).strip()),
            search_filters=tuple(search_filters or ()),
            filters=tuple(filters or ()),
        )
        with self._new_session() as session:
            profile = self._resolve_profile(request.catalog_name)
            primary_key = self._primary_key_column(profile.model_cls)
            if primary_key is None:
                return None

            ranked_stmt = select(
                primary_key.label("record_id"),
                func.row_number().over(order_by=self._ordering_clauses(profile, request)).label("row_number"),
            ).select_from(profile.model_cls)
            ranked_stmt = self._apply_search(ranked_stmt, profile, request)
            ranked_stmt = self._apply_filters(ranked_stmt, profile, request.filters)
            ranked_rows = ranked_stmt.subquery()
            row_number = session.execute(
                select(ranked_rows.c.row_number).where(ranked_rows.c.record_id == int(record_id))
            ).scalar_one_or_none()
            if row_number is None:
                return None
            return max(0, (int(row_number) - 1) // int(page_size))

    @contextmanager
    def _new_session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _resolve_profile(self, catalog_name: str) -> _ResolvedCatalogProfile:
        normalized = str(catalog_name).lower()
        model_cls = self._resolve_model(normalized)
        profile = self._profiles.get(normalized, CatalogQueryProfile())
        return _ResolvedCatalogProfile(
            model_cls=model_cls,
            eager_load_paths=profile.eager_load_paths,
            allowed_filter_fields=profile.allowed_filter_fields,
            allowed_sort_fields=profile.allowed_sort_fields,
            row_transformer=profile.row_transformer,
            visible_columns=profile.visible_columns,
            synthetic_search_clause_factory=profile.synthetic_search_clause_factory,
        )

    def _resolve_model(self, catalog_name: str):
        model_index = self._model_index_by_name()
        if catalog_name not in model_index:
            raise _UnknownCatalogError(f"Modelo no registrado: {catalog_name}")
        return model_index[catalog_name]

    def _model_index_by_name(self) -> dict[str, type]:
        index: dict[str, type] = {}
        for mapper in Base.registry.mappers:
            cls = mapper.class_
            class_name = cls.__name__.lower()
            table_name = getattr(cls, "__tablename__", cls.__name__).lower()
            index[class_name] = cls
            if table_name not in index or cls.__mapper__.inherits is None:
                index[table_name] = cls
        return index

    def _apply_loader_options(self, stmt, profile: _ResolvedCatalogProfile):
        for path in profile.eager_load_paths:
            option = self._build_loader_option(profile.model_cls, path)
            if option is not None:
                stmt = stmt.options(option)
        return stmt

    def _build_loader_option(self, model_cls: type, rel_path: str):
        segments = [segment for segment in str(rel_path).split(".") if segment]
        if not segments:
            return None

        current_cls = model_cls
        first = getattr(current_cls, segments[0], None)
        if not isinstance(first, InstrumentedAttribute) or not isinstance(getattr(first, "property", None), RelationshipProperty):
            return None

        option = joinedload(first)
        loader = option
        current_cls = first.property.mapper.class_
        for segment in segments[1:]:
            attr = getattr(current_cls, segment, None)
            if not isinstance(attr, InstrumentedAttribute) or not isinstance(getattr(attr, "property", None), RelationshipProperty):
                return None
            loader = loader.joinedload(attr)
            current_cls = attr.property.mapper.class_
        return option

    def _apply_filters(self, stmt, profile: _ResolvedCatalogProfile, filters: Sequence[CatalogFilter]):
        for filter_spec in filters:
            stmt = stmt.where(self._filter_clause(profile, filter_spec))
        return stmt

    def _apply_search(self, stmt, profile: _ResolvedCatalogProfile, request: CatalogQueryRequest):
        if request.search_text is None:
            return stmt
        clauses = self._search_clauses(profile, request)
        if not clauses:
            return stmt.where(false())
        return stmt.where(or_(*clauses))

    def _search_clauses(self, profile: _ResolvedCatalogProfile, request: CatalogQueryRequest) -> list[Any]:
        clauses: list[Any] = []
        for field_name in request.search_fields:
            self._ensure_allowed_field(field_name, profile.allowed_filter_fields, kind="search")
            column = self._resolve_query_column(profile.model_cls, field_name)
            if column is None:
                synthetic_clause = (
                    profile.synthetic_search_clause_factory(field_name, request.search_text)
                    if profile.synthetic_search_clause_factory is not None
                    else None
                )
                if synthetic_clause is None:
                    raise ValueError(f"Campo de search no valido: {field_name}")
                clauses.append(synthetic_clause)
                continue
            clauses.append(cast(column, String).ilike(f"%{request.search_text}%"))
        for filter_spec in request.search_filters:
            clauses.append(self._filter_clause(profile, filter_spec))
        return clauses

    def _filter_clause(self, profile: _ResolvedCatalogProfile, filter_spec: CatalogFilter):
        self._ensure_allowed_field(filter_spec.field, profile.allowed_filter_fields, kind="filter")
        column = self._resolve_query_column(profile.model_cls, filter_spec.field)
        if column is None:
            raise ValueError(f"Campo de filtro no valido: {filter_spec.field}")

        normalized_filter = deserialize_record_input(profile.model_cls, {filter_spec.field: filter_spec.value})
        filter_value = normalized_filter.get(filter_spec.field)
        normalized_filter_to = deserialize_record_input(profile.model_cls, {filter_spec.field: filter_spec.value_to})
        filter_value_to = normalized_filter_to.get(filter_spec.field)

        if filter_spec.operator == CatalogFilterOperator.EQ:
            return column == filter_value
        if filter_spec.operator == CatalogFilterOperator.CONTAINS:
            return cast(column, String).ilike(f"%{filter_spec.value}%")
        if filter_spec.operator == CatalogFilterOperator.IN:
            values = filter_spec.value if isinstance(filter_spec.value, (list, tuple, set, frozenset)) else [filter_spec.value]
            if not values:
                return false()
            normalized_values = [
                deserialize_record_input(profile.model_cls, {filter_spec.field: item})[filter_spec.field]
                for item in values
            ]
            if not normalized_values:
                return false()
            return column.in_(list(normalized_values))
        if filter_spec.operator == CatalogFilterOperator.GTE:
            return column >= filter_value
        if filter_spec.operator == CatalogFilterOperator.LTE:
            return column <= filter_value
        if filter_spec.operator == CatalogFilterOperator.BETWEEN:
            return column.between(filter_value, filter_value_to)
        raise ValueError(f"Operador no soportado: {filter_spec.operator}")

    def _apply_sort(self, stmt, profile: _ResolvedCatalogProfile, request: CatalogQueryRequest):
        return stmt.order_by(*self._ordering_clauses(profile, request))

    def _ordering_clauses(self, profile: _ResolvedCatalogProfile, request: CatalogQueryRequest) -> list[Any]:
        primary_key = self._primary_key_column(profile.model_cls)
        if primary_key is None:
            return []

        sort_field = request.sort.field
        direction = request.sort.direction
        clauses: list[Any] = []

        if sort_field:
            self._ensure_allowed_field(sort_field, profile.allowed_sort_fields, kind="sort")
            column = self._resolve_query_column(profile.model_cls, sort_field)
            if column is None:
                raise ValueError(f"Campo de sort no valido: {sort_field}")
            clauses.append(column.desc() if direction == CatalogSortDirection.DESC else column.asc())
            if sort_field == primary_key.key:
                return clauses

        clauses.append(primary_key.desc() if direction == CatalogSortDirection.DESC else primary_key.asc())
        return clauses

    @staticmethod
    def _primary_key_column(model_cls: type):
        primary_keys = tuple(model_cls.__table__.primary_key.columns)
        if not primary_keys:
            return None
        return primary_keys[0]

    @staticmethod
    def _ensure_allowed_field(field_name: str, allowed: frozenset[str] | None, *, kind: str):
        if allowed is not None and field_name not in allowed:
            raise ValueError(f"Campo de {kind} no permitido: {field_name}")

    @staticmethod
    def _resolve_query_column(model_cls: type, field_name: str):
        attribute = getattr(model_cls, field_name, None)
        if isinstance(attribute, InstrumentedAttribute):
            return attribute
        return model_cls.__table__.columns.get(field_name)

    def _resolve_reference_labels(
        self,
        session,
        catalog_name: str,
        rows: Sequence[Any],
    ) -> dict[str, dict[Any, str]]:
        profiles = self._reference_registry.profiles_for_catalog(catalog_name)
        if not profiles or not rows:
            return {}

        resolved: dict[str, dict[Any, str]] = {}
        for field_profile in profiles:
            ids = tuple(
                getattr(row, field_profile.field_name, None)
                for row in rows
                if getattr(row, field_profile.field_name, None) is not None
            )
            if not ids:
                continue
            matches = self._reference_lookup_repository.resolve_ids(
                field_profile.lookup_key,
                ids,
                session=session,
            )
            resolved[field_profile.display_field_key] = {
                key: option.label for key, option in matches.items()
            }
        return resolved

    def _serialize_row(
        self,
        profile: _ResolvedCatalogProfile,
        catalog_name: str,
        row: Any,
        *,
        resolved_labels: Mapping[str, Mapping[Any, str]] | None = None,
    ) -> CatalogRecordDTO:
        if profile.row_transformer is not None:
            record = CatalogRecordDTO(catalog_name=str(catalog_name).lower(), values=dict(profile.row_transformer(row)))
        else:
            record = row_to_record(str(catalog_name).lower(), row)

        if resolved_labels:
            updates: dict[str, Any] = {}
            for field_profile in self._reference_registry.profiles_for_catalog(catalog_name):
                raw_id = record.get(field_profile.field_name)
                updates[field_profile.display_field_key] = resolved_labels.get(
                    field_profile.display_field_key,
                    {},
                ).get(raw_id)
            if updates:
                record = record.with_values(**updates)

        if profile.visible_columns is None:
            return record

        visible = {
            column_name: record.get(column_name)
            for column_name in profile.visible_columns
            if column_name in record
        }
        return CatalogRecordDTO(catalog_name=record.catalog_name, values=visible)


def _default_catalog_query_profiles() -> dict[str, CatalogQueryProfile]:
    return {
        "circuito": CatalogQueryProfile(
            eager_load_paths=(
                "viajes.conductor",
                "viajes._ruta.origen",
                "viajes._ruta.destino",
            ),
            row_transformer=serialize_circuito_catalog_row,
            synthetic_search_clause_factory=circuito_synthetic_search_clause,
        )
    }
