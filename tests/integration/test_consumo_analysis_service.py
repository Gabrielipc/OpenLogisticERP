from __future__ import annotations

from datetime import datetime

from openlogistic_erp.application.modelo.consumo_analysis_service import ConsumoAnalysisService
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import (
    Gasolinera,
    TipoOrdenCombustible,
    TipoReferencia,
    TipoViaje,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.combustible.criterios_consumo import (
    CriteriosConsumoCombustible,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.combustible.modelo_consumo_thermo import (
    ModeloConsumoThermo,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.gasto_real_camion import (
    GastoRealCamion,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.movimiento_adicional import (
    MovimientoAdicional,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.viaje import Viaje
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.ruta import Ruta
from tests.builders.modelo_seed import build_viaje_export_payload, seed_viaje_dependencies


def _create_export(modelo_workflow, deps: dict[str, int], *, detalle_operacion: dict | None = None):
    return modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            viaje={"temperatura": 10.0},
            detalle_operacion=detalle_operacion or {},
        )
    )


def _add_return_trip(modelo_workflow, deps: dict[str, int], circuito_id: int, *, peso: str = "42000"):
    return modelo_workflow.viaje.create(
        {
            "viaje": {
                "cliente_id": deps["cliente_id"],
                "conductor_id": deps["conductor_id"],
                "furgon_id": deps["furgon_id"],
                "camion_id": deps["camion_id"],
                "thermo_id": deps["thermo_id"],
                "tipo_viaje": TipoViaje.IMPOR,
                "_ruta_id": deps["ruta_id"],
                "_circuito_id": circuito_id,
                "fecha_posicionamiento": datetime(2026, 1, 16, 12, 0, 0),
                "descripcion": "Viaje de importacion de prueba",
            },
            "detalle_operacion": {
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 17, 10, 0, 0),
                    "peso": peso,
                    "_lugar_carga_id": deps["origen_id"],
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": Gasolinera.MOVIL,
                        "numero_orden": "IMP-CAM-001",
                        "galones_autorizados": 15,
                        "tipo": TipoOrdenCombustible.CAMION,
                    }
                ],
            },
        }
    )


