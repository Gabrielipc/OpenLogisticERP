"""Factories for recibo creation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ....infrastructure.persistence.modelo.workflow_orm import EstadoRecibo, Moneda, Recibo


class ReciboFactory:
    def create_empty(self, cliente_id: int) -> Recibo:
        return Recibo(
            referencia="",
            fecha_emision=datetime.now(),
            cliente_id=cliente_id,
            monto=Decimal("0.00"),
            estado=EstadoRecibo.ACTIVO,
            moneda=Moneda.USD,
            tasa_cambio=Decimal("1.0000"),
        )

    def create_with_data(self, data: dict) -> Recibo:
        defaults = {
            "referencia": "",
            "fecha_emision": datetime.now(),
            "cliente_id": None,
            "monto": Decimal("0.00"),
            "estado": EstadoRecibo.ACTIVO,
            "moneda": Moneda.USD,
            "tasa_cambio": Decimal("1.0000"),
        }
        complete = {**defaults, **dict(data)}
        return Recibo(**complete)
