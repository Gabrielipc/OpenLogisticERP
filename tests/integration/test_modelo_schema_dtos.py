from __future__ import annotations

from uuid import uuid4

from openlogistic_erp.application.modelo import CreateFacturaCommand, CreateViajeCommand, UpdateFacturaCommand
from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.domain.modelo.catalog_queries import CatalogFilter, CatalogFilterOperator
from openlogistic_erp.domain.modelo.dtos import CatalogPageDTO, CatalogRecordDTO, FieldKind
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
from openlogistic_erp.infrastructure.persistence.modelo.repositories.sqlalchemy_modelo_repository import (
    SqlAlchemyModeloRepository,
)
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import TipoImpuesto
from tests.builders.modelo_seed import build_factura_payload, build_viaje_export_payload, create_cliente, create_impuesto, seed_viaje_dependencies


def test_catalog_schema_exposes_typed_metadata_for_cliente_and_camion(session_factory):
    repository = SqlAlchemyModeloRepository(session_factory)

    cliente_schema = repository.get_schema("cliente")
    camion_schema = repository.get_schema("camion")
    factura_schema = repository.get_schema("factura")

    assert cliente_schema.catalog_name == "cliente"
    assert cliente_schema.title == "Gestión de Clientes"
    assert cliente_schema.search_field == "nombre"
    assert cliente_schema.field("nombre").kind == FieldKind.TEXT
    assert cliente_schema.field("nombre").required is True
    assert cliente_schema.field("nombre").list_width >= 180
    assert cliente_schema.field("direccion").kind == FieldKind.MULTILINE
    assert cliente_schema.field("direccion").list_width >= 240
    assert cliente_schema.field("facturable").kind == FieldKind.BOOL
    assert cliente_schema.field("facturable").list_width == 90

    assert camion_schema.catalog_name == "camion"
    assert camion_schema.field("anio").kind == FieldKind.INTEGER
    assert camion_schema.field("estado").kind == FieldKind.ENUM
    assert any(option.value == "Activo" for option in camion_schema.field("estado").options)

    assert cliente_schema.search_fields[:2] == ("nombre", "ruc")
    cliente_nombre = cliente_schema.field("nombre")
    assert cliente_nombre.searchable is True
    assert cliente_nombre.supported_operators == ("contains", "eq")

    cliente_reference = factura_schema.field("cliente_id").reference
    assert factura_schema.field("cliente_id").kind == FieldKind.REFERENCE
    assert cliente_reference is not None
    assert cliente_reference.lookup_key == "factura.cliente_id"
    assert factura_schema.field("cliente_id").display_field_key == "cliente_label"
    assert factura_schema.field("cliente_id").list_visible is False
    assert factura_schema.field("cliente_label").list_visible is True
    assert factura_schema.field("cliente_id").searchable is True
    assert factura_schema.field("cliente_id").supported_operators == ("eq", "in", "contains")
    assert factura_schema.field("cliente_id").multi_value is True


def test_catalog_schema_exposes_reference_metadata_for_ruta(session_factory):
    repository = SqlAlchemyModeloRepository(session_factory)

    ruta_schema = repository.get_schema("ruta")

    assert ruta_schema.field("origen_id").kind == FieldKind.REFERENCE
    assert ruta_schema.field("origen_id").reference is not None
    assert ruta_schema.field("origen_id").reference.lookup_key == "ruta.origen_id"
    assert ruta_schema.field("origen_id").display_field_key == "origen_label"
    assert ruta_schema.field("destino_id").kind == FieldKind.REFERENCE
    assert ruta_schema.field("destino_id").reference is not None
    assert ruta_schema.field("origen_label").form_visible is False
    assert ruta_schema.field("origen_label").list_visible is True


def test_catalog_schema_exposes_reference_metadata_for_conductor(session_factory):
    repository = SqlAlchemyModeloRepository(session_factory)

    conductor_schema = repository.get_schema("conductor")

    assert conductor_schema.field("camion_id").kind == FieldKind.REFERENCE
    assert conductor_schema.field("camion_id").reference is not None
    assert conductor_schema.field("camion_id").reference.lookup_key == "conductor.camion_id"
    assert conductor_schema.field("camion_id").display_field_key == "camion_label"
    assert conductor_schema.field("camion_id").list_visible is False
    assert conductor_schema.field("camion_label").list_visible is True
    assert conductor_schema.field("furgon_id").reference is not None
    assert conductor_schema.field("thermo_id").reference is not None


def test_catalog_services_and_queries_return_dtos(session_factory, modelo_workflow):
    token = uuid4().hex[:8].upper()
    created = modelo_workflow.catalog.create(
        "cliente",
        {
            "nombre": f"Cliente DTO {token}",
            "ruc": f"DTO-{token}",
            "direccion": f"Masaya {token}",
            "facturable": True,
        },
    )

    assert isinstance(created, CatalogRecordDTO)
    assert created["nombre"] == f"Cliente DTO {token}"

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    result = query_service.list_page(
        "cliente",
        page=0,
        page_size=20,
        filters=(CatalogFilter(field="ruc", operator=CatalogFilterOperator.EQ, value=f"DTO-{token}"),),
    )

    assert isinstance(result, CatalogPageDTO)
    assert all(isinstance(row, CatalogRecordDTO) for row in result.rows)
    assert any(row["id"] == created["id"] for row in result.rows)


def test_catalog_repository_serializes_strenum_values_to_plain_strings(session_factory):
    repository = SqlAlchemyModeloRepository(session_factory)

    with session_factory() as session:
        impuesto = create_impuesto(session, tipo=TipoImpuesto.IVA, porcentaje=15.0)
        session.commit()
        impuesto_id = int(impuesto.id)

    record = repository.get_record("impuesto", impuesto_id)

    assert record is not None
    assert record["tipo"] == "IVA"
    assert isinstance(record["tipo"], str)


def test_workflow_services_accept_command_dtos(session_factory, modelo_workflow):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente = create_cliente(session, ruc=f"CMD-{uuid4().hex[:8]}")
        impuesto = create_impuesto(session, tipo=TipoImpuesto.IVA, porcentaje=15.0)
        session.commit()

    viaje = modelo_workflow.viaje.create(CreateViajeCommand(build_viaje_export_payload(deps)))
    assert viaje is not None
    assert viaje["id"] > 0

    factura = modelo_workflow.factura.create(CreateFacturaCommand(build_factura_payload(cliente.id, [impuesto.id])))
    assert factura is not None

    updated = modelo_workflow.factura.update(
        UpdateFacturaCommand(
            record_id=int(factura["id"]),
            payload={"factura": {"numero_factura": "FAC-CMD-001"}, "impuestos": [impuesto.id]},
        )
    )
    assert updated is not None
    assert updated["numero_factura"] == "FAC-CMD-001"
