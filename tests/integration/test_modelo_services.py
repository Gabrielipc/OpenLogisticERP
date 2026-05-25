from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest

from openlogistic_erp.application.modelo.contracts import InvalidIdentifierError, InvalidPayloadError
from openlogistic_erp.application.modelo.services import ModeloCatalogService
from openlogistic_erp.domain.modelo.dtos import (
    CatalogRecordDTO,
    CatalogSchemaDTO,
    FieldKind,
    FieldOptionDTO,
    FieldSchemaDTO,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import (
    EstadoCamion,
    EstadoCircuito,
    EstadoConductor,
    EstadoDetalle,
    EstadoFactura,
    EstadoViaje,
    TipoViaje,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.factura import Factura
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.recibo import Recibo
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.circuito import Circuito
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.viaje import Viaje
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.camion import Camion
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.conductor import Conductor
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.thermo import Thermo
from tests.builders.modelo_seed import (
    build_factura_payload,
    build_viaje_export_payload,
    create_camion,
    create_cliente,
    create_conductor,
    create_furgon,
    create_ruta,
    create_thermo,
    create_ubicacion,
    get_camion,
    get_conductor,
    get_thermo,
    seed_viaje_dependencies,
)


class FakeCatalogRepository:
    def __init__(self) -> None:
        self.created_payload: dict[str, Any] | None = None

    def get_schema(self, model_name: str) -> CatalogSchemaDTO:
        return CatalogSchemaDTO(
            catalog_name=model_name,
            title="Eventos",
            fields=(
                FieldSchemaDTO(name="cantidad", label="Cantidad", kind=FieldKind.INTEGER, required=True, nullable=False),
                FieldSchemaDTO(name="monto", label="Monto", kind=FieldKind.MONEY, required=True, nullable=False),
                FieldSchemaDTO(name="fecha", label="Fecha", kind=FieldKind.DATE, required=True, nullable=False),
                FieldSchemaDTO(name="inicio", label="Inicio", kind=FieldKind.DATETIME, required=True, nullable=False),
                FieldSchemaDTO(
                    name="estado",
                    label="Estado",
                    kind=FieldKind.ENUM,
                    required=True,
                    nullable=False,
                    options=(
                        FieldOptionDTO(value="Activo", label="Activo"),
                        FieldOptionDTO(value="Inactivo", label="Inactivo"),
                    ),
                ),
            ),
        )

    def create_record(self, model_name: str, data):
        self.created_payload = dict(data)
        return CatalogRecordDTO(catalog_name=model_name, values={"id": 1, **dict(data)})

    def update_record(self, model_name: str, record_id: int, data):
        return CatalogRecordDTO(catalog_name=model_name, values={"id": record_id, **dict(data)})

    def list_models(self) -> list[str]:
        return ["evento"]


def test_viaje_service_only_resolves_available_conductor_equipment_defaults(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        active_camion = create_camion(session, placa="DEF-ACTIVO", estado=EstadoCamion.ACTIVO)
        unavailable_furgon = create_furgon(session, placa="DEF-VIAJE", estado=EstadoCamion.ENVIAJE)
        unavailable_thermo = create_thermo(session, codigo="DEF-BAJA", estado=EstadoCamion.BAJA)
        conductor = create_conductor(
            session,
            nombre="Defaults",
            apellido="Disponibles",
            camion_id=active_camion.id,
            furgon_id=unavailable_furgon.id,
            thermo_id=unavailable_thermo.id,
        )
        session.commit()
        conductor_id = int(conductor.id)
        active_camion_id = int(active_camion.id)

    defaults = modelo_workflow.viaje.resolve_conductor_equipment_defaults(conductor_id)

    assert defaults == {
        "camion_id": active_camion_id,
        "furgon_id": None,
        "thermo_id": None,
    }


def test_catalog_service_normalizes_schema_aware_payloads_before_repository():
    repository = FakeCatalogRepository()
    service = ModeloCatalogService(repository=repository) # type: ignore

    created = service.create(
        "evento",
        {
            "cantidad": "7",
            "monto": "125.5",
            "fecha": "08/04/2026",
            "inicio": "08/04/2026 14:30",
            "estado": "Activo",
        },
    )

    assert repository.created_payload == {
        "cantidad": 7,
        "monto": "125.50",
        "fecha": "2026-04-08",
        "inicio": "2026-04-08T14:30",
        "estado": "Activo",
    }
    assert created["cantidad"] == 7


def test_catalog_service_rejects_unknown_and_invalid_typed_values():
    repository = FakeCatalogRepository()
    service = ModeloCatalogService(repository=repository) # type: ignore

    with pytest.raises(InvalidPayloadError, match="Cantidad: Debe ser un numero entero."):
        service.create(
            "evento",
            {
                "cantidad": "siete",
                "monto": "125.5",
                "fecha": "08/04/2026",
                "inicio": "08/04/2026 14:30",
                "estado": "Activo",
            },
        )

    with pytest.raises(InvalidPayloadError, match="campo no permitido"):
        service.create(
            "evento",
            {
                "cantidad": "7",
                "monto": "125.5",
                "fecha": "08/04/2026",
                "inicio": "08/04/2026 14:30",
                "estado": "Activo",
                "extra": "nope",
            },
        )


def test_viaje_service_validates_payloads_and_identifiers(modelo_workflow):
    with pytest.raises(InvalidPayloadError):
        modelo_workflow.viaje.create(None)

    with pytest.raises(InvalidIdentifierError):
        modelo_workflow.viaje.get(0)

    with pytest.raises(InvalidIdentifierError):
        modelo_workflow.viaje.update(0, {"descripcion": "x"})

    with pytest.raises(InvalidPayloadError):
        modelo_workflow.viaje.update(1, None)

    with pytest.raises(InvalidIdentifierError):
        modelo_workflow.viaje.delete(None)


def test_terminar_viaje_exportacion_cierra_detalle_y_pasa_conductor_a_instrucciones(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 9, 0, 0),
                }
            },
        )
    )

    modelo_workflow.viaje.terminar_viaje(created["id"])

    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        conductor = session.get(Conductor, deps["conductor_id"])
        camion = session.get(Camion, deps["camion_id"])
        thermo = session.get(Thermo, deps["thermo_id"])

        assert viaje is not None
        assert viaje.tipo_viaje == TipoViaje.EXPOR
        assert viaje.estado == EstadoViaje.FINALIZADO
        assert viaje.detalle_operacion is not None
        assert viaje.detalle_operacion.estado == EstadoDetalle.CERRADO
        assert conductor is not None
        assert conductor.estado == EstadoConductor.INSTRUCCIONES
        assert camion is not None
        assert camion.estado == EstadoCamion.ENVIAJE
        assert thermo is not None
        assert thermo.estado == EstadoCamion.ENVIAJE


