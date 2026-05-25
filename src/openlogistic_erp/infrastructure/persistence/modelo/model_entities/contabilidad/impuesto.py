"""Impuestos."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Integer, Numeric, String
from sqlalchemy.orm import relationship, validates

from ..base import Base, TipoImpuesto, factura_impuesto, parse_percent


class Impuesto(Base):
    __tablename__ = "impuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False)
    tipo = Column(Enum(TipoImpuesto), nullable=False)
    porcentaje = Column(Numeric(8,2), nullable=False)

    facturas = relationship("Factura", secondary=factura_impuesto, back_populates="impuestos")

    @validates("porcentaje")
    def validate_porcentaje(self, _, value):
        return parse_percent(value)
