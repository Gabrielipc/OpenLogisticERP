"""Gasto."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Column, Enum, Integer, Numeric, String
from sqlalchemy.orm import relationship, validates

from ..base import Base, Moneda, TipoGasto, parse_money


class Gasto(Base):
    __tablename__ = "gasto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(Enum(TipoGasto), nullable=False)
    descripcion = Column(String(200), nullable=True)
    costo = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    moneda = Column(Enum(Moneda), nullable=False, default=Moneda.USD)

    detalles_factura = relationship("DetalleFactura", uselist=False, back_populates="gasto")

    @validates("costo")
    def validate_costo(self, _, value):
        return parse_money(value)