def test_importacion_finalizada_permite_cerrar_circuito_y_libera_equipo(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 12, 0, 0),
                }
            },
        )
    )

    importacion = modelo_workflow.viaje.create(
        {
            "viaje": {
                "cliente_id": deps["cliente_id"],
                "conductor_id": deps["conductor_id"],
                "furgon_id": deps["furgon_id"],
                "camion_id": deps["camion_id"],
                "thermo_id": deps["thermo_id"],
                "tipo_viaje": TipoViaje.IMPOR,
                "_ruta_id": deps["ruta_id"],
                "_circuito_id": exportacion["_circuito_id"],
                "fecha_posicionamiento": datetime(2026, 1, 17, 8, 0, 0),
            },
            "detalle_operacion": {
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 18, 14, 30, 0),
                }
            },
        }
    )

    modelo_workflow.viaje.terminar_viaje(importacion["id"])
    closed = modelo_workflow.circuito.close_circuito(exportacion["_circuito_id"])

    assert closed is True

    with session_factory() as session:
        circuito = session.get(Circuito, exportacion["_circuito_id"])
        viaje_vuelta = session.get(Viaje, importacion["id"])

        assert circuito is not None
        assert circuito.estado == EstadoCircuito.FINALIZADO
        assert circuito.fecha_fin == datetime(2026, 1, 18, 14, 30, 0)
        assert viaje_vuelta is not None
        assert viaje_vuelta.estado == EstadoViaje.FINALIZADO
        assert viaje_vuelta.detalle_operacion is not None
        assert viaje_vuelta.detalle_operacion.estado == EstadoDetalle.CERRADO

    camion = get_camion(session_factory, deps["camion_id"])
    conductor = get_conductor(session_factory, deps["conductor_id"])
    thermo = get_thermo(session_factory, deps["thermo_id"])

    assert camion is not None
    assert cast(EstadoCamion, camion.estado) == EstadoCamion.ACTIVO
    assert conductor is not None
    assert cast(EstadoConductor, conductor.estado) == EstadoConductor.DISPONIBLE
    assert thermo is not None
    assert cast(EstadoCamion, thermo.estado) == EstadoCamion.ACTIVO


