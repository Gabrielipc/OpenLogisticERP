"""Use cases for modelo."""

from .circuito.close_circuito import CloseCircuitoUseCase
from .circuito.delete_circuito import DeleteCircuitoUseCase
from .circuito.delete_empty_circuito import DeleteEmptyCircuitoRule
from .circuito.update_circuito_sections import UpdateCircuitoSectionsUseCase
from .crud_model import CreateModelUseCase, DeleteModelUseCase, GetModelUseCase, ListModelUseCase, UpdateModelUseCase
from .detalle_operacion.update_detalle_operacion_sections import UpdateDetalleOperacionSectionsUseCase
from .factura.create_factura import CreateFacturaConDetallesUseCase
from .factura.delete_factura import DeleteFacturaUseCase
from .factura.update_factura import UpdateFacturaUseCase
from .recibo.create_recibo import CreateReciboConAplicacionesUseCase
from .recibo.delete_recibo import DeleteReciboUseCase
from .recibo.update_recibo import UpdateReciboUseCase
from .viaje.create_viaje import CreateViajeUseCase
from .viaje.delete_viaje import DeleteViajeUseCase
from .viaje.terminar_viaje import TerminarViajeUseCase
from .viaje.update_viaje import UpdateViajeUseCase

__all__ = [
    "ListModelUseCase",
    "GetModelUseCase",
    "CreateModelUseCase",
    "UpdateModelUseCase",
    "DeleteModelUseCase",
    "CreateViajeUseCase",
    "UpdateViajeUseCase",
    "DeleteViajeUseCase",
    "CreateFacturaConDetallesUseCase",
    "UpdateFacturaUseCase",
    "DeleteFacturaUseCase",
    "CreateReciboConAplicacionesUseCase",
    "UpdateReciboUseCase",
    "DeleteReciboUseCase",
    "DeleteCircuitoUseCase",
    "DeleteEmptyCircuitoRule",
    "CloseCircuitoUseCase",
    "UpdateCircuitoSectionsUseCase",
    "UpdateDetalleOperacionSectionsUseCase",
    "TerminarViajeUseCase",
]
