"""Use case to create invoice with details and totals in one atomic transaction."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    Factura,
    Gasto,
    Impuesto,
    Moneda,
    TipoGasto,
    TipoImpuesto,
    parse_money,
    parse_percent,
    q2,
)
from ...factories.detalle_factura_factory import DetalleFacturaFactory
from ...factories.factura_factory import FacturaFactory


class CreateFacturaConDetallesUseCase:
    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        factura_factory: FacturaFactory,
        detalle_factura_factory: DetalleFacturaFactory,
    ):
        self._repository = repository
        self._uow = unit_of_work
        self._factura_factory = factura_factory
        self._detalle_factory = detalle_factura_factory

    def execute(self, payload: dict[str, Any]) -> Factura:
        factura_payload = dict(payload.get("factura", {}))
        detalles_payload = payload.get("detalles_data", []) or []
        impuestos_payload = payload.get("impuestos", []) or []

        def _action(session):
            factura = self._factura_factory.create_with_data(factura_payload)
            session.add(factura)
            session.flush()
            factura_id = cast(int, factura.id)

            for detalle_payload in detalles_payload:
                detalle = self._create_detalle(session, detalle_payload, factura_id=factura_id)
                session.add(detalle)

            impuestos = [session.get(Impuesto, int(item)) if isinstance(item, int) else item for item in impuestos_payload]
            factura.impuestos = [i for i in impuestos if i is not None]

            subtotal = self._calcular_subtotal(factura)
            total = self._calcular_total(factura, subtotal)
            factura._subtotal = subtotal
            factura._total = total
            session.add(factura)
            return factura

        return self._uow.run_in_transaction(_action)

    def _calcular_subtotal(self, factura: Factura) -> Decimal:
        return q2(sum((parse_money(detalle.costo) for detalle in factura.detalles), Decimal("0")))

    def _calcular_total(self, factura: Factura, subtotal: Decimal) -> Decimal:
        base = q2(subtotal)
        impuestos = Decimal("0")
        retenciones = Decimal("0")

        for impuesto in factura.impuestos:
            porcentaje = parse_percent(impuesto.porcentaje or 0)
            if impuesto.tipo == TipoImpuesto.RETENCION:
                retenciones += porcentaje
            else:
                impuestos += porcentaje

        total = base + base * (impuestos / Decimal("100")) - base * (retenciones / Decimal("100"))
        return q2(total)

    def _create_detalle(self, session, detalle_payload: dict[str, Any], *, factura_id: int):
        payload = dict(detalle_payload)
        gasto_payload = payload.pop("gasto_data", None)
        if gasto_payload is not None:
            gasto = self._create_or_update_gasto(None, gasto_payload)
            session.add(gasto)
            session.flush()
            payload["gasto_id"] = cast(int, gasto.id)
            payload.setdefault("costo", gasto_payload.get("costo", gasto.costo))
        return self._detalle_factory.create_with_data(payload, factura_id=factura_id)

    @staticmethod
    def _create_or_update_gasto(existing: Gasto | None, gasto_payload: dict[str, Any]) -> Gasto:
        gasto = existing or Gasto(
            tipo=TipoGasto.OTRO,
            descripcion=None,
            costo=Decimal("0.00"),
            moneda=Moneda.NIO,
        )
        payload = dict(gasto_payload)
        tipo = payload.get("tipo")
        if tipo is not None:
            gasto.tipo = tipo if isinstance(tipo, TipoGasto) else TipoGasto(tipo)
        gasto.descripcion = payload.get("descripcion")
        if "costo" in payload:
            gasto.costo = parse_money(payload.get("costo"))
        moneda = payload.get("moneda")
        if moneda is not None:
            gasto.moneda = moneda if isinstance(moneda, Moneda) else Moneda(moneda)
        return gasto
