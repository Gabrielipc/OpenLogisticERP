"""Use case to evaluate and close a circuito with all invariants in one transaction."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import object_session

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import Circuito, EstadoCircuito, EstadoViaje, TipoViaje


class CloseCircuitoUseCase:
    """Close a circuito when its return trip is finalized."""

    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        payload = {} if payload is None else payload
        circuito_ref = self._resolve_circuito(payload)

        def _action(session):
            circuito = self._load_circuito(session, circuito_ref)
            return self._evaluate_closure(circuito)

        return self._uow.run_in_transaction(_action)

    def _resolve_circuito(self, payload):
        if isinstance(payload, Mapping):
            return (
                payload.get("circuito")
                or payload.get("entity")
                or payload.get("id")
                or payload.get("circuito_id")
            )
        return payload

    def _load_circuito(self, session, circuito_ref):
        if isinstance(circuito_ref, Circuito):
            return self._attach_entity(session, circuito_ref)

        if circuito_ref is None:
            raise ValueError("Se requiere un circuito para cerrar")

        circuito_id = int(circuito_ref)
        circuito = session.get(Circuito, circuito_id)
        if not circuito:
            raise ValueError(f"Circuito no encontrado: id={circuito_id}")

        return circuito

    def _attach_entity(self, session, entity):
        current_session = object_session(entity)
        if current_session is None or current_session is not session:
            return session.merge(entity)
        return entity

    def _evaluate_closure(self, circuito: Circuito) -> bool:
        return close_circuito_if_return_trip_finalized(circuito)


def close_circuito_if_return_trip_finalized(circuito: Circuito) -> bool:
    """Close a circuito when one of its return trips has already been finalized."""

    viaje_vuelta = None
    for viaje in circuito.viajes or []:
        if viaje.tipo_viaje in (TipoViaje.IMPOR, TipoViaje.VACIO):
            viaje_vuelta = viaje
            break

    if not viaje_vuelta or viaje_vuelta.estado != EstadoViaje.FINALIZADO:
        return False

    detalle = viaje_vuelta.detalle_operacion
    descarga = detalle.descarga if detalle is not None else None
    if descarga is not None:
        circuito.fecha_fin = descarga.fecha_descarga

    if circuito.fecha_fin is None:
        circuito.fecha_fin = viaje_vuelta.fecha_posicionamiento

    circuito.estado = EstadoCircuito.FINALIZADO
    return True
