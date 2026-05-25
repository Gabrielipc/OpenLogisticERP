"""Domain service for Recibo use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ...domain.modelo.dtos import CatalogRecordDTO
from ...domain.modelo.field_validation import format_field_value_for_ui
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from ...infrastructure.persistence.modelo.workflow_orm import EstadoFactura, Factura, Moneda, Recibo, ReciboFactura
from ..common.uow import SQLAlchemyUnitOfWork
from ..modelo.use_cases import (
    CreateReciboConAplicacionesUseCase,
    DeleteReciboUseCase,
    GetModelUseCase,
    ListModelUseCase,
    UpdateReciboUseCase,
)
from .contracts import InvalidIdentifierError, InvalidPayloadError
from .workflow_dtos import CreateReciboCommand, UpdateReciboCommand

_RECIBO_COBRABLE_STATES = (
    EstadoFactura.PENDIENTE,
    EstadoFactura.PAGADAPAR,
    EstadoFactura.ATRASADA,
    EstadoFactura.PROXIMA_A_VENCER,
)


def _money_text(value: Any) -> str:
    return format(float(value or 0), ".2f")


def _rate_text(value: Any) -> str:
    return format(float(value or 0), ".4f")


def _invoice_currency_value(currency: Any) -> str:
    if isinstance(currency, Moneda):
        return currency.value
    return str(currency or Moneda.NIO.value)


class ReciboWorkflowService:
    """Orchestrates recibo use cases and read models for UI workflows."""

    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        list_recibo_use_case: ListModelUseCase,
        get_recibo_use_case: GetModelUseCase,
        create_recibo_use_case: CreateReciboConAplicacionesUseCase,
        update_recibo_use_case: UpdateReciboUseCase,
        delete_recibo_use_case: DeleteReciboUseCase,
    ):
        self.repository = repository
        self.unit_of_work = unit_of_work
        self.list_recibo_use_case = list_recibo_use_case
        self.get_recibo_use_case = get_recibo_use_case
        self.create_recibo_use_case = create_recibo_use_case
        self.update_recibo_use_case = update_recibo_use_case
        self.delete_recibo_use_case = delete_recibo_use_case

    @staticmethod
    def _as_payload(payload: Mapping[str, object], *, message: str) -> dict[str, object]:
        if payload is None or not isinstance(payload, Mapping):
            raise InvalidPayloadError(message)
        return dict(payload)

    @staticmethod
    def _as_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("Se requiere identificador valido de recibo")
        return record_id

    def list(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        return self.list_recibo_use_case.execute(filters)

    def get(self, record_id: int) -> CatalogRecordDTO | None:
        return self.get_recibo_use_case.execute(self._as_record_id(record_id))

    def create(self, payload: Mapping[str, object] | CreateReciboCommand) -> CatalogRecordDTO | None:
        if isinstance(payload, CreateReciboCommand):
            data = payload.to_payload()
        else:
            data = self._as_payload(payload, message="Se requiere payload para crear recibo")
        recibo = self.create_recibo_use_case.execute(data)
        return self.repository.get_record("recibo", cast(int, recibo.id))

    def update(
        self,
        record_id_or_payload: int | Mapping[str, object] | UpdateReciboCommand,
        payload: Mapping[str, object] | None = None,
    ) -> CatalogRecordDTO | None:
        if isinstance(record_id_or_payload, UpdateReciboCommand):
            data = record_id_or_payload.to_payload()
        else:
            data = self._normalize_update_payload(record_id_or_payload, payload)
        recibo = self.update_recibo_use_case.execute(data)
        return self.repository.get_record("recibo", cast(int, recibo.id))

    def delete(self, payload: Mapping[str, object] | int) -> bool:
        if payload is None:
            raise InvalidIdentifierError("Se requiere identificador para eliminar recibo")
        return self.delete_recibo_use_case.execute(payload)

    def get_form_state(self, record_id: int) -> dict[str, Any]:
        normalized_record_id = self._as_record_id(record_id)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._load_form_state(session, normalized_record_id)
        )

    def search_factura_candidates(
        self,
        cliente_id: int,
        term: str,
        *,
        exclude_recibo_id: int | None = None,
        excluded_factura_ids: Sequence[int] = (),
    ) -> list[dict[str, Any]]:
        normalized_cliente_id = self._as_record_id(int(cliente_id))
        excluded_ids = {int(factura_id) for factura_id in excluded_factura_ids if int(factura_id) > 0}
        normalized_term = str(term or "").strip()
        return self.unit_of_work.run_in_transaction(
            lambda session: self._search_facturas(
                session,
                normalized_cliente_id,
                normalized_term,
                exclude_recibo_id=exclude_recibo_id,
                excluded_factura_ids=excluded_ids,
            )
        )

    def crear(self, payload: Mapping[str, object]):
        return self.create(payload)

    def eliminar(self, payload: Mapping[str, object] | int):
        return self.delete(payload)

    def crear_recibo(self, payload: Mapping[str, object]):
        return self.create(payload)

    def create_recibo(self, payload: Mapping[str, object]):
        return self.create(payload)

    def create_recibo_full(self, payload: Mapping[str, object]):
        return self.create(payload)

    def _normalize_update_payload(
        self,
        record_id_or_payload,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if payload is None:
            if not isinstance(record_id_or_payload, Mapping):
                raise InvalidPayloadError("Se requiere payload para actualizar recibo")
            return dict(record_id_or_payload)

        record_id = self._as_record_id(record_id_or_payload)
        update_payload = self._as_payload(payload, message="Se requiere payload para actualizar recibo")
        return {"id": record_id, **update_payload}

    def _load_form_state(self, session, record_id: int) -> dict[str, Any]:
        recibo = session.execute(
            select(Recibo)
            .options(
                joinedload(Recibo.recibos_facturas).joinedload(ReciboFactura.factura),
            )
            .where(Recibo.id == record_id)
        ).unique().scalar_one_or_none()
        if recibo is None:
            raise ValueError(f"No se encontro recibo con id={record_id}")

        values = {
            "referencia": str(recibo.referencia or ""),
            "fecha_emision": format_field_value_for_ui(kind="datetime", value=recibo.fecha_emision),
            "cliente_id": int(recibo.cliente_id),
            "monto": _money_text(recibo.monto),
            "moneda": _invoice_currency_value(recibo.moneda),
            "tasa_cambio": _rate_text(recibo.tasa_cambio),
        }
        selected_facturas: list[dict[str, Any]] = []
        for relacion in recibo.recibos_facturas:
            factura = relacion.factura
            if factura is None:
                continue
            item = self._serialize_factura_for_recibo(factura, exclude_recibo_id=recibo.id)
            item["applied_amount"] = _money_text(relacion.monto_pagado)
            selected_facturas.append(item)
        return {"values": values, "selected_facturas": selected_facturas}

    def _search_facturas(
        self,
        session,
        cliente_id: int,
        term: str,
        *,
        exclude_recibo_id: int | None,
        excluded_factura_ids: set[int],
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Factura)
            .options(joinedload(Factura.impuestos), joinedload(Factura.recibos_facturas))
            .where(Factura.cliente_id == cliente_id)
            .where(Factura.estado.in_(_RECIBO_COBRABLE_STATES))
        )
        if term:
            stmt = stmt.where(Factura.numero_factura.ilike(f"%{term}%"))
        facturas = (
            session.execute(stmt.order_by(Factura.fecha_emision.desc(), Factura.id.desc()).limit(20))
            .unique()
            .scalars()
            .all()
        )
        return [
            self._serialize_factura_for_recibo(factura, exclude_recibo_id=exclude_recibo_id)
            for factura in facturas
            if int(factura.id) not in excluded_factura_ids
        ]

    def _serialize_factura_for_recibo(self, factura: Factura, *, exclude_recibo_id: int | None) -> dict[str, Any]:
        return {
            "value": int(factura.id),
            "label": str(factura.numero_factura or f"Factura #{factura.id}"),
            "id": int(factura.id),
            "numero_factura": str(factura.numero_factura or f"Factura #{factura.id}"),
            "fecha_emision": format_field_value_for_ui(kind="datetime", value=factura.fecha_emision),
            "subtotal": _money_text(factura._subtotal),
            "retenciones": _money_text(factura.monto_retenido),
            "total": _money_text(factura._total),
            "saldo_restante": _money_text(factura.get_saldo_restante(exclude_recibo_id=exclude_recibo_id)),
            "moneda": _invoice_currency_value(factura.moneda),
            "tasa_cambio": _rate_text(factura.tasa_cambio),
            "estado": str(getattr(factura.estado, "value", factura.estado)),
            "applied_amount": "0.00",
        }
