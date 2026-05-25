"""Viajes y subtipos de viaje."""
from __future__ import annotations

from typing import cast

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from ..base import Base, EstadoFacturacion, EstadoViaje, Moneda, TipoViaje


class Viaje(Base):
    __tablename__ = "viaje"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referencia = Column(String, nullable=True)
    cliente_id = Column(Integer, ForeignKey("cliente.id"), nullable=True)
    conductor_id = Column(Integer, ForeignKey("conductor.id"), nullable=False)
    furgon_id = Column(Integer, ForeignKey("furgon.id"), nullable=False)
    camion_id = Column(Integer, ForeignKey("camion.id"), nullable=False)
    thermo_id = Column(Integer, ForeignKey("thermo.id"), nullable=False)

    tipo_viaje = Column(Enum(TipoViaje), nullable=False)
    _ruta_id = Column(Integer, ForeignKey("ruta.id"), nullable=False)
    fecha_posicionamiento = Column(DateTime, nullable=True)
    descripcion = Column(String, nullable=True)
    estado = Column(Enum(EstadoViaje), nullable=False)
    _estado_facturacion = Column(
        "estado_facturacion",
        Enum(EstadoFacturacion),
        nullable=False,
        default=EstadoFacturacion.REGISTRADO,
    )
    _circuito_id = Column(Integer, ForeignKey("circuito.id", ondelete="CASCADE"), nullable=False)
    viaticos_monto = Column(Numeric(12, 2), nullable=True)
    viaticos_moneda = Column(Enum(Moneda), nullable=False, default=Moneda.USD)

    cliente = relationship("Cliente", back_populates="viajes")
    conductor = relationship("Conductor", back_populates="viajes")
    furgon = relationship("Furgon", back_populates="viajes")
    camion = relationship("Camion", back_populates="viajes")
    thermo = relationship("Thermo", back_populates="viajes")
    detalles_factura = relationship("DetalleFactura", uselist=False, back_populates="viaje")
    _ruta = relationship("Ruta", back_populates="viajes")
    _circuito = relationship("Circuito", back_populates="viajes")
    detalle_operacion = relationship(
        "DetalleOperacion",
        back_populates="viaje",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
        passive_deletes=True,
    )

    __mapper_args__ = {
        "polymorphic_on": tipo_viaje,
        "with_polymorphic": None,
    }

    @property
    def estado_facturacion(self) -> EstadoFacturacion:
        value = self._estado_facturacion
        if isinstance(value, EstadoFacturacion):
            return value
        return EstadoFacturacion(cast(str, value))

    @estado_facturacion.setter
    def estado_facturacion(self, value: EstadoFacturacion | str):
        if value is None:
            raise ValueError("El estado de facturacion no puede ser nulo.")
        self._estado_facturacion = value if isinstance(value, EstadoFacturacion) else EstadoFacturacion(value)


class ViajeExportacion(Viaje):
    __mapper_args__ = {"polymorphic_identity": TipoViaje.EXPOR}
    temperatura = Column(Float)


class ViajeImportacion(Viaje):
    __mapper_args__ = {"polymorphic_identity": TipoViaje.IMPOR}


class ViajeVacio(Viaje):
    __mapper_args__ = {"polymorphic_identity": TipoViaje.VACIO}
