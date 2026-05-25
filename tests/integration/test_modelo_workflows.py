from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import cast

import pytest

from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import (
    EstadoCamion,
    EstadoCircuito,
    EstadoConductor,
    EstadoViaje,
    Moneda,
    TipoImpuesto,
    TipoViaje,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.detalle_operacion import (
    DetalleOperacion,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.circuito import (
    Circuito,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.factura import (
    Factura,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.recibo import (
    Recibo,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.recibo_factura import (
    ReciboFactura,
)
from tests.builders.modelo_seed import (
    build_factura_payload,
    build_viaje_export_payload,
    create_cliente,
    create_ruta,
    create_impuesto,
    get_camion,
    get_circuito,
    get_conductor,
    get_thermo,
    get_viaje,
    seed_viaje_dependencies,
)


def test_viaje_create_exportacion_success_and_sets_equipment_status(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    assert created is not None
    assert created["id"] > 0
    assert created["cliente_id"] == deps["cliente_id"]
    assert created["tipo_viaje"] == TipoViaje.EXPOR

    camion = get_camion(session_factory, deps["camion_id"])
    conductor = get_conductor(session_factory, deps["conductor_id"])
    thermo = get_thermo(session_factory, deps["thermo_id"])

    assert camion is not None
    assert cast(EstadoCamion, camion.estado) == EstadoCamion.ENVIAJE
    assert conductor is not None
    assert cast(EstadoConductor, conductor.estado) == EstadoConductor.VIAJE
    assert thermo is not None
    assert cast(EstadoCamion, thermo.estado) == EstadoCamion.ENVIAJE


def test_viaje_create_injects_fecha_posicionamiento_into_descarga(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = build_viaje_export_payload(deps)
    expected_fecha = payload["viaje"]["fecha_posicionamiento"]
    created = modelo_workflow.viaje.create(payload)

    with session_factory() as session:
        detalle = session.query(DetalleOperacion).filter_by(viaje_id=created["id"]).one_or_none()
        assert detalle is not None
        assert detalle.descarga is not None
        assert detalle.descarga.fecha_posicionamiento == expected_fecha



def test_viaje_update_and_delete(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = build_viaje_export_payload(deps)
    payload["detalle_operacion"] = {
        "descarga": {
            "fecha_descarga": payload["viaje"]["fecha_posicionamiento"],
        }
    }
    created = modelo_workflow.viaje.create(payload)

    updated = modelo_workflow.viaje.update(
        created["id"],
        {
            "descripcion": "Viaje actualizado",
        },
    )
    assert updated is not None
    assert updated["descripcion"] == "Viaje actualizado"

    with session_factory() as session:
        detalle = session.query(DetalleOperacion).filter_by(viaje_id=created["id"]).one_or_none()
        assert detalle is not None

    deleted = modelo_workflow.viaje.delete(created["id"])
    assert deleted is True
    assert get_viaje(session_factory, created["id"]) is None
    with session_factory() as session:
        detalle = session.query(DetalleOperacion).filter_by(viaje_id=created["id"]).one_or_none()
        assert detalle is None


def test_viaje_delete_last_trip_removes_empty_circuito(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])

    deleted = modelo_workflow.viaje.delete(created["id"])

    assert deleted is True
    assert get_viaje(session_factory, created["id"]) is None
    assert get_circuito(session_factory, circuito_id) is None


def test_viaje_delete_keeps_circuito_when_other_trip_exists(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={"descarga": {"fecha_descarga": "2026-01-15T10:00"}},
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
                "viaje_ida_id": exportacion["id"],
                "fecha_posicionamiento": datetime(2026, 1, 16, 12, 0, 0),
            }
        }
    )
    circuito_id = int(exportacion["_circuito_id"])

    deleted = modelo_workflow.viaje.delete(importacion["id"])

    assert deleted is True
    assert get_circuito(session_factory, circuito_id) is not None


def test_viaje_terminar_importacion_cierra_circuito(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={"descarga": {"fecha_descarga": "2026-01-15T10:00"}},
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
                "viaje_ida_id": exportacion["id"],
                "fecha_posicionamiento": datetime(2026, 1, 16, 12, 0, 0),
            }
        }
    )

    modelo_workflow.viaje.terminar_viaje(importacion["id"])

    with session_factory() as session:
        circuito = session.get(Circuito, int(exportacion["_circuito_id"]))
        assert circuito is not None
        assert circuito.estado == EstadoCircuito.FINALIZADO


def test_viaje_terminar_vacio_cierra_circuito(modelo_workflow, session_factory):
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
            }
        }
    )

    modelo_workflow.viaje.terminar_viaje(vacio["id"])

    with session_factory() as session:
        circuito = session.get(Circuito, int(exportacion["_circuito_id"]))
        assert circuito is not None
        assert circuito.estado == EstadoCircuito.FINALIZADO


