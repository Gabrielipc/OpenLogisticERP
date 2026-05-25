"""Factories for factura creation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ....infrastructure.persistence.modelo.workflow_orm import Factura, Moneda, parse_money, q4


class FacturaFactory:
    def create_empty(self, cliente_id: int | None = None) -> Factura:
        return Factura(
            numero_factura="",
            fecha_emision=datetime.now(),
            cliente_id=cliente_id,
            dias_credito=30,
            moneda=Moneda.NIO,
            tasa_cambio=Decimal("1.0000"),
        )

    def create_with_data(self, data: dict) -> Factura:
        defaults = {
            "numero_factura": "",
            "fecha_emision": datetime.now(),
            "cliente_id": None,
            "dias_credito": 30,
            "moneda": Moneda.NIO,
            "tasa_cambio": Decimal("1.0000"),
            "_subtotal": Decimal("0.00"),
            "_total": Decimal("0.00"),
        }
        complete = {**defaults, **dict(data)}
        complete["tasa_cambio"] = q4(complete.get("tasa_cambio"))
        complete["_subtotal"] = parse_money(complete.get("_subtotal"))
        complete["_total"] = parse_money(complete.get("_total"))
        return Factura(**complete)
