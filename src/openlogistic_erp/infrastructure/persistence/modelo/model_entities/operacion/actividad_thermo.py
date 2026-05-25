"""Actividad del Thermo en detalle de operación."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..base import Base


class ActividadThermo(Base):
    __tablename__ = "actividad_thermo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detalle_operacion_id = Column(Integer, ForeignKey("detalle_operacion.id", ondelete="CASCADE"), nullable=False)
    fecha_hora_encendido = Column(DateTime, nullable=True)
    fecha_hora_apagado = Column(DateTime, nullable=True)
    _duracion_horas = Column(Float, nullable=True)

    detalle_operacion = relationship("DetalleOperacion", back_populates="actividad_thermo")

    @property
    def temperatura(self):
        if self.detalle_operacion is None:
            return None
        if self.detalle_operacion.viaje is None:
            return None
        return getattr(self.detalle_operacion.viaje, "temperatura", None)

    def calcular_horas_trabajadas(self):
        if self.fecha_hora_apagado is not None and self.fecha_hora_encendido is not None:
            delta = self.fecha_hora_apagado - self.fecha_hora_encendido
            self._duracion_horas = delta.total_seconds() / 3600
        else:
            self._duracion_horas = None
