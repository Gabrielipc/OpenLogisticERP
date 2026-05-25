"""Repository contracts for Modelo module."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from ..dtos import CatalogPageDTO, CatalogRecordDTO, CatalogSchemaDTO, SimpleValue


class ModeloCatalogRepository(Protocol):
    """Contract used by application services to access Modelo tables."""

    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        ...

    def list_records(
        self,
        model_name: str,
        filters: Mapping[str, SimpleValue] | None = None,
    ) -> list[CatalogRecordDTO]:
        ...

    def get_record(self, model_name: str, record_id: int) -> CatalogRecordDTO | None:
        ...

    def create_record(self, model_name: str, data: Mapping[str, SimpleValue]) -> CatalogRecordDTO:
        ...

    def update_record(
        self,
        model_name: str,
        record_id: int,
        data: Mapping[str, SimpleValue],
    ) -> CatalogRecordDTO:
        ...

    def delete_record(self, model_name: str, record_id: int) -> bool:
        ...

    def list_models(self) -> list[str]:
        ...


class CatalogSchemaProvider(Protocol):
    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        ...


class CatalogDataGateway(Protocol):
    def list_records(
        self,
        model_name: str,
        filters: Mapping[str, SimpleValue] | None = None,
    ) -> list[CatalogRecordDTO]:
        ...

    def get_record(self, model_name: str, record_id: int) -> CatalogRecordDTO | None:
        ...

    def create_record(self, model_name: str, data: Mapping[str, SimpleValue]) -> CatalogRecordDTO:
        ...

    def update_record(
        self,
        model_name: str,
        record_id: int,
        data: Mapping[str, SimpleValue],
    ) -> CatalogRecordDTO:
        ...

    def delete_record(self, model_name: str, record_id: int) -> bool:
        ...

    def query_page(self, request) -> CatalogPageDTO:
        ...
