"""Use case to delete a factura by id in one atomic transaction."""

from __future__ import annotations

from collections.abc import Mapping

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import Factura


class DeleteFacturaUseCase:
    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
    ):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        factura_id = payload.get("id") if isinstance(payload, Mapping) else payload
        if not factura_id:
            raise ValueError("Se requiere id de factura para eliminar")

        def _action(session):
            factura = session.get(Factura, int(factura_id))
            if not factura:
                raise ValueError(f"Factura no encontrada: id={factura_id}")
            session.delete(factura)
            return True

        return self._uow.run_in_transaction(_action)