def test_guardar_detalle_operacion_sections_moves_pending_viaje_to_en_curso(
    modelo_workflow,
    session_factory,
):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    created_detalle = modelo_workflow.detalle_operacion.create({"viaje_id": created["id"]})

    with session_factory() as session:
        detalle = session.get(DetalleOperacion, created_detalle["id"])
        assert detalle is not None
        detalle_id = detalle.id
        viaje = detalle.viaje
        assert viaje is not None
        assert viaje.estado == EstadoViaje.PENDIENTE

    modelo_workflow.detalle_operacion.guardar_secciones_detalle_operacion(
        detalle_id,
        {
            "descarga": {
                "fecha_descarga": "2026-01-16T10:00",
            }
        },
    )

    viaje = get_viaje(session_factory, created["id"])
    assert viaje is not None
    assert viaje.estado == EstadoViaje.ENCURSO



def test_viaje_importacion_requires_existing_circuito(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = {
        "viaje": {
            "cliente_id": deps["cliente_id"],
            "conductor_id": deps["conductor_id"],
            "furgon_id": deps["furgon_id"],
            "camion_id": deps["camion_id"],
            "thermo_id": deps["thermo_id"],
            "tipo_viaje": TipoViaje.IMPOR,
            "_ruta_id": deps["ruta_id"],
            "_circuito_id": 999999,
            "fecha_posicionamiento": build_viaje_export_payload(deps)["viaje"]["fecha_posicionamiento"],
        }
    }

    with pytest.raises(ValueError, match="Circuito de importaci"):
        modelo_workflow.viaje.create(payload)


def test_viaje_exportacion_requires_cliente_explicitly(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    payload = build_viaje_export_payload(deps)
    payload["viaje"]["cliente_id"] = None

    with pytest.raises(ValueError, match="cliente_id es obligatorio"):
        modelo_workflow.viaje.create(payload)


def test_viaje_importacion_requires_cliente_explicitly(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    payload = {
        "viaje": {
            "cliente_id": None,
            "conductor_id": deps["conductor_id"],
            "furgon_id": deps["furgon_id"],
            "camion_id": deps["camion_id"],
            "thermo_id": deps["thermo_id"],
            "tipo_viaje": TipoViaje.IMPOR,
            "_ruta_id": deps["ruta_id"],
            "viaje_ida_id": exportacion["id"],
            "fecha_posicionamiento": build_viaje_export_payload(deps)["viaje"]["fecha_posicionamiento"],
        }
    }

    with pytest.raises(ValueError, match="cliente_id es obligatorio"):
        modelo_workflow.viaje.create(payload)


def test_viaje_vacio_rejects_cliente_explicitly(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    payload = {
        "viaje": {
            "cliente_id": deps["cliente_id"],
            "tipo_viaje": TipoViaje.VACIO,
            "viaje_ida_id": exportacion["id"],
        }
    }

    with pytest.raises(ValueError, match="no debe tener cliente"):
        modelo_workflow.viaje.create(payload)


def test_viaje_vacio_uses_reverse_route_from_exportacion(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        ruta_retorno = create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        ruta_retorno_id = int(ruta_retorno.id)
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    created = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "viaje_ida_id": exportacion["id"],
            }
        }
    )

    assert created is not None
    assert created["cliente_id"] is None
    assert created["_ruta_id"] == ruta_retorno_id


def test_viaje_vacio_generates_automatic_reference_and_description(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"referencia": "EXP-IDA-001"})
    )
    created = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "viaje_ida_id": exportacion["id"],
            }
        }
    )

    assert created["referencia"] == f"Viaje vacío #{created['id']}"
    assert created["descripcion"] == "Viaje de vuelta vacío para el viaje de exportación EXP-IDA-001"


def test_viaje_vacio_description_uses_export_fallback_label(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    created = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "viaje_ida_id": exportacion["id"],
            }
        }
    )

    assert created["descripcion"] == f"Viaje de vuelta vacío para el viaje de exportación Viaje #{exportacion['id']}"


def test_viaje_vacio_preserves_automatic_text_on_update(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        create_ruta(session, origen_id=deps["destino_id"], destino_id=deps["origen_id"])
        session.commit()

    exportacion = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"referencia": "EXP-IDA-002"})
    )
    created = modelo_workflow.viaje.create(
        {
            "viaje": {
                "tipo_viaje": TipoViaje.VACIO,
                "viaje_ida_id": exportacion["id"],
            }
        }
    )

    updated = modelo_workflow.viaje.update(
        created["id"],
        {
            "referencia": "REF-MANUAL",
            "descripcion": "Descripcion manual",
        },
    )

    assert updated["referencia"] == f"Viaje vacío #{created['id']}"
    assert updated["descripcion"] == "Viaje de vuelta vacío para el viaje de exportación EXP-IDA-002"


