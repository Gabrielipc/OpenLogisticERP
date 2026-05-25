"""Use case to create recibo and apply it to selected facturas atomically."""

from __future__ import annotations

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
from ...contracts import InvalidPayloadError
from ...factories.recibo_factory import ReciboFactory


class CreateReciboConAplicacionesUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork, recibo_factory: ReciboFactory):
        self._repository = repository
        self._uow = unit_of_work
        self._recibo_factory = recibo_factory

    def execute(self, payload: dict[str, Any]) -> Recibo:
        recibo_payload = dict(payload.get("recibo", {}))
        pagos_payload = payload.get("facturas", []) or []
        if not pagos_payload:
            raise InvalidPayloadError("El recibo debe incluir al menos una factura asignada.")

        def _action(session):
            recibo = self._recibo_factory.create_with_data(recibo_payload)
            
            tasa_cambio = getattr(recibo, "tasa_cambio", None)
            if tasa_cambio is not None:
                tasa_cambio_dec = Decimal(str(tasa_cambio))
                if tasa_cambio_dec <= 0:
                    raise ValueError("tasa de cambio debe ser mayor que cero")

            session.add(recibo)
            session.flush()

            total_consumido_recibo = Decimal("0")
            pagos = []

            for pago in pagos_payload:
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

            for factura, monto in pagos:
                session.add(
                    ReciboFactura(
                        recibo=recibo,
                        factura=factura,
                        monto_pagado=monto,
                    )
                )

            for factura, _ in pagos:
                self._recalc_estado_factura(session, factura)

            return recibo

        return self._uow.run_in_transaction(_action)

    def _recalc_estado_factura(self, session, factura: Factura) -> None:
        total_factura = _to_decimal(factura._total) or Decimal("0")
        total_pagado = Decimal("0")
        for rf in factura.recibos_facturas:
            total_pagado += parse_money(rf.monto_pagado)

        if total_pagado >= total_factura:
            factura.estado = EstadoFactura.PAGADA
        elif total_pagado > 0:
            factura.estado = EstadoFactura.PAGADAPAR
        else:
            factura.estado = EstadoFactura.PENDIENTE
