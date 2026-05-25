"""Detalle de factura."""
from __future__ import annotations

from sqlalchemy import Column, Enum, ForeignKey, Integer, Numeric, event
from sqlalchemy.orm import relationship, validates

from ..base import Base, EstadoFacturacion, TipoDetalle, parse_money
from ..operacion.viaje import Viaje


class DetalleFactura(Base):
    __tablename__ = "detalle_factura"

    id = Column(Integer, primary_key=True, autoincrement=True)
    factura_id = Column(Integer, ForeignKey("factura.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(Enum(TipoDetalle), nullable=False)
    viaje_id = Column(Integer, ForeignKey("viaje.id"), nullable=True)
    gasto_id = Column(Integer, ForeignKey("gasto.id"), nullable=True)
    costo = Column(Numeric(12, 2), nullable=False)

    factura = relationship("Factura", back_populates="detalles")
    viaje = relationship("Viaje", back_populates="detalles_factura")
    gasto = relationship("Gasto", back_populates="detalles_factura")

    @validates("tipo")
    def validate_tipo(self, _, tipo):
        if tipo == TipoDetalle.VIAJE and self.gasto_id is not None:
            raise ValueError("No se puede asignar un gasto a un detalle de tipo VIAJE")
        if tipo == TipoDetalle.GASTO and self.viaje_id is not None:
            raise ValueError("No se puede asignar un viaje a un detalle de tipo GASTO")
        return tipo

    @validates("costo")
    def validate_costo(self, _, costo):
        return parse_money(costo)


@event.listens_for(DetalleFactura, "after_insert")
def after_insert_detalle_factura(mapper, connection, target):
    if target.viaje_id:
        viaje_table = Viaje.__table__
        connection.execute(
            viaje_table.update()
            .where(viaje_table.c.id == target.viaje_id)
            .values(estado_facturacion=EstadoFacturacion.FACTURADO)
        )


@event.listens_for(DetalleFactura, "after_delete")
def after_delete_detalle_factura(mapper, connection, target):
    if target.viaje_id:
        viaje_table = Viaje.__table__
        connection.execute(
            viaje_table.update()
            .where(viaje_table.c.id == target.viaje_id)
            .values(estado_facturacion=EstadoFacturacion.REGISTRADO)
        )

    if target.gasto_id:
        from .gasto import Gasto

        gasto_table = Gasto.__table__
        connection.execute(gasto_table.delete().where(gasto_table.c.id == target.gasto_id))
