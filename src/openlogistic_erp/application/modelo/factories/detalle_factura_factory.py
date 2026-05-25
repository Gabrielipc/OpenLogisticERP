"""Factories for factura detalle creation."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ....infrastructure.persistence.modelo.workflow_orm import DetalleFactura, TipoDetalle, parse_money


class DetalleFacturaFactory:
    def create_empty(self, factura_id: int, tipo: TipoDetalle) -> DetalleFactura:
        return DetalleFactura(
            factura_id=factura_id,
            tipo=tipo,
            viaje_id=None,
            gasto_id=None,
            costo=Decimal("0.00"),
        )

    def create_with_data(self, data: dict[str, Any], factura_id: int) -> DetalleFactura:
        defaults = {
            "factura_id": factura_id,
            "tipo": None,
            "viaje_id": None,
            "gasto_id": None,
            "costo": Decimal("0.00"),
        }
        complete = {**defaults, **dict(data)}
        if "tipo" in complete and not isinstance(complete["tipo"], TipoDetalle):
            complete["tipo"] = TipoDetalle(complete["tipo"])
        complete["costo"] = parse_money(complete.get("costo"))
        return DetalleFactura(**complete)
