"""Use case to delete circuito and its related viajes atomically."""

from __future__ import annotations

from collections.abc import Mapping

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import Circuito
from ...contracts import InvalidIdentifierError


class DeleteCircuitoUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload) -> bool:
        circuito_id = payload.get("id") if isinstance(payload, Mapping) else payload
        if not isinstance(circuito_id, int) or circuito_id <= 0:
            raise InvalidIdentifierError("Se requiere id de circuito para eliminar")

        def _action(session):
            circuito = session.get(Circuito, circuito_id)
            if circuito is None:
                raise ValueError(f"Circuito no encontrado: id={circuito_id}")

            for viaje in list(circuito.viajes or []):
                session.delete(viaje)

            session.flush()
            session.delete(circuito)
            return True

        return self._uow.run_in_transaction(_action)
