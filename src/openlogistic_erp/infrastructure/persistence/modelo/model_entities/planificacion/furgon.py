"""Furgon."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base, EstadoCamion, TipoCarga


class Furgon(Base):
    __tablename__ = "furgon"

    id = Column(Integer, primary_key=True, autoincrement=True)
    placa = Column(String, nullable=False)
    numero_economico = Column(String, nullable=True)
    codigo_aduanero = Column(String, nullable=True)
    marca = Column(String, nullable=True)
    modelo = Column(String, nullable=True)
    color = Column(String, nullable=True)
    chasis = Column(String, nullable=True)
    anio = Column(Integer, nullable=True)
    tamanio = Column(String, nullable=True)
    tipo_carga = Column(Enum(TipoCarga), nullable=False)
    estado = Column(Enum(EstadoCamion), nullable=False, default=EstadoCamion.ACTIVO)

    conductor = relationship("Conductor", back_populates="furgon")
    viajes = relationship("Viaje", back_populates="furgon")
