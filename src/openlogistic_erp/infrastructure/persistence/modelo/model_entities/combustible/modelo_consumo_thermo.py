"""Modelo de consumo del Thermo."""
from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class ModeloConsumoThermo(Base):
    __tablename__ = "modelo_consumo_thermo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thermo_id = Column(Integer, ForeignKey("thermo.id"), nullable=False)
    pendiente = Column(Float, nullable=True)
    interseccion = Column(Float, nullable=True)

    thermo = relationship("Thermo", back_populates="modelo_consumo")

    def calcular_gasto_combustible(self, temperatura, horas_encendida):
        if self.pendiente is None or self.interseccion is None:
            raise ValueError("El modelo no tiene valores definidos. Calcula el modelo primero.")
        rendimiento = self.pendiente * temperatura + self.interseccion
        if rendimiento <= 0:
            raise ValueError("El rendimiento estimado debe ser positivo para calcular el consumo.")
        return horas_encendida / rendimiento
