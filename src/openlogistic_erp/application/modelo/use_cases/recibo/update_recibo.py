"""Use case to update recibo payments atomically."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    EstadoFactura,
    Factura,
    Recibo,
    ReciboFactura,
    _to_decimal,
    parse_money,
)
from ...contracts import InvalidIdentifierError, InvalidPayloadError


class UpdateReciboUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload: dict[str, Any]) -> Recibo:
        if not isinstance(payload, Mapping):
            raise InvalidPayloadError("Se requiere payload para actualizar recibo")

        payload = dict(payload)
        recibo_id = self._resolve_recibo_id(payload)
        recibo_data = payload.get("recibo", {})
        pagos_data = payload.get("facturas", []) or []
        if not pagos_data:
            raise InvalidPayloadError("El recibo debe incluir al menos una factura asignada.")

        def _action(session):
            recibo = session.get(Recibo, recibo_id)
            if recibo is None:
                raise ValueError(f"Recibo no encontrado: id={recibo_id}")

            if isinstance(recibo_data, Mapping):
                for campo, valor in dict(recibo_data).items():
                    if campo == "id":
                        continue
                    if hasattr(recibo, campo):
                        setattr(recibo, campo, valor)

            tasa_cambio = getattr(recibo, "tasa_cambio", None)
            if tasa_cambio is not None:
                tasa_cambio_dec = Decimal(str(tasa_cambio))
                if tasa_cambio_dec <= 0:
                    raise ValueError("La tasa de cambio debe ser mayor que cero.")

            facturas_impactadas = self._clear_existing_payments(session, recibo)
            facturas_impactadas.update(self._assign_payments(session, recibo, pagos_data))

            for factura in facturas_impactadas:
                self._recalc_estado_factura(factura)

            session.add(recibo)
            session.flush()
            return recibo

        return self._uow.run_in_transaction(_action)

    def _resolve_recibo_id(self, payload: dict[str, Any]) -> int:
        recibo_id = payload.get("id")
        recibo_data = payload.get("recibo")
        if recibo_id is None and isinstance(recibo_data, Mapping):
            recibo_id = recibo_data.get("id")
        if not isinstance(recibo_id, int) or recibo_id <= 0:
            raise InvalidIdentifierError("Se requiere id de recibo para actualizar")
        return recibo_id

    def _clear_existing_payments(self, session, recibo: Recibo) -> set[Factura]:
        facturas: set[Factura] = set()
        relaciones = session.query(ReciboFactura).filter_by(recibo_id=recibo.id).all()
        for relacion in relaciones:
            factura = relacion.factura
            if factura is not None:
                facturas.add(factura)
                if relacion in factura.recibos_facturas:
                    factura.recibos_facturas.remove(relacion)
            session.delete(relacion)
        session.flush()
        return facturas

    def _assign_payments(self, session, recibo: Recibo, pagos_data: list[dict[str, Any]]) -> set[Factura]:
        total_consumido_recibo = Decimal("0")
        pagos: list[tuple[Factura, Decimal]] = []

        for pago in pagos_data:
            if not isinstance(pago, Mapping) or pago.get("factura_id") is None:
                raise InvalidPayloadError("Cada pago debe incluir factura_id")

            pago = dict(pago)
            factura = session.get(Factura, int(pago["factura_id"]))
            if factura is None:
                raise ValueError(f"Factura no encontrada: {pago['factura_id']}")
            if factura.cliente_id != recibo.cliente_id:
                raise ValueError("La factura debe pertenecer al mismo cliente que el recibo.")

            saldo_restante = parse_money(factura.get_saldo_restante(exclude_recibo_id=recibo.id))
            monto = parse_money(pago.get("monto", saldo_restante))
            if monto <= 0:
                raise ValueError("El monto de pago debe ser mayor que cero.")
            if monto > saldo_restante:
                raise ValueError("El monto a pagar excede el saldo pendiente.")

            total_consumido_recibo += recibo.convert_to_recibo_currency(monto, factura.moneda)
            pagos.append((factura, monto))

        monto_recibo = parse_money(recibo.monto)
        total_consumido_recibo = parse_money(total_consumido_recibo)
        if total_consumido_recibo > monto_recibo:
            raise ValueError("Total de pagos supera el saldo del recibo.")
        if total_consumido_recibo != monto_recibo:
            raise ValueError("La suma aplicada debe consumir todo el monto del recibo.")

        facturas_impactadas: set[Factura] = set()
        for factura, monto in pagos:
            session.add(
                ReciboFactura(
                    recibo=recibo,
                    factura=factura,
                    monto_pagado=monto,
                )
            )
            facturas_impactadas.add(factura)

        session.flush()
        return facturas_impactadas

    def _recalc_estado_factura(self, factura: Factura) -> None:
        total_factura = _to_decimal(factura._total) or Decimal("0")
        total_pagado = Decimal("0")
        for relacion in factura.recibos_facturas:
            total_pagado += parse_money(relacion.monto_pagado or 0)

        if total_pagado >= total_factura:
            factura.estado = EstadoFactura.PAGADA
        elif total_pagado > 0:
            factura.estado = EstadoFactura.PAGADAPAR
        else:
            factura.estado = EstadoFactura.PENDIENTE
