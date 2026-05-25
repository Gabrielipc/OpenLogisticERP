"""Resumen de deudas por cliente."""
from __future__ import annotations

from sqlalchemy import Column, Integer, Numeric, String

from ..base import Base


class DeudaPorCliente(Base):
    __tablename__ = "deuda_por_cliente"
    __table_args__ = {"extend_existing": True}

    cliente_id = Column(Integer, primary_key=True)
    nombre_cliente = Column(String)
    deuda_dolares = Column(Numeric)
    deuda_cordobas = Column(Numeric)


