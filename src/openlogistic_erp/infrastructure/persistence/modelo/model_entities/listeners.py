"""Event listeners para reglas de dominio del módulo Modelo."""
from __future__ import annotations

from sqlalchemy import event

from .base import EstadoFacturacion
from .contabilidad.detalle_factura import DetalleFactura
from .contabilidad.gasto import Gasto
from .operacion.actividad_thermo import ActividadThermo
from .operacion.viaje import Viaje


@event.listens_for(DetalleFactura, "after_insert")
def _after_insert_detalle_factura(mapper, connection, target):
    if target.viaje_id:
        viaje_table = Viaje.__table__
        connection.execute(
            viaje_table.update()
            .where(viaje_table.c.id == target.viaje_id)
            .values(estado_facturacion=EstadoFacturacion.FACTURADO.value)
        )


@event.listens_for(DetalleFactura, "after_delete")
def _after_delete_detalle_factura(mapper, connection, target):
    if target.viaje_id:
        viaje_table = Viaje.__table__
        connection.execute(
            viaje_table.update()
            .where(viaje_table.c.id == target.viaje_id)
            .values(estado_facturacion=EstadoFacturacion.REGISTRADO.value)
        )


@event.listens_for(DetalleFactura, "after_delete")
def _cleanup_after_delete_detalle_factura(mapper, connection, target):
    if not target.gasto_id:
        return

    gasto_table = Gasto.__table__
    connection.execute(gasto_table.delete().where(gasto_table.c.id == target.gasto_id))


@event.listens_for(ActividadThermo, "before_insert")
@event.listens_for(ActividadThermo, "before_update")
def _actualizar_duracion_horas(mapper, connection, target):
    target.calcular_horas_trabajadas()
