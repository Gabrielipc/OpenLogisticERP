"""Detalle de operación (container de acciones operativas)."""
from __future__ import annotations

from sqlalchemy import Column, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base, EstadoDetalle


class DetalleOperacion(Base):
    __tablename__ = "detalle_operacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    viaje_id = Column(Integer, ForeignKey("viaje.id", ondelete="CASCADE"), nullable=False)
    estado = Column(Enum(EstadoDetalle), nullable=False, default=EstadoDetalle.ABIERTO)

    viaje = relationship("Viaje", back_populates="detalle_operacion")
    ordenes_combustible = relationship(
        "OrdenCombustible",
        back_populates="detalle_operacion",
        cascade="all, delete-orphan",
    )
    movimientos_combustible = relationship(
        "MovimientoCombustible",
        back_populates="detalle_operacion",
        cascade="all, delete-orphan",
    )
    actividad_thermo = relationship(
        "ActividadThermo",
        back_populates="detalle_operacion",
        uselist=False,
        cascade="all, delete-orphan",
    )
    descarga = relationship(
        "Descarga",
        back_populates="detalle_operacion",
        uselist=False,
        cascade="all, delete-orphan",
    )
    gasto_real_thermo = relationship(
        "GastoRealThermo",
        back_populates="detalle_operacion",
        uselist=False,
        cascade="all, delete-orphan",
    )
