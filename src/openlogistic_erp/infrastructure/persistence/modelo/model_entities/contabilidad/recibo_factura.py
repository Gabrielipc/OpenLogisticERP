"""Recibo-Factura association model."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Column, ForeignKey, Integer, Numeric
from sqlalchemy.orm import relationship, validates

from ..base import Base, parse_money


class ReciboFactura(Base):
    __tablename__ = "recibo_factura"

    recibo_id = Column(Integer, ForeignKey("recibo.id"), primary_key=True)
    factura_id = Column(Integer, ForeignKey("factura.id"), primary_key=True)
    monto_pagado = Column(Numeric(12,2), nullable=False, default=Decimal("0.00"))

    recibo = relationship("Recibo", back_populates="recibos_facturas")
    factura = relationship("Factura", back_populates="recibos_facturas")

    @validates("monto_pagado")
    def validate_monto_pagado(self, _, value):
        return parse_money(value)
