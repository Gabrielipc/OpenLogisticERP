"""Orden de combustible."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base, Gasolinera, TipoOrdenCombustible


class OrdenCombustible(Base):
    __tablename__ = "orden_combustible"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_operacion_id = Column(Integer, ForeignKey("detalle_operacion.id", ondelete="CASCADE"), nullable=False)
    gasolinera = Column(Enum(Gasolinera), nullable=False)
    numero_orden = Column(String, nullable=False)
    galones_autorizados = Column(Float, nullable=False)
    tipo = Column(Enum(TipoOrdenCombustible), nullable=False, default=TipoOrdenCombustible.CAMION)

    detalle_operacion = relationship("DetalleOperacion", back_populates="ordenes_combustible")
