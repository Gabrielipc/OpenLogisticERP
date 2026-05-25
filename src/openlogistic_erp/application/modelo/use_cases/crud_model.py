"""Thin CRUD use cases for workflow-owned modelo entities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....domain.modelo.dtos import CatalogRecordDTO
from ....domain.modelo.repositories.catalog import ModeloCatalogRepository
from ..contracts import InvalidIdentifierError, InvalidPayloadError


class _BaseModelCrudUseCase:
    def __init__(self, repository: ModeloCatalogRepository, model_name: str):
        self._repository = repository
        self._model_name = self._normalize_model_name(model_name)

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidPayloadError("Se requiere model_name")
        return model_name.strip().lower()

    @staticmethod
    def _validate_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("record_id debe ser entero positivo")
        return record_id

    @staticmethod
    def _validate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise InvalidPayloadError("Se requiere un payload tipo mapping")
        return dict(payload)


class ListModelUseCase(_BaseModelCrudUseCase):
    def execute(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        if filters is not None and not isinstance(filters, Mapping):
            raise InvalidPayloadError("filters debe ser un mapping")
        return self._repository.list_records(self._model_name, filters)


class GetModelUseCase(_BaseModelCrudUseCase):
    def execute(self, record_id: int) -> CatalogRecordDTO | None:
        record_id = self._validate_record_id(record_id)
        return self._repository.get_record(self._model_name, record_id)


class CreateModelUseCase(_BaseModelCrudUseCase):
    def execute(self, payload: Mapping[str, Any]) -> CatalogRecordDTO:
        data = self._validate_payload(payload)
        return self._repository.create_record(self._model_name, data)


class UpdateModelUseCase(_BaseModelCrudUseCase):
    def execute(self, payload) -> CatalogRecordDTO:
        if not isinstance(payload, Mapping):
            raise InvalidPayloadError("Se requiere payload para actualizar")

        data = dict(payload)
        record_id = data.get("id")
        if record_id is None:
            raise InvalidIdentifierError("Se requiere id para actualizar")

        record_id = self._validate_record_id(int(record_id))
        update_data = data.get("data", data.get("payload"))
        if update_data is None:
            update_data = {key: value for key, value in data.items() if key != "id"}
        update_data = self._validate_payload(update_data)
        return self._repository.update_record(self._model_name, record_id, update_data)


class DeleteModelUseCase(_BaseModelCrudUseCase):
    def execute(self, payload) -> bool:
        record_id = payload.get("id") if isinstance(payload, Mapping) else payload
        if record_id is None:
            raise InvalidIdentifierError("Se requiere id para eliminar")
        record_id = self._validate_record_id(int(record_id))
        return self._repository.delete_record(self._model_name, record_id)
