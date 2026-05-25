"""Use case to delete recibo and recalculate linked factura states."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import EstadoFactura, Factura, Recibo, _to_decimal
from ...contracts import InvalidIdentifierError


class DeleteReciboUseCase:
    def __init__(self, repository: ModeloCatalogRepository, unit_of_work: SQLAlchemyUnitOfWork):
        self._repository = repository
        self._uow = unit_of_work

    def execute(self, payload) -> bool:
        recibo_id = payload.get("id") if isinstance(payload, Mapping) else payload
        if not isinstance(recibo_id, int) or recibo_id <= 0:
            raise InvalidIdentifierError("Se requiere id de recibo para eliminar")

        def _action(session):
            recibo = session.get(Recibo, recibo_id)
            if recibo is None:
                raise ValueError(f"Recibo no encontrado: id={recibo_id}")

            facturas: list[Factura] = []
            for relacion in list(recibo.recibos_facturas):
                factura_relacionada = relacion.factura
                if factura_relacionada is not None and factura_relacionada not in facturas:
                    facturas.append(factura_relacionada)
                if factura_relacionada is not None and relacion in factura_relacionada.recibos_facturas:
                    factura_relacionada.recibos_facturas.remove(relacion)
                session.delete(relacion)

            session.delete(recibo)
            session.flush()

            for factura in facturas:
                if cast(EstadoFactura, factura.estado) == EstadoFactura.ANULADA:
                    continue
                total_pagado = sum(
                    (_to_decimal(relacion.monto_pagado) or Decimal("0"))
                    for relacion in factura.recibos_facturas
                )
                total_factura = _to_decimal(factura._total) or Decimal("0")
                if total_pagado <= 0:
                    factura.estado = EstadoFactura.PENDIENTE
                elif total_pagado >= total_factura:
                    factura.estado = EstadoFactura.PAGADA
                else:
                    factura.estado = EstadoFactura.PAGADAPAR

            return True

        return self._uow.run_in_transaction(_action)
