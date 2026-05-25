"""Thermo."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base, EstadoCamion


class Thermo(Base):
    __tablename__ = "thermo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False)
    marca = Column(String, nullable=False)
    modelo = Column(String, nullable=True)
    estado = Column(Enum(EstadoCamion), nullable=False, default=EstadoCamion.ACTIVO)

    conductor = relationship("Conductor", back_populates="thermo")
    viajes = relationship("Viaje", back_populates="thermo")
    datos_historicos_consumo = relationship("DatosHistoricosConsumoThermo", back_populates="thermo")
    modelo_consumo = relationship("ModeloConsumoThermo", back_populates="thermo")

