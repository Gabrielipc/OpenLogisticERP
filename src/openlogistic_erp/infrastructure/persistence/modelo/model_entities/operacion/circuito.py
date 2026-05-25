"""Circuito operativo."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Enum, Integer
from sqlalchemy.orm import relationship

from ..base import Base, EstadoCircuito


class Circuito(Base):
    __tablename__ = "circuito"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_inicio = Column(DateTime, nullable=False)
    fecha_fin = Column(DateTime, nullable=True)
    estado = Column(Enum(EstadoCircuito), default=EstadoCircuito.ENPROGRESO, nullable=False)

    viajes = relationship("Viaje", back_populates="_circuito")
    gasto_real_camion = relationship("GastoRealCamion", back_populates="circuito", uselist=False)
    movimientos_adicionales = relationship("MovimientoAdicional", back_populates="circuito")
