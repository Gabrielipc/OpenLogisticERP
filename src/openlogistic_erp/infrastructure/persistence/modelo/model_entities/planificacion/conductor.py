"""Conductor."""
from __future__ import annotations

from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base, EstadoConductor


class Conductor(Base):
    __tablename__ = "conductor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    apellido = Column(String, nullable=False)
    cedula = Column(String, nullable=True)
    licencia = Column(String, nullable=True)
    pasaporte = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    camion_id = Column(Integer, ForeignKey("camion.id"), nullable=True)
    furgon_id = Column(Integer, ForeignKey("furgon.id"), nullable=True)
    thermo_id = Column(Integer, ForeignKey("thermo.id"), nullable=True)
    estado = Column(Enum(EstadoConductor), nullable=False, default=EstadoConductor.DISPONIBLE)

    camion = relationship("Camion", back_populates="conductor")
    furgon = relationship("Furgon", back_populates="conductor")
    thermo = relationship("Thermo", back_populates="conductor")
    viajes = relationship("Viaje", back_populates="conductor")