def test_viaje_service_detail_summary_expands_operational_sections_for_export(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        lugar_carga = create_ubicacion(session, descripcion="Puerto Corinto")
        session.commit()

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_posicionamiento": datetime(2026, 1, 16, 7, 0, 0),
                    "fecha_despacho": datetime(2026, 1, 16, 9, 0, 0),
                    "fecha_descarga": datetime(2026, 1, 17, 11, 30, 0),
                    "peso": "42000",
                    "_lugar_carga_id": lugar_carga.id,
                    "_dias_viajados": 2,
                },
                "actividad_thermo": {
                    "fecha_hora_encendido": datetime(2026, 1, 16, 7, 15, 0),
                    "fecha_hora_apagado": datetime(2026, 1, 17, 11, 0, 0),
                    "_duracion_horas": 27.75,
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 42.5,
                    "restante_thermo": 8.5,
                    "_consumo_thermo": 34.0,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "OT-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    },
                    {
                        "gasolinera": "MOVIL",
                        "numero_orden": "OT-002",
                        "galones_autorizados": 35,
                        "tipo": "THERMO",
                    },
                ],
            },
        )
    )

    summary = modelo_workflow.viaje.get_detail_summary(created["id"])

    assert summary["viaje_summary"]["id"] == created["id"]
    assert summary["viaje_summary"]["cliente_label"] != ""
    assert summary["viaje_summary"]["ruta_label"] != ""
    assert "dias_viajados" not in summary["viaje_summary"]
    assert "consumo_thermo" not in summary["viaje_summary"]
    assert summary["visible_sections"] == ["descarga", "combustible_thermo", "ordenes_combustible"]
    assert summary["descarga"]["_lugar_carga_id"] == lugar_carga.id
    assert summary["descarga"]["lugar_carga_label"] == "Puerto Corinto"
    assert summary["descarga"]["_dias_viajados"] == 3
    assert summary["actividad_thermo"]["_duracion_horas"] == "27.75"
    assert summary["gasto_real_thermo"]["restante_thermo"] == "8.50"
    assert summary["gasto_real_thermo"]["_consumo_thermo"] == "34.00"
    assert len(summary["ordenes_combustible"]) == 2


def test_viaje_service_detail_summary_omits_thermo_section_for_import(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 12, 0, 0),
                }
            },
        )
    )

    importacion = modelo_workflow.viaje.create(
        {
            "viaje": {
                "cliente_id": deps["cliente_id"],
                "conductor_id": deps["conductor_id"],
                "furgon_id": deps["furgon_id"],
                "camion_id": deps["camion_id"],
                "thermo_id": deps["thermo_id"],
                "tipo_viaje": TipoViaje.IMPOR,
                "_ruta_id": deps["ruta_id"],
                "_circuito_id": exportacion["_circuito_id"],
                "fecha_posicionamiento": datetime(2026, 1, 17, 8, 0, 0),
            },
            "detalle_operacion": {
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 18, 14, 30, 0),
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "MOVIL",
                        "numero_orden": "IMP-001",
                        "galones_autorizados": 40,
                        "tipo": "CAMION",
                    }
                ],
            },
        }
    )

    summary = modelo_workflow.viaje.get_detail_summary(importacion["id"])

    assert summary["visible_sections"] == ["descarga", "ordenes_combustible"]
    assert summary["actividad_thermo"] == {}
    assert summary["gasto_real_thermo"] == {}


