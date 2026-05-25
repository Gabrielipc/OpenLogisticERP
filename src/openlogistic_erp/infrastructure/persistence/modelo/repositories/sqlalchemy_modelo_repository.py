"""SQLAlchemy-based repository for Modelo entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....domain.modelo.dtos import CatalogRecordDTO, CatalogSchemaDTO, SimpleValue
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from ..catalog_schema import build_catalog_schema, deserialize_record_input, row_to_record
from ..models import Base
from ..reference_profiles import DEFAULT_REFERENCE_PROFILES, ReferenceProfileRegistry
from .integrity_errors import translate_integrity_error


class _UnknownModelError(LookupError):
    pass


class SqlAlchemyModeloRepository(ModeloCatalogRepository):
    def __init__(
        self,
        session_factory,
        reference_registry: ReferenceProfileRegistry | None = None,
    ):
        self._session_factory = session_factory
        self._reference_registry = reference_registry or DEFAULT_REFERENCE_PROFILES

    def list_models(self) -> list[str]:
        return sorted(self._model_index_by_name().keys())

    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        model_cls = self._resolve_model(model_name)
        return build_catalog_schema(
            model_cls,
            catalog_name=str(model_name).lower(),
            reference_registry=self._reference_registry,
        )

    def list_records(
        self,
        model_name: str,
        filters: Mapping[str, SimpleValue] | None = None,
        session: Session | None = None,
    ) -> list[CatalogRecordDTO]:
        def _execute(active_session: Session) -> list[CatalogRecordDTO]:
            model_cls = self._resolve_model(model_name)
            stmt = select(model_cls)
            if filters:
                for key, value in filters.items():
                    col = getattr(model_cls, key, None)
                    if col is None:
                        continue
                    stmt = stmt.where(col == deserialize_record_input(model_cls, {key: value})[key])
            rows = active_session.execute(stmt).scalars().all()
            normalized_name = str(model_name).lower()
            return [row_to_record(normalized_name, row) for row in rows]

        return self._with_session(session, _execute)

    def get_record(
        self,
        model_name: str,
        record_id: int,
        session: Session | None = None,
    ) -> CatalogRecordDTO | None:
        def _execute(active_session: Session) -> CatalogRecordDTO | None:
            model_cls = self._resolve_model(model_name)
            pk_column = self._pk_column(model_cls)
            row = active_session.execute(select(model_cls).where(pk_column == record_id)).scalar_one_or_none()
            if row is None:
                return None
            return row_to_record(str(model_name).lower(), row)

        return self._with_session(session, _execute)

    def create_record(
        self,
        model_name: str,
        data: Mapping[str, SimpleValue],
        session: Session | None = None,
    ) -> CatalogRecordDTO:
        def _execute(active_session: Session) -> CatalogRecordDTO:
            model_cls = self._resolve_model(model_name)
            row = model_cls(**deserialize_record_input(model_cls, data))
            active_session.add(row)
            active_session.flush()
            return row_to_record(str(model_name).lower(), row)

        return self._execute_write(model_name, session, _execute)

    def update_record(
        self,
        model_name: str,
        record_id: int,
        data: Mapping[str, SimpleValue],
        session: Session | None = None,
    ) -> CatalogRecordDTO:
        def _execute(active_session: Session) -> CatalogRecordDTO:
            model_cls = self._resolve_model(model_name)
            pk_column = self._pk_column(model_cls)
            row = active_session.execute(select(model_cls).where(pk_column == record_id)).scalar_one_or_none()
            if row is None:
                raise _UnknownModelError(f"Registro no encontrado para {model_name} id={record_id}")
            payload = deserialize_record_input(model_cls, data)
            for key, value in payload.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            active_session.add(row)
            active_session.flush()
            return row_to_record(str(model_name).lower(), row)

        return self._execute_write(model_name, session, _execute)

    def delete_record(self, model_name: str, record_id: int, session: Session | None = None) -> bool:
        def _execute(active_session: Session) -> bool:
            model_cls = self._resolve_model(model_name)
            pk_column = self._pk_column(model_cls)
            row = active_session.execute(select(model_cls).where(pk_column == record_id)).scalar_one_or_none()
            if row is None:
                return False
            active_session.delete(row)
            return True

        return self._with_session(session, _execute)

    @contextmanager
    def _new_session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _with_session(self, session: Session | None, fn: Callable[[Session], Any]) -> Any:
        if session is not None:
            return fn(session)

        with self._new_session() as active_session:
            result = fn(active_session)
            active_session.commit()
            return result

    def _execute_write(
        self,
        model_name: str,
        session: Session | None,
        fn: Callable[[Session], CatalogRecordDTO],
    ) -> CatalogRecordDTO:
        if session is not None:
            try:
                return fn(session)
            except IntegrityError as exc:
                session.rollback()
                raise translate_integrity_error(model_name, exc) from exc

        with self._new_session() as active_session:
            try:
                result = fn(active_session)
                active_session.commit()
                return result
            except IntegrityError as exc:
                active_session.rollback()
                raise translate_integrity_error(model_name, exc) from exc
            except Exception:
                active_session.rollback()
                raise

    def _resolve_model(self, model_name: str):
        model_index = self._model_index_by_name()
        normalized = str(model_name).lower()
        if normalized not in model_index:
            raise _UnknownModelError(f"Modelo no registrado: {model_name}")
        return model_index[normalized]

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

    def _pk_column(self, model_cls):
        keys = model_cls.__mapper__.primary_key
        if not keys:
            raise _UnknownModelError(f"Modelo '{model_cls.__name__}' no tiene PK")
        return keys[0]