def test_viaje_vacio_requires_existing_reverse_route(modelo_workflow, session_factory):
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    exportacion = modelo_workflow.viaje.create(build_viaje_export_payload(deps))

    with pytest.raises(ValueError, match="ruta de retorno"):
        modelo_workflow.viaje.create(
            {
                "viaje": {
                    "tipo_viaje": TipoViaje.VACIO,
                    "viaje_ida_id": exportacion["id"],
                }
            }
        )



def test_factura_create_calculates_subtotal_and_total(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="J031000000111")
        impuesto = create_impuesto(session, tipo=TipoImpuesto.IVA, porcentaje=15.0)
        session.commit()

    created = modelo_workflow.factura.create(build_factura_payload(cliente.id, [impuesto.id]))

    assert created is not None
    assert created["id"] > 0

    with session_factory() as session:
        factura = session.get(Factura, created["id"])
        assert factura is not None
        assert factura._subtotal == Decimal("150.00")
        assert factura._total == Decimal("172.50")
        assert len(factura.detalles) == 2



def test_factura_update_and_delete(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="J031000000222")
        impuesto = create_impuesto(session, codigo="RET-1", tipo=TipoImpuesto.RETENCION, porcentaje=2.0)
        session.commit()

    created = modelo_workflow.factura.create(build_factura_payload(cliente.id, [impuesto.id]))

    updated = modelo_workflow.factura.update(
        created["id"],
        {
            "factura": {"numero_factura": "FAC-002"},
            "detalles_data": [
                {
                    "tipo": "Gasto",
                    "costo": 200.0,
                }
            ],
            "impuestos": [impuesto.id],
        },
    )

    assert updated is not None
    assert updated["numero_factura"] == "FAC-002"

    with session_factory() as session:
        factura = session.get(Factura, created["id"])
        assert factura is not None
        assert factura._subtotal == Decimal("200.00")
        assert factura._total == Decimal("196.00")
        assert len(factura.detalles) == 1

    deleted = modelo_workflow.factura.delete(created["id"])
    assert deleted is True

    with session_factory() as session:
        assert session.get(Factura, created["id"]) is None


def _set_factura_total(session_factory, factura_id: int, total: str) -> None:
    with session_factory() as session:
        factura = session.get(Factura, factura_id)
        assert factura is not None
        factura._subtotal = Decimal(total)
        factura._total = Decimal(total)
        session.commit()


def test_recibo_exchange_helpers_use_nio_per_usd_rate_in_both_directions():
    nio_receipt = Recibo(
        referencia="REC-CONV-NIO",
        cliente_id=1,
        monto=Decimal("36500.00"),
        moneda=Moneda.NIO,
        tasa_cambio=Decimal("36.5000"),
    )
    usd_receipt = Recibo(
        referencia="REC-CONV-USD",
        cliente_id=1,
        monto=Decimal("1000.00"),
        moneda=Moneda.USD,
        tasa_cambio=Decimal("36.5000"),
    )

    assert nio_receipt.convert_to_recibo_currency(Decimal("1000.00"), Moneda.USD) == Decimal("36500.00")
    assert nio_receipt.convert_from_recibo_currency(Decimal("36500.00"), Moneda.USD) == Decimal("1000.00")
    assert usd_receipt.convert_to_recibo_currency(Decimal("36500.00"), Moneda.NIO) == Decimal("1000.00")
    assert usd_receipt.convert_from_recibo_currency(Decimal("1000.00"), Moneda.NIO) == Decimal("36500.00")


def test_recibo_create_nio_receipt_pays_usd_invoice_by_converting_invoice_to_receipt_currency(
    modelo_workflow,
    session_factory,
):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="REC-CROSS-NIO-USD")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = "FAC-USD-CROSS"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura_payload["factura"]["tasa_cambio"] = Decimal("36.5000")
    factura = modelo_workflow.factura.create(factura_payload)
    _set_factura_total(session_factory, factura["id"], "1000.00")

    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": "REC-NIO-CROSS",
                "cliente_id": cliente.id,
                "monto": Decimal("36500.00"),
                "moneda": Moneda.NIO,
                "tasa_cambio": Decimal("36.5000"),
            },
            "facturas": [{"factura_id": factura["id"], "monto": Decimal("1000.00")}],
        }
    )

    assert recibo is not None
    with session_factory() as session:
        recibo_row = session.get(Recibo, recibo["id"])
        factura_row = session.get(Factura, factura["id"])
        relacion = session.get(ReciboFactura, (recibo["id"], factura["id"]))
        assert recibo_row is not None
        assert factura_row is not None
        assert relacion is not None
        assert recibo_row.tasa_cambio == Decimal("36.5000")
        assert relacion.monto_pagado == Decimal("1000.00")
        assert recibo_row.saldo_disponible == Decimal("0.00")
        assert factura_row.saldo_restante == Decimal("0.00")


