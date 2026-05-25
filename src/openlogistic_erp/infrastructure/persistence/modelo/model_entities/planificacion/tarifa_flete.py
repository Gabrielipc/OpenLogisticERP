"""Tarifa de flete."""
from __future__ import annotations

from sqlalchemy import Column, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from ..base import Base, Moneda


class TarifaFlete(Base):
    __tablename__ = "tarifa_flete"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=False)
    ruta_id = Column(Integer, ForeignKey("ruta.id"), nullable=False)
    costo = Column(Numeric(12, 2), nullable=False)
    moneda = Column(Enum(Moneda), nullable=False, default=Moneda.NIO)
    descripcion = Column(String, nullable=True, default=None)

    cliente = relationship("Cliente", back_populates="tarifas")
    ruta = relationship("Ruta", back_populates="tarifas")
