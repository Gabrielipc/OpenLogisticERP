"""Referencias y modelos de consumo."""
from __future__ import annotations

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base, TipoReferencia


class CriteriosConsumoCombustible(Base):
    __tablename__ = "referencia_consumo_combustible"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo_referencia = Column(Enum(TipoReferencia), nullable=False, default=TipoReferencia.BASE)
    destino_id = Column(Integer, ForeignKey("ubicacion.id"), nullable=True)
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=True)
    lugar_carga_id = Column(Integer, ForeignKey("ubicacion.id"), nullable=True)
    ruta_movimiento_id = Column(Integer, ForeignKey("ruta.id"), nullable=True)
    peso_min = Column(Float, nullable=True)
    peso_max = Column(Float, nullable=True)
    consumo_galones = Column(Float, nullable=False)

    camiones = relationship(
        "Camion",
        secondary="camion_criterio_consumo",
        back_populates="referencias_consumo_combustible",
    )
    destino = relationship("Ubicacion", foreign_keys=[destino_id], back_populates="referencias_consumo_destino")
    lugar_carga = relationship("Ubicacion", foreign_keys=[lugar_carga_id], back_populates="referencias_consumo_lugar_carga")
    ruta_movimiento = relationship("Ruta", foreign_keys=[ruta_movimiento_id], back_populates="referencias_consumo_movimiento")
    cliente = relationship("Cliente", back_populates="referencias_consumo_combustible")