def test_recibo_create_cross_currency_rejects_unconverted_amount(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="REC-CROSS-BAD")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = "FAC-USD-BAD"
    factura_payload["factura"]["moneda"] = Moneda.USD
    factura = modelo_workflow.factura.create(factura_payload)
    _set_factura_total(session_factory, factura["id"], "1000.00")

    with pytest.raises(ValueError, match="supera el saldo del recibo"):
        modelo_workflow.recibo.create(
            {
                "recibo": {
                    "referencia": "REC-NIO-BAD",
                    "cliente_id": cliente.id,
                    "monto": Decimal("1000.00"),
                    "moneda": Moneda.NIO,
                    "tasa_cambio": Decimal("36.5000"),
                },
                "facturas": [{"factura_id": factura["id"], "monto": Decimal("1000.00")}],
            }
        )


def test_recibo_create_usd_receipt_pays_nio_invoice_by_converting_invoice_to_receipt_currency(
    modelo_workflow,
    session_factory,
):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="REC-CROSS-USD-NIO")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = "FAC-NIO-CROSS"
    factura_payload["factura"]["moneda"] = Moneda.NIO
    factura = modelo_workflow.factura.create(factura_payload)
    _set_factura_total(session_factory, factura["id"], "36500.00")

    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": "REC-USD-CROSS",
                "cliente_id": cliente.id,
                "monto": Decimal("1000.00"),
                "moneda": Moneda.USD,
                "tasa_cambio": Decimal("36.5000"),
            },
            "facturas": [{"factura_id": factura["id"], "monto": Decimal("36500.00")}],
        }
    )

    assert recibo is not None
    with session_factory() as session:
        recibo_row = session.get(Recibo, recibo["id"])
        factura_row = session.get(Factura, factura["id"])
        assert recibo_row is not None
        assert factura_row is not None
        assert recibo_row.saldo_disponible == Decimal("0.00")
        assert factura_row.saldo_restante == Decimal("0.00")


def test_recibo_update_usd_receipt_pays_nio_invoice_by_dividing_invoice_amount(
    modelo_workflow,
    session_factory,
):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="REC-UPD-USD-NIO")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = "FAC-NIO-UPD-CROSS"
    factura_payload["factura"]["moneda"] = Moneda.NIO
    factura = modelo_workflow.factura.create(factura_payload)
    _set_factura_total(session_factory, factura["id"], "36500.00")

    recibo = modelo_workflow.recibo.create(
        {
            "recibo": {
                "referencia": "REC-USD-UPD-CROSS",
                "cliente_id": cliente.id,
                "monto": Decimal("1000.00"),
                "moneda": Moneda.USD,
                "tasa_cambio": Decimal("36.5000"),
            },
            "facturas": [{"factura_id": factura["id"], "monto": Decimal("36500.00")}],
        }
    )

    modelo_workflow.recibo.update(
        recibo["id"],
        {
            "recibo": {
                "monto": Decimal("500.00"),
                "moneda": Moneda.USD,
                "tasa_cambio": Decimal("36.5000"),
            },
            "facturas": [{"factura_id": factura["id"], "monto": Decimal("18250.00")}],
        },
    )

    with session_factory() as session:
        recibo_row = session.get(Recibo, recibo["id"])
        factura_row = session.get(Factura, factura["id"])
        relacion = session.get(ReciboFactura, (recibo["id"], factura["id"]))
        assert recibo_row is not None
        assert factura_row is not None
        assert relacion is not None
        assert relacion.monto_pagado == Decimal("18250.00")
        assert recibo_row.saldo_disponible == Decimal("0.00")
        assert factura_row.saldo_restante == Decimal("18250.00")


def test_recibo_create_rejects_invalid_exchange_rate(modelo_workflow, session_factory):
    with session_factory() as session:
        cliente = create_cliente(session, ruc="REC-RATE-BAD")
        session.commit()

    factura_payload = build_factura_payload(cliente.id, [])
    factura_payload["factura"]["numero_factura"] = "FAC-RATE-BAD"
    factura = modelo_workflow.factura.create(factura_payload)

    with pytest.raises(ValueError, match="tasa de cambio debe ser mayor que cero"):
        modelo_workflow.recibo.create(
            {
                "recibo": {
                    "referencia": "REC-RATE-BAD",
                    "cliente_id": cliente.id,
                    "monto": Decimal("150.00"),
                    "moneda": Moneda.NIO,
                    "tasa_cambio": Decimal("0.0000"),
                },
                "facturas": [{"factura_id": factura["id"], "monto": Decimal("150.00")}],
            }
        )
