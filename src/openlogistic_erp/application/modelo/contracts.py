"""Common application contracts for the new modelo domain use cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from ...domain.modelo.dtos import CatalogPageDTO, CatalogRecordDTO, CatalogSchemaDTO, SimpleValue

I = TypeVar("I")  # noqa: E741
O = TypeVar("O")  # noqa: E741


class WorkflowRequiredError(ValueError):
    """Raised when a domain workflow model is requested through generic catalog operations."""


class InvalidIdentifierError(ValueError):
    """Raised when an entity identifier is missing or not valid."""


class InvalidPayloadError(ValueError):
    """Raised when a workflow payload is missing or malformed."""


@dataclass(frozen=True)
class UseCaseResult(Generic[O]):
    ok: bool
    payload: O | None = None
    error: str | None = None


class UseCase(Generic[I, O]):
    """Contract for application use-cases."""

    def execute(self, input_data: I) -> O:
        raise NotImplementedError


class CreateModelUseCase(UseCase[I, O], Generic[I, O]):
    pass


class UpdateModelUseCase(UseCase[I, O], Generic[I, O]):
    pass


class DeleteModelUseCase(UseCase[I, O], Generic[I, O]):
    pass


class UnitOfWorkExecutor:
    def run_in_transaction(self, fn: Callable[[Any], O]) -> O:
        raise NotImplementedError


class ModelRepositoryContract:
    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        raise NotImplementedError

    def list_records(
        self,
        model_name: str,
        filters: Mapping[str, SimpleValue] | None = None,
    ) -> list[CatalogRecordDTO]:
        raise NotImplementedError

    def get_record(self, model_name: str, record_id: int) -> CatalogRecordDTO | None:
        raise NotImplementedError

    def create_record(self, model_name: str, data: Mapping[str, SimpleValue]) -> CatalogRecordDTO:
        raise NotImplementedError

    def update_record(
        self,
        model_name: str,
        record_id: int,
        data: Mapping[str, SimpleValue],
    ) -> CatalogRecordDTO:
        raise NotImplementedError

    def delete_record(self, model_name: str, record_id: int) -> bool:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        raise NotImplementedError

    def query_page(self, request) -> CatalogPageDTO:
        raise NotImplementedError
