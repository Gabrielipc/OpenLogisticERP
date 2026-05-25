"""Ubicación."""
from __future__ import annotations

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class Ubicacion(Base):
    __tablename__ = "ubicacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String, nullable=False)
    descripcion = Column(String, nullable=False)

    rutas_como_origen = relationship("Ruta", foreign_keys="[Ruta.origen_id]", back_populates="origen")
    rutas_como_destino = relationship("Ruta", foreign_keys="[Ruta.destino_id]", back_populates="destino")
    descarga = relationship("Descarga", back_populates="lugar_carga")
    referencias_consumo_lugar_carga = relationship(
        "CriteriosConsumoCombustible",
        foreign_keys="[CriteriosConsumoCombustible.lugar_carga_id]",
        back_populates="lugar_carga",
    )
    referencias_consumo_destino = relationship(
        "CriteriosConsumoCombustible",
        foreign_keys="[CriteriosConsumoCombustible.destino_id]",
        back_populates="destino",
    )
