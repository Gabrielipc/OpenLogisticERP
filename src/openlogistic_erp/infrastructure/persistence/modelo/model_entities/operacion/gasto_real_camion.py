"""Gasto real de camión por circuito."""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class GastoRealCamion(Base):
    __tablename__ = "gasto_real_camion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    circuito_id = Column(Integer, ForeignKey("circuito.id", ondelete="CASCADE"), nullable=False)
    combustible_base_camion = Column(Float, default=60.0)
    retorno_camion = Column(Float, default=0.0, nullable=True)
    _consumo_camion = Column(Float, default=0.0)

    circuito = relationship("Circuito", back_populates="gasto_real_camion")
