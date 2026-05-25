"""Use case to save section data for a circuito in one transaction."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import object_session

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import Circuito, GastoRealCamion, MovimientoAdicional


class UpdateCircuitoSectionsUseCase:
    """Build/update section relationships for a circuito."""

    _SECTION_MAP = {
        "GastoRealCamion": ("gasto_real_camion", GastoRealCamion, "one"),
        "MovimientoAdicional": ("movimientos_adicionales", MovimientoAdicional, "many"),
        "gasto_real_camion": ("gasto_real_camion", GastoRealCamion, "one"),
        "movimientos_adicionales": ("movimientos_adicionales", MovimientoAdicional, "many"),
    }

    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload):
        payload = {} if payload is None else payload
        if isinstance(payload, Mapping):
            circuito_ref = (
                payload.get("circuito")
                or payload.get("entity")
                or payload.get("id")
                or payload.get("circuito_id")
            )
            sections_data = (
                payload.get("secciones_data")
                or payload.get("secciones")
                or payload.get("sections")
                or payload.get("section_data")
                or {}
            )
        else:
            circuito_ref = payload
            sections_data = {}

        def _action(session):
            circuito = self._load_circuito(session, circuito_ref)
            self._sync_sections(session, circuito, sections_data)
            return circuito

        return self._uow.run_in_transaction(_action)

    def _load_circuito(self, session, circuito_ref: object):
        if isinstance(circuito_ref, Circuito):
            return self._attach_entity(session, circuito_ref)

        if circuito_ref is None:
            raise ValueError("Se requiere un circuito para guardar secciones")

        circuito_id = self._coerce_id(circuito_ref)
        circuito = session.get(Circuito, circuito_id)
        if circuito is None:
            raise ValueError(f"Circuito no encontrado: id={circuito_ref}")

        return circuito

    @staticmethod
    def _coerce_id(value: object) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        raise ValueError("Se requiere identificador valido de circuito")

    def _attach_entity(self, session, entity):
        current_session = object_session(entity)
        if current_session is None or current_session is not session:
            return session.merge(entity)
        return entity

    def _sync_sections(self, session, circuito: Circuito, sections_data):
        if not isinstance(sections_data, Mapping):
            return circuito

        for section_key, section_payload in dict(sections_data).items():
            config = self._SECTION_MAP.get(section_key)
            if config is None:
                continue

            relation_name, model_cls, relation_kind = config
            if relation_kind == "one":
                self._sync_one(session, circuito, relation_name, model_cls, section_payload)
            else:
                self._sync_many(session, circuito, relation_name, model_cls, section_payload)

    def _sync_one(self, session, circuito: Circuito, relation_name: str, model_cls, section_data):
        if not isinstance(section_data, Mapping):
            return

        current = getattr(circuito, relation_name)
        data = {k: v for k, v in section_data.items() if k != "id"}

        if current is not None:
            self._update_instance(current, data)
            return

        setattr(circuito, relation_name, model_cls(**data))

    def _sync_many(self, session, circuito: Circuito, relation_name: str, model_cls, section_data):
        if not isinstance(section_data, list):
            return

        collection = getattr(circuito, relation_name)
        if collection is None:
            setattr(circuito, relation_name, [])
            collection = getattr(circuito, relation_name)

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

        for item in list(collection):
            item_id = getattr(item, "id", None)
            if item_id is not None and item_id not in incoming_ids:
                session.delete(item)
                if item in collection:
                    collection.remove(item)

        for section_item in section_data:
            if not isinstance(section_item, Mapping):
                continue

            item_id = section_item.get("id")
            if item_id is not None and item_id in existing_by_id:
                self._update_instance(existing_by_id[item_id], section_item)
                continue

            data = {k: v for k, v in section_item.items() if k != "id"}
            collection.append(model_cls(**data))

    def _update_instance(self, instance, section_data):
        for attr, value in section_data.items():
            if attr == "id":
                continue
            if hasattr(instance, attr):
                setattr(instance, attr, value)

