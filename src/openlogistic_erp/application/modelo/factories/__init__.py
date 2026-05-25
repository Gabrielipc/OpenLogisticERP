"""Composition helpers for modelo module."""

from __future__ import annotations

from collections.abc import Callable

from ....domain.modelo.repositories.catalog import ModeloCatalogRepository
from ...common.uow import SQLAlchemyUnitOfWork
from ...modelo.circuito_service import CircuitoWorkflowService
from ...modelo.detalle_operacion_service import DetalleOperacionWorkflowService
from ...modelo.factura_service import FacturaWorkflowService
from ...modelo.recibo_service import ReciboWorkflowService
from ...modelo.services import ModeloCatalogService, ModeloWorkflowService
from ...modelo.use_cases import (
    CloseCircuitoUseCase,
    CreateFacturaConDetallesUseCase,
    CreateModelUseCase,
    CreateReciboConAplicacionesUseCase,
    CreateViajeUseCase,
    DeleteCircuitoUseCase,
    DeleteFacturaUseCase,
    DeleteModelUseCase,
    DeleteReciboUseCase,
    DeleteViajeUseCase,
    GetModelUseCase,
    ListModelUseCase,
    TerminarViajeUseCase,
    UpdateCircuitoSectionsUseCase,
    UpdateDetalleOperacionSectionsUseCase,
    UpdateFacturaUseCase,
    UpdateModelUseCase,
    UpdateReciboUseCase,
    UpdateViajeUseCase,
)
from ...modelo.viaje_service import ViajeWorkflowService
from .circuito_factory import CircuitoFactory
from .detalle_factura_factory import DetalleFacturaFactory
from .detalle_operacion_factory import DetalleOperacionFactory
from .factura_factory import FacturaFactory
from .recibo_factory import ReciboFactory
from .viaje_factory import ViajeFactory


def build_modelo_module(
    repository: ModeloCatalogRepository,
    session_factory: Callable[[], object],
) -> ModeloWorkflowService:
    """Compose Modelo domain services by use case and factories."""

    catalog_service = ModeloCatalogService(
        repository=repository,
        protected_model_names=frozenset({"factura", "recibo", "viaje", "circuito", "detalle_operacion"}),
    )
    unit_of_work = SQLAlchemyUnitOfWork(session_factory=session_factory)

    viaje_factory = ViajeFactory()
    circuito_factory = CircuitoFactory()
    detalle_operacion_factory = DetalleOperacionFactory()
    factura_factory = FacturaFactory()
    detalle_factura_factory = DetalleFacturaFactory()
    recibo_factory = ReciboFactory()

    list_viaje = ListModelUseCase(repository=repository, model_name="viaje")
    get_viaje = GetModelUseCase(repository=repository, model_name="viaje")
    list_factura = ListModelUseCase(repository=repository, model_name="factura")
    get_factura = GetModelUseCase(repository=repository, model_name="factura")
    list_recibo = ListModelUseCase(repository=repository, model_name="recibo")
    get_recibo = GetModelUseCase(repository=repository, model_name="recibo")
    list_circuito = ListModelUseCase(repository=repository, model_name="circuito")
    get_circuito = GetModelUseCase(repository=repository, model_name="circuito")
    create_circuito = CreateModelUseCase(repository=repository, model_name="circuito")
    update_circuito = UpdateModelUseCase(repository=repository, model_name="circuito")
    list_detalle_operacion = ListModelUseCase(repository=repository, model_name="detalle_operacion")
    get_detalle_operacion = GetModelUseCase(repository=repository, model_name="detalle_operacion")
    create_detalle_operacion = CreateModelUseCase(repository=repository, model_name="detalle_operacion")
    update_detalle_operacion = UpdateModelUseCase(repository=repository, model_name="detalle_operacion")
    delete_detalle_operacion = DeleteModelUseCase(repository=repository, model_name="detalle_operacion")

    create_viaje = CreateViajeUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
        viaje_factory=viaje_factory,
        circuito_factory=circuito_factory,
        detalle_operacion_factory=detalle_operacion_factory,
    )
    update_viaje = UpdateViajeUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    delete_viaje = DeleteViajeUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    terminar_viaje = TerminarViajeUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    create_factura = CreateFacturaConDetallesUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
        factura_factory=factura_factory,
        detalle_factura_factory=detalle_factura_factory,
    )
    update_factura = UpdateFacturaUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
        detalle_factura_factory=detalle_factura_factory,
    )
    delete_factura = DeleteFacturaUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    create_recibo = CreateReciboConAplicacionesUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
        recibo_factory=recibo_factory,
    )
    update_recibo = UpdateReciboUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    delete_recibo = DeleteReciboUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    delete_circuito = DeleteCircuitoUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    close_circuito = CloseCircuitoUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    update_circuito_sections = UpdateCircuitoSectionsUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )
    update_detalle_sections = UpdateDetalleOperacionSectionsUseCase(
        unit_of_work=unit_of_work,
        repository=repository,
    )

    viaje_service = ViajeWorkflowService(
        repository=repository,
        unit_of_work=unit_of_work,
        list_viaje_use_case=list_viaje,
        get_viaje_use_case=get_viaje,
        create_viaje_use_case=create_viaje,
        update_viaje_use_case=update_viaje,
        delete_viaje_use_case=delete_viaje,
        terminar_viaje_use_case=terminar_viaje,
    )
    factura_service = FacturaWorkflowService(
        repository=repository,
        unit_of_work=unit_of_work,
        list_factura_use_case=list_factura,
        get_factura_use_case=get_factura,
        create_factura_use_case=create_factura,
        update_factura_use_case=update_factura,
        delete_factura_use_case=delete_factura,
    )
    recibo_service = ReciboWorkflowService(
        repository=repository,
        unit_of_work=unit_of_work,
        list_recibo_use_case=list_recibo,
        get_recibo_use_case=get_recibo,
        create_recibo_use_case=create_recibo,
        update_recibo_use_case=update_recibo,
        delete_recibo_use_case=delete_recibo,
    )
    circuito_service = CircuitoWorkflowService(
        repository=repository,
        unit_of_work=unit_of_work,
        list_circuito_use_case=list_circuito,
        get_circuito_use_case=get_circuito,
        create_circuito_use_case=create_circuito,
        update_circuito_use_case=update_circuito,
        delete_circuito_use_case=delete_circuito,
        close_circuito_use_case=close_circuito,
        update_circuito_sections_use_case=update_circuito_sections,
    )
    detalle_operacion_service = DetalleOperacionWorkflowService(
        repository=repository,
        unit_of_work=unit_of_work,
        list_detalle_operacion_use_case=list_detalle_operacion,
        get_detalle_operacion_use_case=get_detalle_operacion,
        create_detalle_operacion_use_case=create_detalle_operacion,
        update_detalle_operacion_use_case=update_detalle_operacion,
        delete_detalle_operacion_use_case=delete_detalle_operacion,
        update_detalle_operacion_sections_use_case=update_detalle_sections,
    )

    return ModeloWorkflowService(
        catalog=catalog_service,
        viaje=viaje_service,
        factura=factura_service,
        recibo=recibo_service,
        circuito=circuito_service,
        detalle_operacion=detalle_operacion_service,
    )
