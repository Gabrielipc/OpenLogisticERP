"""Cliente."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from ..base import Base


class Cliente(Base):
    __tablename__ = "cliente"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    ruc = Column(String, nullable=False, unique=True)
    direccion = Column(String, nullable=False)
    facturable = Column(Boolean, nullable=False, default=True)

    facturas = relationship("Factura", back_populates="cliente")
    tarifas = relationship("TarifaFlete", back_populates="cliente")
    viajes = relationship("Viaje", back_populates="cliente")
    recibos = relationship("Recibo", back_populates="cliente")
    referencias_consumo_combustible = relationship(
        "CriteriosConsumoCombustible",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )
