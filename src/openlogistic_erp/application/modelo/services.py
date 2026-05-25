"""Application services and orchestration for Modelo domain."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.modelo.dtos import CatalogRecordDTO, CatalogSchemaDTO, FieldSchemaDTO, SimpleValue
from ...domain.modelo.field_validation import normalize_field_value
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from .circuito_service import CircuitoWorkflowService
from .contracts import InvalidIdentifierError, InvalidPayloadError, WorkflowRequiredError
from .detalle_operacion_service import DetalleOperacionWorkflowService
from .factura_service import FacturaWorkflowService
from .recibo_service import ReciboWorkflowService
from .viaje_service import ViajeWorkflowService


@dataclass(frozen=True)
class ModeloCatalogService:
    """Application facade for direct Modelo catalog operations."""

    repository: ModeloCatalogRepository
    protected_model_names: frozenset[str] = frozenset()

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name is required")
        return model_name.strip().lower()

    @staticmethod
    def _as_payload(data):
        from collections.abc import Mapping

        if not isinstance(data, Mapping):
            raise InvalidPayloadError("Se requiere un payload tipo mapping")
        return dict(data)

    def _validate_model(self, model_name: str) -> str:
        normalized = self._normalize_model_name(model_name)
        if normalized in {name.lower() for name in self.protected_model_names}:
            raise WorkflowRequiredError(f"El modelo '{normalized}' se maneja por su workflow, no por CRUD generico")
        return normalized

    @staticmethod
    def _field_index(schema: CatalogSchemaDTO) -> dict[str, FieldSchemaDTO]:
        return {field.name: field for field in schema.form_fields}

    def _normalize_payload(self, model_name: str, payload: dict[str, object]) -> dict[str, SimpleValue]:
        schema = self.repository.get_schema(model_name)
        field_index = self._field_index(schema)
        normalized_payload: dict[str, SimpleValue] = {}
        errors: list[str] = []

        for field_name, raw_value in payload.items():
            field_schema = field_index.get(field_name)
            if field_schema is None or field_schema.read_only or not field_schema.editable:
                errors.append(f"{field_name}: campo no permitido.")
                continue
            try:
                normalized_payload[field_name] = normalize_field_value(
                    kind=field_schema.kind,
                    value=raw_value,
                    required=field_schema.required,
                    nullable=field_schema.nullable,
                    options=field_schema.options,
                )
            except ValueError as exc:
                errors.append(f"{field_schema.label}: {exc}")

        if errors:
            raise InvalidPayloadError("Payload invalido. " + " ".join(errors))
        return normalized_payload

    @staticmethod
    def _validate_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("record_id debe ser entero positivo")
        return record_id

    def list_models(self) -> list[str]:
        return self.repository.list_models()

    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        normalized = self._validate_model(model_name)
        return self.repository.get_schema(normalized)

    def list(self, model_name: str, filters=None) -> list[CatalogRecordDTO]:
        normalized = self._validate_model(model_name)
        return self.repository.list_records(normalized, filters)

    def get(self, model_name: str, record_id: int) -> CatalogRecordDTO | None:
        normalized = self._validate_model(model_name)
        record_id = self._validate_record_id(record_id)
        return self.repository.get_record(normalized, record_id)

    def create(self, model_name: str, data: dict[str, SimpleValue]) -> CatalogRecordDTO:
        normalized = self._validate_model(model_name)
        payload = self._as_payload(data)
        payload = self._normalize_payload(normalized, payload)
        return self.repository.create_record(normalized, payload)

    def update(self, model_name: str, record_id: int, data: dict[str, SimpleValue]) -> CatalogRecordDTO:
        normalized = self._validate_model(model_name)
        record_id = self._validate_record_id(record_id)
        payload = self._as_payload(data)
        payload = self._normalize_payload(normalized, payload)
        return self.repository.update_record(normalized, record_id, payload)

    def delete(self, model_name: str, record_id: int) -> bool:
        normalized = self._validate_model(model_name)
        record_id = self._validate_record_id(record_id)
        return self.repository.delete_record(normalized, record_id)


@dataclass(frozen=True)
class ModeloWorkflowService:
    """Application orchestrator with dedicated workflow subservices."""

    catalog: ModeloCatalogService
    viaje: ViajeWorkflowService
    factura: FacturaWorkflowService
    recibo: ReciboWorkflowService
    circuito: CircuitoWorkflowService
    detalle_operacion: DetalleOperacionWorkflowService
