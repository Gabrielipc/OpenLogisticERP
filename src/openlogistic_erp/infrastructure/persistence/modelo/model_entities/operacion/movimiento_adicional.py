"""Movimiento adicional."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class MovimientoAdicional(Base):
    __tablename__ = "movimiento_adicional"

    id = Column(Integer, primary_key=True, autoincrement=True)
    circuito_id = Column(Integer, ForeignKey("circuito.id", ondelete="CASCADE"), nullable=False)
    ruta_id = Column(Integer, ForeignKey("ruta.id"), nullable=True)
    fecha_movimiento = Column(DateTime, nullable=True)
    descripcion = Column(String, nullable=True)
    es_triangulado = Column(Boolean, nullable=False, default=False)

    ruta = relationship("Ruta", back_populates="movimientos_adicionales")
    circuito = relationship("Circuito", back_populates="movimientos_adicionales")
