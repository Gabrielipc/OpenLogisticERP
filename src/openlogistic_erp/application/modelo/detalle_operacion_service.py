"""Domain service for DetalleOperacion use cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...domain.modelo.dtos import CatalogRecordDTO
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from ..common.uow import SQLAlchemyUnitOfWork
from ..modelo.use_cases import (
    CreateModelUseCase,
    DeleteModelUseCase,
    GetModelUseCase,
    ListModelUseCase,
    UpdateDetalleOperacionSectionsUseCase,
    UpdateModelUseCase,
)
from .contracts import InvalidIdentifierError, InvalidPayloadError


class DetalleOperacionWorkflowService:
    """Orchestrates detalle_operacion use cases."""

    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        list_detalle_operacion_use_case: ListModelUseCase,
        get_detalle_operacion_use_case: GetModelUseCase,
        create_detalle_operacion_use_case: CreateModelUseCase,
        update_detalle_operacion_use_case: UpdateModelUseCase,
        delete_detalle_operacion_use_case: DeleteModelUseCase,
        update_detalle_operacion_sections_use_case: UpdateDetalleOperacionSectionsUseCase,
    ):
        self.repository = repository
        self.unit_of_work = unit_of_work
        self.list_detalle_operacion_use_case = list_detalle_operacion_use_case
        self.get_detalle_operacion_use_case = get_detalle_operacion_use_case
        self.create_detalle_operacion_use_case = create_detalle_operacion_use_case
        self.update_detalle_operacion_use_case = update_detalle_operacion_use_case
        self.delete_detalle_operacion_use_case = delete_detalle_operacion_use_case
        self.update_detalle_operacion_sections_use_case = update_detalle_operacion_sections_use_case

    @staticmethod
    def _as_payload(payload: Mapping[str, object], *, message: str) -> dict[str, object]:
        if payload is None or not isinstance(payload, Mapping):
            raise InvalidPayloadError(message)
        return dict(payload)

    @staticmethod
    def _as_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("Se requiere identificador valido de detalle_operacion")
        return record_id

    def list(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        return self.list_detalle_operacion_use_case.execute(filters)

    def get(self, record_id: int) -> CatalogRecordDTO | None:
        return self.get_detalle_operacion_use_case.execute(self._as_record_id(record_id))

    def create(self, payload: Mapping[str, object]) -> CatalogRecordDTO:
        data = self._as_payload(payload, message="Se requiere payload para crear detalle de operacion")
        return self.create_detalle_operacion_use_case.execute(data)

    def update(self, record_id_or_payload, payload: Mapping[str, object] | None = None) -> CatalogRecordDTO:
        data = self._normalize_update_payload(record_id_or_payload, payload)
        return self.update_detalle_operacion_use_case.execute(data)

    def delete(self, payload: Mapping[str, object] | int) -> bool:
        if payload is None:
            raise InvalidIdentifierError("Se requiere identificador para eliminar detalle de operacion")
        return self.delete_detalle_operacion_use_case.execute(payload)

    def actualizar_secciones(self, detalle_operacion, secciones_data=None):
        if detalle_operacion is None:
            raise InvalidPayloadError("Se requiere detalle de operacion")
        if secciones_data is None:
            return self.update_detalle_operacion_sections_use_case.execute(detalle_operacion)
        return self.update_detalle_operacion_sections_use_case.execute(
            {
                "detalle_operacion": detalle_operacion,
                "secciones_data": secciones_data,
            }
        )

    def guardar_secciones_detalle_operacion(self, detalle_operacion, secciones_data=None):
        return self.actualizar_secciones(detalle_operacion, secciones_data)

    def _normalize_update_payload(self, record_id_or_payload, payload: Mapping[str, object] | None = None) -> dict[str, object]:
        if payload is None:
            if not isinstance(record_id_or_payload, Mapping):
                raise InvalidPayloadError("Se requiere payload para actualizar detalle de operacion")
            return dict(record_id_or_payload)

        record_id = self._as_record_id(record_id_or_payload)
        update_payload = self._as_payload(payload, message="Se requiere payload para actualizar detalle de operacion")
        return {"id": record_id, **update_payload}
