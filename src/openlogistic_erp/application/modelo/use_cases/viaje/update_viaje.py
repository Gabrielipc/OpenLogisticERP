"""Use case for updating viaje fields with controlled transaction."""

from __future__ import annotations

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import TipoViaje


class UpdateViajeUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        via_id = payload.get("id")
        data = payload.get("viaje", payload)
        if not via_id:
            raise ValueError("Se requiere id de viaje para actualizar")

        def _action(session):
            from .....infrastructure.persistence.modelo.workflow_orm import Viaje

            viaje = session.get(Viaje, int(via_id))
            if not viaje:
                raise ValueError(f"Viaje no encontrado: id={via_id}")

            for key, value in dict(data).items():
                if key == "id" or (
                    viaje.tipo_viaje == TipoViaje.VACIO and key in {"referencia", "descripcion"}
                ):
                    continue
                if hasattr(viaje, key):
                    setattr(viaje, key, value)

            session.add(viaje)
            return viaje

        return self._uow.run_in_transaction(_action)
