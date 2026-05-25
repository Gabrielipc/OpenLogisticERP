"""Infrastructure-only re-exports for workflow-specific ORM types.

Application-layer workflow shims may depend on this module, but they must not
import ``model_entities`` directly.
"""

from __future__ import annotations

from .model_entities.base import (
    EstadoCamion,
    EstadoCircuito,
    EstadoConductor,
    EstadoDetalle,
    EstadoFactura,
    EstadoFacturacion,
    EstadoRecibo,
    EstadoViaje,
    Gasolinera,
    Moneda,
    TipoDetalle,
    TipoGasto,
    TipoImpuesto,
    TipoOrdenCombustible,
    TipoViaje,
    _to_decimal,
    parse_money,
    parse_percent,
    q2,
    q4,
)
from .model_entities.contabilidad.detalle_factura import DetalleFactura
from .model_entities.contabilidad.factura import Factura
from .model_entities.contabilidad.gasto import Gasto
from .model_entities.contabilidad.impuesto import Impuesto
from .model_entities.contabilidad.recibo import Recibo
from .model_entities.contabilidad.recibo_factura import ReciboFactura
from .model_entities.operacion.actividad_thermo import ActividadThermo
from .model_entities.operacion.circuito import Circuito
from .model_entities.operacion.descarga import Descarga
from .model_entities.operacion.detalle_operacion import DetalleOperacion
from .model_entities.operacion.gasto_real_camion import GastoRealCamion
from .model_entities.operacion.gasto_real_thermo import GastoRealThermo
from .model_entities.operacion.movimiento_adicional import MovimientoAdicional
from .model_entities.operacion.movimiento_combustible import MovimientoCombustible
from .model_entities.operacion.orden_combustible import OrdenCombustible
from .model_entities.operacion.viaje import Viaje, ViajeExportacion, ViajeImportacion, ViajeVacio
from .model_entities.planificacion.camion import Camion
from .model_entities.planificacion.cliente import Cliente
from .model_entities.planificacion.conductor import Conductor
from .model_entities.planificacion.furgon import Furgon
from .model_entities.planificacion.ruta import Ruta
from .model_entities.planificacion.tarifa_flete import TarifaFlete
from .model_entities.planificacion.thermo import Thermo
from .model_entities.planificacion.ubicacion import Ubicacion

__all__ = [
    "ActividadThermo",
    "Camion",
    "Circuito",
    "Cliente",
    "Conductor",
    "Descarga",
    "DetalleFactura",
    "DetalleOperacion",
    "EstadoCamion",
    "EstadoCircuito",
    "EstadoConductor",
    "EstadoDetalle",
    "EstadoFactura",
    "EstadoFacturacion",
    "EstadoRecibo",
    "EstadoViaje",
    "Factura",
    "Furgon",
    "Gasolinera",
    "Gasto",
    "GastoRealCamion",
    "GastoRealThermo",
    "Impuesto",
    "Moneda",
    "MovimientoAdicional",
    "MovimientoCombustible",
    "OrdenCombustible",
    "Recibo",
    "ReciboFactura",
    "Ruta",
    "TarifaFlete",
    "Thermo",
    "TipoDetalle",
    "TipoGasto",
    "TipoImpuesto",
    "TipoOrdenCombustible",
    "TipoViaje",
    "Ubicacion",
    "Viaje",
    "ViajeExportacion",
    "ViajeImportacion",
    "ViajeVacio",
    "_to_decimal",
    "parse_money",
    "parse_percent",
    "q2",
    "q4",
]