def test_viaje_service_detail_summary_only_shows_descarga_for_vacio(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    vacio = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "viaje_ida_id": exportacion["id"],
            },
            "detalle_operacion": {
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 18, 14, 30, 0),
                }
            },
        }
    )

    summary = modelo_workflow.viaje.get_detail_summary(vacio["id"])

    assert summary["visible_sections"] == ["descarga"]


def test_recibo_create_and_update_recalculates_factura_status(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session)
        session.commit()

    factura = modelo_workflow.factura.create(build_factura_payload(cliente.id, []))
    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": "REC-001",
                "fecha_emision": datetime(2026, 1, 21, 10, 0, 0),
                "cliente_id": cliente.id,
                "monto": 150,
            },
            "facturas": [
                {
                    "factura_id": factura["id"],
                    "monto": 150,
                }
            ],
        }
    )

    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        recibo_row = session.get(Recibo, recibo["id"])

        assert factura_row is not None
        assert factura_row.estado == EstadoFactura.PAGADA
        assert str(factura_row.saldo_restante) == "0.00"
        assert recibo_row is not None
        assert str(recibo_row.saldo_disponible) == "0.00"

    modelo_workflow.recibo.update(
        recibo["id"],
        {
            "recibo": {
                "monto": 50,
            },
            "facturas": [
                {
                    "factura_id": factura["id"],
                    "monto": 50,
                }
            ]
        },
    )

    with session_factory() as session:
        factura_row = session.get(Factura, factura["id"])
        recibo_row = session.get(Recibo, recibo["id"])

        assert factura_row is not None
        assert factura_row.estado == EstadoFactura.PAGADAPAR
        assert str(factura_row.saldo_restante) == "100.00"
        assert recibo_row is not None
        assert str(recibo_row.saldo_disponible) == "0.00"


def test_recibo_rejects_missing_facturas_and_leftover_balance(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session)
        session.commit()

    factura = modelo_workflow.factura.create(build_factura_payload(cliente.id, []))

    with pytest.raises(InvalidPayloadError, match="al menos una factura asignada"):
        modelo_workflow.recibo.create(
            {
                "recibo": {
                    "referencia": "REC-EMPTY",
                    "fecha_emision": datetime(2026, 1, 22, 10, 0, 0),
                    "cliente_id": cliente.id,
                    "monto": 150,
                },
                "facturas": [],
            }
        )

    with pytest.raises(ValueError, match="debe consumir todo el monto del recibo"):
        modelo_workflow.recibo.create(
            {
                "recibo": {
                    "referencia": "REC-PARCIAL",
                    "fecha_emision": datetime(2026, 1, 22, 11, 0, 0),
                    "cliente_id": cliente.id,
                    "monto": 150,
                },
                "facturas": [
                    {
                        "factura_id": factura["id"],
                        "monto": 100,
                    }
                ],
            }
        )


def test_recibo_update_rejects_missing_facturas_and_leftover_balance(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session)
        session.commit()

    factura = modelo_workflow.factura.create(build_factura_payload(cliente.id, []))
    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": "REC-UPD",
                "fecha_emision": datetime(2026, 1, 23, 10, 0, 0),
                "cliente_id": cliente.id,
                "monto": 150,
            },
            "facturas": [
                {
                    "factura_id": factura["id"],
                    "monto": 150,
                }
            ],
        }
    )

    with pytest.raises(InvalidPayloadError, match="al menos una factura asignada"):
        modelo_workflow.recibo.update(recibo["id"], {"facturas": []})

    with pytest.raises(ValueError, match="debe consumir todo el monto del recibo"):
        modelo_workflow.recibo.update(
            recibo["id"],
            {
                "facturas": [
                    {
                        "factura_id": factura["id"],
                        "monto": 100,
                    }
                ]
            },
        )
