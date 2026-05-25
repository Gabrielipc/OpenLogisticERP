"""Use case to save section data for a detalle_operacion in one transaction."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import object_session

from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    ActividadThermo,
    Descarga,
    DetalleOperacion,
    EstadoViaje,
    GastoRealThermo,
    MovimientoCombustible,
    OrdenCombustible,
)
from ....common.uow import SQLAlchemyUnitOfWork


class UpdateDetalleOperacionSectionsUseCase:
    """Build/update section relationships for a detalle_operacion."""

    _SECTION_MAP = {
        "ActividadThermo": ("actividad_thermo", ActividadThermo, "one"),
        "MovimientoCombustible": ("movimientos_combustible", MovimientoCombustible, "many"),
        "OrdenCombustible": ("ordenes_combustible", OrdenCombustible, "many"),
        "Descarga": ("descarga", Descarga, "one"),
        "GastoRealThermo": ("gasto_real_thermo", GastoRealThermo, "one"),
        "actividad_thermo": ("actividad_thermo", ActividadThermo, "one"),
        "movimientos_combustible": ("movimientos_combustible", MovimientoCombustible, "many"),
        "ordenes_combustible": ("ordenes_combustible", OrdenCombustible, "many"),
        "descarga": ("descarga", Descarga, "one"),
        "gasto_real_thermo": ("gasto_real_thermo", GastoRealThermo, "one"),
    }

    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        payload = {} if payload is None else payload
        if isinstance(payload, Mapping):
            detalle_ref = (
                payload.get("detalle_operacion")
                or payload.get("entity")
                or payload.get("id")
                or payload.get("detalle_operacion_id")
            )
            sections_data = (
                payload.get("secciones_data")
                or payload.get("secciones")
                or payload.get("sections")
                or payload.get("section_data")
                or {}
            )
        else:
            detalle_ref = payload
            sections_data = {}

        def _action(session):
            detalle = self._load_detalle_operacion(session, detalle_ref)
            changed_sections = self._sync_sections(session, detalle, sections_data)
            if changed_sections:
                self._mark_viaje_en_curso(detalle)
            return detalle

        return self._uow.run_in_transaction(_action)

    def _load_detalle_operacion(self, session, detalle_ref: object):
        if isinstance(detalle_ref, DetalleOperacion):
            return self._attach_entity(session, detalle_ref)

        if detalle_ref is None:
            raise ValueError("Se requiere un detalle de operacion para guardar secciones")

        detalle_id = self._coerce_id(detalle_ref)
        detalle = session.get(DetalleOperacion, detalle_id)
        if detalle is None:
            raise ValueError(f"Detalle de operacion no encontrado: id={detalle_ref}")

        return detalle

    @staticmethod
    def _coerce_id(value: object) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        raise ValueError("Se requiere identificador valido de detalle de operacion")

    def _attach_entity(self, session, entity):
        current_session = object_session(entity)
        if current_session is None or current_session is not session:
            return session.merge(entity)
        return entity

    def _sync_sections(self, session, detalle: DetalleOperacion, sections_data):
        if not isinstance(sections_data, Mapping):
            return False

        changed_sections = False
        for section_key, section_payload in dict(sections_data).items():
            config = self._SECTION_MAP.get(section_key)
            if config is None:
                continue

            relation_name, model_cls, relation_kind = config
            if relation_kind == "one":
                changed_sections = (
                    self._sync_one(session, detalle, relation_name, model_cls, section_payload)
                    or changed_sections
                )
            else:
                changed_sections = (
                    self._sync_many(session, detalle, relation_name, model_cls, section_payload)
                    or changed_sections
                )

        return changed_sections

    def _sync_one(self, session, detalle: DetalleOperacion, relation_name: str, model_cls, section_data):
        if not isinstance(section_data, Mapping):
            return False

        current = getattr(detalle, relation_name)
        data = {k: v for k, v in section_data.items() if k != "id"}

        if current is not None:
            self._update_instance(current, data)
            return True

        setattr(detalle, relation_name, model_cls(**data))
        return True

    def _sync_many(self, session, detalle: DetalleOperacion, relation_name: str, model_cls, section_data):
        if not isinstance(section_data, list):
            return False

        collection = getattr(detalle, relation_name)
        if collection is None:
            setattr(detalle, relation_name, [])
            collection = getattr(detalle, relation_name)

        existing_by_id = {
            getattr(item, "id", None): item
            for item in list(collection)
            if getattr(item, "id", None) is not None
        }
        incoming_ids = {
            item.get("id")
            for item in section_data
            if isinstance(item, Mapping) and item.get("id") is not None
        }
        changed_sections = False

        for item in list(collection):
            item_id = getattr(item, "id", None)
            if item_id is not None and item_id not in incoming_ids:
                session.delete(item)
                if item in collection:
                    collection.remove(item)
                changed_sections = True

        for section_item in section_data:
            if not isinstance(section_item, Mapping):
                continue

            item_id = section_item.get("id")
            if item_id is not None and item_id in existing_by_id:
                self._update_instance(existing_by_id[item_id], section_item)
                changed_sections = True
                continue

            data = {k: v for k, v in section_item.items() if k != "id"}
            collection.append(model_cls(**data))
            changed_sections = True

        return changed_sections

    def _update_instance(self, instance, section_data):
        for attr, value in section_data.items():
            if attr == "id":
                continue
            if hasattr(instance, attr):
                setattr(instance, attr, value)

    @staticmethod
    def _mark_viaje_en_curso(detalle: DetalleOperacion):
        viaje = getattr(detalle, "viaje", None)
        if viaje is not None and viaje.estado == EstadoViaje.PENDIENTE:
            viaje.estado = EstadoViaje.ENCURSO

