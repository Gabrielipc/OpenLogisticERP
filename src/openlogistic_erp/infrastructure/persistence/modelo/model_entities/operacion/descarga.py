"""Descarga."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class Descarga(Base):
    __tablename__ = "descarga"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_operacion_id = Column(Integer, ForeignKey("detalle_operacion.id", ondelete="CASCADE"), nullable=False)
    fecha_posicionamiento = Column(DateTime, nullable=True)
    fecha_despacho = Column(DateTime, nullable=True)
    fecha_descarga = Column(DateTime, nullable=True)
    peso = Column(String, nullable=True)
    _lugar_carga_id = Column(Integer, ForeignKey("ubicacion.id"), default=3, nullable=True)
    _dias_viajados = Column(Integer, nullable=True)

    detalle_operacion = relationship("DetalleOperacion", back_populates="descarga")
    lugar_carga = relationship("Ubicacion", back_populates="descarga")
