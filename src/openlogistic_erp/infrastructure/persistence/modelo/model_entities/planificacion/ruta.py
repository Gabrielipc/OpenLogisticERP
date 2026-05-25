"""Rutas."""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class Ruta(Base):
    __tablename__ = "ruta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origen_id = Column(Integer, ForeignKey("ubicacion.id"), nullable=False)
    destino_id = Column(Integer, ForeignKey("ubicacion.id"), nullable=False)

    origen = relationship("Ubicacion", foreign_keys=[origen_id], back_populates="rutas_como_origen")
    destino = relationship("Ubicacion", foreign_keys=[destino_id], back_populates="rutas_como_destino")
    tarifas = relationship("TarifaFlete", back_populates="ruta")
    movimientos_adicionales = relationship("MovimientoAdicional", back_populates="ruta")
    viajes = relationship("Viaje", back_populates="_ruta")
    referencias_consumo_movimiento = relationship("CriteriosConsumoCombustible", back_populates="ruta_movimiento")
