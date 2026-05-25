"""Camion."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base, EstadoCamion


class Camion(Base):
    __tablename__ = "camion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    placa = Column(String, nullable=False)
    numero_caat = Column(String, nullable=True)
    codigo_aduanero = Column(String, nullable=True)
    marca = Column(String, nullable=False)
    modelo = Column(String, nullable=True)
    color = Column(String, nullable=False)
    motor = Column(String, nullable=False)
    chasis = Column(String, nullable=False)
    anio = Column(Integer, nullable=True)
    estado = Column(Enum(EstadoCamion), nullable=False, default=EstadoCamion.ACTIVO)

    conductor = relationship("Conductor", back_populates="camion")
    viajes = relationship("Viaje", back_populates="camion")
    referencias_consumo_combustible = relationship(
        "CriteriosConsumoCombustible",
        secondary="camion_criterio_consumo",
        back_populates="camiones",
    )
