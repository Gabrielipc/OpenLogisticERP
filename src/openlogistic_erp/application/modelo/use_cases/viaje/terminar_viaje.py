"""Use case to finish a viaje from a detalle_operacion flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy.orm import object_session

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    EstadoCamion,
    EstadoConductor,
    EstadoDetalle,
    EstadoViaje,
    TipoViaje,
    DetalleOperacion,
    Viaje,
)
from ..circuito.close_circuito import close_circuito_if_return_trip_finalized


class TerminarViajeUseCase:
    """Apply domain transition to mark a viaje and detalle as closed."""

    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        payload = {} if payload is None else payload
        if isinstance(payload, Mapping):
            viaje_ref = payload.get("viaje") or payload.get("entity") or payload.get("id") or payload.get("viaje_id")
            detalle_ref = payload.get("detalle_operacion") or payload.get("detalle_operacion_id")
        else:
            viaje_ref = payload
            detalle_ref = None

        def _action(session):
            viaje = self._load_viaje(session, viaje_ref)
            detalle = self._load_detalle(session, detalle_ref, viaje)
            self._transition(viaje, detalle)
            return viaje

        return self._uow.run_in_transaction(_action)

    def _load_viaje(self, session, viaje_ref: object):
        if isinstance(viaje_ref, Viaje):
            return self._attach_entity(session, viaje_ref)

        if viaje_ref is None:
            raise ValueError("Se requiere un viaje para terminarlo")

        viaje_id = self._coerce_id(viaje_ref)
        viaje = session.get(Viaje, viaje_id)
        if viaje is None:
            raise ValueError(f"Viaje no encontrado: id={viaje_ref}")
        return viaje

    def _load_detalle(self, session, detalle_ref, viaje: Viaje):
        if detalle_ref is not None:
            if isinstance(detalle_ref, DetalleOperacion):
                return self._attach_entity(session, detalle_ref)
            detalle = session.get(DetalleOperacion, self._coerce_id(detalle_ref))
            if detalle is None:
                raise ValueError(f"Detalle de operacion no encontrado: id={detalle_ref}")
            return detalle

        detalle = getattr(viaje, "detalle_operacion", None)
        if detalle is None:
            raise ValueError("El viaje no tiene detalle de operacion asociado")
        return detalle

    def _attach_entity(self, session, entity):
        current_session = object_session(entity)
        if current_session is None or current_session is not session:
            return session.merge(entity)
        return entity

    def _transition(self, viaje: Viaje, detalle: DetalleOperacion):
        tipo_viaje = cast(TipoViaje, viaje.tipo_viaje)

        if tipo_viaje == TipoViaje.EXPOR:
            self._release_conductor(viaje, EstadoConductor.INSTRUCCIONES)
            detalle.estado = EstadoDetalle.CERRADO
            viaje.estado = EstadoViaje.FINALIZADO
            return

        if tipo_viaje in (TipoViaje.IMPOR, TipoViaje.VACIO):
            self._release_conductor(viaje, EstadoConductor.DISPONIBLE)
            self._release_equipment(viaje.camion, EstadoCamion.ACTIVO)
            self._release_equipment(viaje.furgon, EstadoCamion.ACTIVO)
            self._release_equipment(viaje.thermo, EstadoCamion.ACTIVO)

            detalle.estado = EstadoDetalle.CERRADO
            viaje.estado = EstadoViaje.FINALIZADO
            self._close_circuito_if_return_trip(viaje)
            return

        raise ValueError(f"Tipo de viaje no soportado para terminar: {tipo_viaje}")

    @staticmethod
    def _coerce_id(value: object) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        raise ValueError("Se requiere identificador valido")

    def _release_conductor(self, viaje: Viaje, to_estado: EstadoConductor):
        conductor = viaje.conductor
        if conductor is None:
            return
        if cast(EstadoConductor, conductor.estado) == EstadoConductor.AGREGADO:
            return
        conductor.estado = to_estado

    def _release_equipment(self, equipment, to_estado: EstadoCamion):
        if equipment is None:
            return
        if cast(EstadoCamion, equipment.estado) == EstadoCamion.AGREGADO:
            return
        equipment.estado = to_estado

    @staticmethod
    def _close_circuito_if_return_trip(viaje: Viaje) -> None:
        circuito = getattr(viaje, "_circuito", None)
        if circuito is not None:
            close_circuito_if_return_trip_finalized(circuito)

