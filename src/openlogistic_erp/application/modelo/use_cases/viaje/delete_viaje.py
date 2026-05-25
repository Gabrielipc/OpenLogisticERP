"""Use case for deleting viaje with side effects for equipment availability."""

from __future__ import annotations

from sqlalchemy import func, select

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    Camion,
    Conductor,
    EstadoCamion,
    EstadoConductor,
    Furgon,
    Thermo,
    Viaje,
)
from ..circuito.delete_empty_circuito import DeleteEmptyCircuitoRule


class DeleteViajeUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work
        self._delete_empty_circuito = DeleteEmptyCircuitoRule()

    def execute(self, payload):
        viaje_id = payload.get("id") if isinstance(payload, dict) else payload
        if not viaje_id:
            raise ValueError("Se requiere id de viaje para eliminar")

        def _action(session):
            viaje = session.get(Viaje, int(viaje_id))
            if not viaje:
                raise ValueError(f"Viaje no encontrado: id={viaje_id}")
            circuito_id = int(viaje._circuito_id) if viaje._circuito_id is not None else None

            self._release_entity(session, Conductor, viaje.conductor_id, EstadoConductor.DISPONIBLE, "conductor_id")
            self._release_entity(session, Camion, viaje.camion_id, EstadoCamion.ACTIVO, "camion_id")
            self._release_entity(session, Furgon, viaje.furgon_id, EstadoCamion.ACTIVO, "furgon_id")
            self._release_entity(session, Thermo, viaje.thermo_id, EstadoCamion.ACTIVO, "thermo_id")

            session.delete(viaje)
            session.flush()
            self._delete_empty_circuito.delete_if_empty(session, circuito_id)
            return True

        return self._uow.run_in_transaction(_action)

    def _release_entity(self, session, model, entity_id: int | None, available_state, fk_attr: str):
        if entity_id is None:
            return

        stmt = select(func.count()).select_from(Viaje).where(getattr(Viaje, fk_attr) == entity_id)
        used_count = session.execute(stmt).scalar() or 0
        if used_count <= 1:
            entity = session.get(model, entity_id)
            if entity is not None:
                entity.estado = available_state
