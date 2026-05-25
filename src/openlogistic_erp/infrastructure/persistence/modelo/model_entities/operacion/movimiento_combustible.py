"""Movimiento de combustible."""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class MovimientoCombustible(Base):
    __tablename__ = "movimiento_combustible"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_operacion_id = Column(Integer, ForeignKey("detalle_operacion.id", ondelete="CASCADE"), nullable=False)
    galones_transferidos = Column(Float, nullable=False)
    nota = Column(String, nullable=True)

    detalle_operacion = relationship("DetalleOperacion", back_populates="movimientos_combustible")