def test_camion_analysis_uses_explicit_triangulado_flag_not_description(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = _create_export(
        modelo_workflow,
        deps,
        detalle_operacion={
            "descarga": {"fecha_descarga": datetime(2026, 1, 16, 10, 0, 0)},
            "ordenes_combustible": [
                {
                    "gasolinera": Gasolinera.NEDICSA,
                    "numero_orden": "EXP-CAM-001",
                    "galones_autorizados": 70,
                    "tipo": TipoOrdenCombustible.CAMION,
                }
            ],
        },
    )
    circuito_id = int(created["_circuito_id"])

    service = ConsumoAnalysisService()
    with session_factory() as session:
        circuito = session.get(Viaje, int(created["id"]))._circuito
        session.add(GastoRealCamion(circuito_id=circuito_id, retorno_camion=10))
        session.add(
            MovimientoAdicional(
                circuito_id=circuito_id,
                ruta_id=deps["ruta_id"],
                descripcion="Movimiento triangulado escrito en texto libre",
                es_triangulado=False,
            )
        )
        session.flush()

        plain_text_result = service.analyze_camion(session, circuito_id)
        assert plain_text_result["type"] == "BASE"
        assert plain_text_result["consumo_real"] == "60.00"
        assert circuito is not None

        movimiento = circuito.movimientos_adicionales[0]
        movimiento.es_triangulado = True
        session.flush()

        flagged_result = service.analyze_camion(session, circuito_id)

    assert flagged_result["type"] == "TRIANGULADO"
    assert flagged_result["criteria"]["ruta_movimiento_id"] == deps["ruta_id"]


def test_camion_por_peso_detection_uses_destination_code_not_id(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        ruta = session.get(Ruta, deps["ruta_id"])
        ruta.destino.codigo = "CIUDAD_HIDALGO"
        ruta.destino.descripcion = "Destino con otro nombre"
        session.commit()

    created = _create_export(
        modelo_workflow,
        deps,
        detalle_operacion={
            "descarga": {"fecha_descarga": datetime(2026, 1, 16, 10, 0, 0)},
            "ordenes_combustible": [
                {
                    "gasolinera": Gasolinera.NEDICSA,
                    "numero_orden": "EXP-CAM-002",
                    "galones_autorizados": 80,
                    "tipo": TipoOrdenCombustible.CAMION,
                }
            ],
        },
    )
    circuito_id = int(created["_circuito_id"])
    _add_return_trip(modelo_workflow, deps, circuito_id, peso="42000")

    with session_factory() as session:
        session.add(GastoRealCamion(circuito_id=circuito_id, retorno_camion=5))
        session.flush()

        result = ConsumoAnalysisService().analyze_camion(session, circuito_id)

    assert result["type"] == "POR_PESO"
    assert result["criteria"]["peso_min"] == "42000"
    assert result["criteria"]["peso_max"] == "42000"
    assert result["consumo_real"] == "90.00"


def test_camion_analysis_falls_back_to_export_orders_when_no_reference_exists(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = _create_export(
        modelo_workflow,
        deps,
        detalle_operacion={
            "ordenes_combustible": [
                {
                    "gasolinera": Gasolinera.NEDICSA,
                    "numero_orden": "EXP-CAM-003",
                    "galones_autorizados": 75,
                    "tipo": TipoOrdenCombustible.CAMION,
                }
            ],
        },
    )
    circuito_id = int(created["_circuito_id"])

    with session_factory() as session:
        session.add(GastoRealCamion(circuito_id=circuito_id, retorno_camion=15))
        session.flush()

        result = ConsumoAnalysisService().analyze_camion(session, circuito_id)

    assert result["status"] == "ok"
    assert result["type"] == "BASE"
    assert result["consumo_estimado"] == "75.00"
    assert result["consumo_real"] == "60.00"
    assert result["diferencia"] == "-15.00"


def test_thermo_analysis_returns_missing_model_without_breaking_detail(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = _create_export(
        modelo_workflow,
        deps,
        detalle_operacion={
            "gasto_real_thermo": {"combustible_base_thermo": 40, "restante_thermo": 0},
        },
    )

    with session_factory() as session:
        result = ConsumoAnalysisService().analyze_thermo(session, int(created["id"]))

    assert result["status"] == "missing_model"
    assert result["type"] == "THERMO"
    assert result["consumo_real"] == "40.00"
    assert result["consumo_estimado"] == ""
    assert result["messages"] == ["No hay modelo de consumo para el thermo seleccionado."]


def test_thermo_analysis_compares_real_consumption_against_model_estimate(
    session_factory,
    modelo_workflow,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = _create_export(
        modelo_workflow,
        deps,
        detalle_operacion={
            "actividad_thermo": {
                "fecha_hora_encendido": datetime(2026, 1, 16, 8, 0, 0),
                "fecha_hora_apagado": datetime(2026, 1, 16, 18, 0, 0),
            },
            "gasto_real_thermo": {"combustible_base_thermo": 40, "restante_thermo": 15},
            "movimientos_combustible": [{"galones_transferidos": 5, "nota": "Transferencia"}],
            "ordenes_combustible": [
                {
                    "gasolinera": Gasolinera.NEDICSA,
                    "numero_orden": "EXP-TH-001",
                    "galones_autorizados": 10,
                    "tipo": TipoOrdenCombustible.THERMO,
                }
            ],
        },
    )

    with session_factory() as session:
        session.add(ModeloConsumoThermo(thermo_id=deps["thermo_id"], pendiente=0.0, interseccion=2.0))
        session.flush()

        result = ConsumoAnalysisService().analyze_thermo(session, int(created["id"]))

    assert result["status"] == "ok"
    assert result["consumo_real"] == "40.00"
    assert result["consumo_estimado"] == "5.00"
    assert result["diferencia"] == "35.00"
    assert result["rendimiento"] == "0.25"
