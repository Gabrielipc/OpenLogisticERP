"""Gasto real del Thermo."""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class GastoRealThermo(Base):
    __tablename__ = "gasto_real_thermo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_operacion_id = Column(Integer, ForeignKey("detalle_operacion.id", ondelete="CASCADE"), nullable=False)
    combustible_base_thermo = Column(Float, default=40.0)
    restante_thermo = Column(Float, default=0.0, nullable=True)
    _consumo_thermo = Column(Float, default=0.0)

    detalle_operacion = relationship("DetalleOperacion", back_populates="gasto_real_thermo")
