"""Historia de consumo del Thermo."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class DatosHistoricosConsumoThermo(Base):
    __tablename__ = "datos_historicos_consumo_thermo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thermo_id = Column(Integer, ForeignKey("thermo.id"), nullable=False)
    fecha = Column(DateTime, nullable=False)
    temperatura = Column(Float, nullable=False)
    rendimiento = Column(Float, nullable=False)

    thermo = relationship("Thermo", back_populates="datos_historicos_consumo")
