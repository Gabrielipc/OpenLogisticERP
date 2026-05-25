from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import EstadoCamion, EstadoConductor, Moneda
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.tarifa_flete import TarifaFlete
from openlogistic_erp.infrastructure.persistence.session_identity import authenticated_user
from tests.builders.modelo_seed import (
    create_camion,
    create_cliente,
    create_conductor,
    create_furgon,
    create_ruta,
    create_thermo,
    create_ubicacion,
)
from tests.builders.security_seed import create_permission, create_role


def _build_lookup_user(auth_service, session_factory) -> object:
    with session_factory() as session:
        viaje_permission = create_permission(session, "viaje", "leer")
        role = create_role(session, name=uuid4().hex[:10], permissions=[viaje_permission])
        session.commit()
    return auth_service.create_user(
        username=f"lookup_{uuid4().hex[:8]}",
        password="secret123",
        roles=[role.name],
    )


def test_reference_lookup_service_filters_viaje_resources_by_status_and_include_agregados(
    session_factory,
    reference_lookup_service,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:6].upper()
    with session_factory() as session:
        conductor_disponible = create_conductor(
            session,
            nombre=f"Alpha{token}",
            apellido="Driver",
            estado=EstadoConductor.DISPONIBLE,
        )
        conductor_instrucciones = create_conductor(
            session,
            nombre=f"Beta{token}",
            apellido="Driver",
            estado=EstadoConductor.INSTRUCCIONES,
        )
        create_conductor(
            session,
            nombre=f"Delta{token}",
            apellido="Driver",
            estado=EstadoConductor.VIAJE,
        )
        conductor_agregado = create_conductor(
            session,
            nombre=f"Gamma{token}",
            apellido="Driver",
            estado=EstadoConductor.AGREGADO,
        )
        camion_activo = create_camion(session, placa=f"ACT-{token}", estado=EstadoCamion.ACTIVO)
        create_camion(session, placa=f"VJE-{token}", estado=EstadoCamion.ENVIAJE)
        camion_agregado = create_camion(session, placa=f"AGR-{token}", estado=EstadoCamion.AGREGADO)
        furgon_activo = create_furgon(session, placa=f"FAT-{token}", estado=EstadoCamion.ACTIVO)
        create_furgon(session, placa=f"FEN-{token}", estado=EstadoCamion.ENVIAJE)
        furgon_agregado = create_furgon(session, placa=f"FAG-{token}", estado=EstadoCamion.AGREGADO)
        thermo_activo = create_thermo(session, codigo=f"TAT-{token}", estado=EstadoCamion.ACTIVO)
        create_thermo(session, codigo=f"TEN-{token}", estado=EstadoCamion.ENVIAJE)
        thermo_agregado = create_thermo(session, codigo=f"TAG-{token}", estado=EstadoCamion.AGREGADO)
        session.commit()

    user = _build_lookup_user(auth_service, session_factory)

    with authenticated_user(user.id):
        conductor_export_options = reference_lookup_service.search(
            "viaje.conductor_id",
            token,
            context={"trip_type": "Exportacion"},
        )
        conductor_export_options_with_agregados = reference_lookup_service.search(
            "viaje.conductor_id",
            token,
            context={"trip_type": "Exportacion", "include_agregados": True},
        )
        conductor_import_options = reference_lookup_service.search(
            "viaje.conductor_id",
            token,
            context={"trip_type": "Importacion"},
        )
        conductor_import_options_with_agregados = reference_lookup_service.search(
            "viaje.conductor_id",
            token,
            context={"trip_type": "Importacion", "include_agregados": True},
        )
        camion_options = reference_lookup_service.search("viaje.camion_id", token)
        camion_options_with_agregados = reference_lookup_service.search(
            "viaje.camion_id",
            token,
            context={"include_agregados": True},
        )
        furgon_options = reference_lookup_service.search("viaje.furgon_id", token)
        furgon_options_with_agregados = reference_lookup_service.search(
            "viaje.furgon_id",
            token,
            context={"include_agregados": True},
        )
        thermo_options = reference_lookup_service.search("viaje.thermo_id", token)
        thermo_options_with_agregados = reference_lookup_service.search(
            "viaje.thermo_id",
            token,
            context={"include_agregados": True},
        )

    assert [option.value for option in conductor_export_options] == [conductor_disponible.id]
    assert [option.value for option in conductor_export_options_with_agregados] == [
        conductor_disponible.id,
        conductor_agregado.id,
    ]
    assert [option.value for option in conductor_import_options] == [conductor_instrucciones.id]
    assert [option.value for option in conductor_import_options_with_agregados] == [
        conductor_instrucciones.id,
        conductor_agregado.id,
    ]
    assert conductor_import_options_with_agregados[-1].label.endswith("(AGREGADO)")

    assert [option.value for option in camion_options] == [camion_activo.id]
    assert sorted(option.value for option in camion_options_with_agregados) == sorted([
        camion_activo.id,
        camion_agregado.id,
    ])

    assert [option.value for option in furgon_options] == [furgon_activo.id]
    assert sorted(option.value for option in furgon_options_with_agregados) == sorted([
        furgon_activo.id,
        furgon_agregado.id,
    ])

    assert [option.value for option in thermo_options] == [thermo_activo.id]
    assert sorted(option.value for option in thermo_options_with_agregados) == sorted([
        thermo_activo.id,
        thermo_agregado.id,
    ])


def test_reference_lookup_service_filters_viaje_clientes_y_ubicaciones_por_contexto(
    session_factory,
    reference_lookup_service,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:6].upper()
    destinos_ancla = [
        "Nicaragua",
        "Matadero GINSA",
        "San Martin",
        "MACESA",
    ]

    with session_factory() as session:
        puerto_exportacion = create_ubicacion(session, descripcion=f"Puerto Export {token}")
        patio_importacion = create_ubicacion(session, descripcion=f"Patio Import {token}")
        frontera_extra = create_ubicacion(session, descripcion=f"Frontera {token}")
        destino_importacion = create_ubicacion(session, descripcion=destinos_ancla[0])
        origen_exportacion = create_ubicacion(session, descripcion=destinos_ancla[1])

        cliente_importacion = create_cliente(session, nombre=f"Cliente Import {token}")
        cliente_exportacion = create_cliente(session, nombre=f"Cliente Export {token}")

        ruta_importacion = create_ruta(
            session,
            origen=patio_importacion,
            destino=destino_importacion,
        )
        ruta_exportacion = create_ruta(
            session,
            origen=origen_exportacion,
            destino=puerto_exportacion,
        )
        ruta_exportacion_extra = create_ruta(
            session,
            origen=origen_exportacion,
            destino=frontera_extra,
        )

        session.add_all(
            [
                TarifaFlete(
                    cliente_id=cliente_importacion.id,
                    ruta_id=ruta_importacion.id,
                    costo=Decimal("100.00"),
                    moneda=Moneda.USD,
                ),
                TarifaFlete(
                    cliente_id=cliente_exportacion.id,
                    ruta_id=ruta_exportacion.id,
                    costo=Decimal("120.00"),
                    moneda=Moneda.USD,
                ),
                TarifaFlete(
                    cliente_id=cliente_exportacion.id,
                    ruta_id=ruta_exportacion_extra.id,
                    costo=Decimal("130.00"),
                    moneda=Moneda.USD,
                ),
            ]
        )
        session.commit()

    user = _build_lookup_user(auth_service, session_factory)

    with authenticated_user(user.id):
        clientes_exportacion = reference_lookup_service.search(
            "viaje.cliente_id",
            token,
            context={"trip_type": "Exportacion"},
        )
        clientes_importacion = reference_lookup_service.search(
            "viaje.cliente_id",
            token,
            context={"trip_type": "Importacion"},
        )
        origenes_exportacion = reference_lookup_service.search(
            "viaje.origen_id",
            "",
            context={"cliente_id": cliente_exportacion.id},
        )
        destinos_exportacion = reference_lookup_service.search(
            "viaje.destino_id",
            "",
            context={"cliente_id": cliente_exportacion.id},
        )

    assert [option.value for option in clientes_exportacion] == [cliente_exportacion.id]
    assert [option.value for option in clientes_importacion] == [cliente_importacion.id]
    assert sorted(option.label for option in origenes_exportacion) == [origen_exportacion.descripcion]
    assert sorted(option.label for option in destinos_exportacion) == sorted(
        [puerto_exportacion.descripcion, frontera_extra.descripcion]
    )


def test_reference_lookup_service_cross_filters_viaje_origenes_y_destinos_por_ruta_tarifada(
    session_factory,
    reference_lookup_service,
    auth_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    token = uuid4().hex[:6].upper()

    with session_factory() as session:
        cliente = create_cliente(session, nombre=f"Cliente Cross {token}")
        origen_a = create_ubicacion(session, descripcion=f"Origen A {token}")
        origen_b = create_ubicacion(session, descripcion=f"Origen B {token}")
        destino_a = create_ubicacion(session, descripcion=f"Destino A {token}")
        destino_b = create_ubicacion(session, descripcion=f"Destino B {token}")

        ruta_a = create_ruta(session, origen=origen_a, destino=destino_a)
        ruta_b = create_ruta(session, origen=origen_b, destino=destino_b)

        session.add_all(
            [
                TarifaFlete(cliente_id=cliente.id, ruta_id=ruta_a.id, costo=Decimal("100.00"), moneda=Moneda.USD),
                TarifaFlete(cliente_id=cliente.id, ruta_id=ruta_b.id, costo=Decimal("150.00"), moneda=Moneda.USD),
            ]
        )
        session.commit()

    user = _build_lookup_user(auth_service, session_factory)

    with authenticated_user(user.id):
        destinos_desde_origen_a = reference_lookup_service.search(
            "viaje.destino_id",
            "",
            context={"cliente_id": cliente.id, "origen_id": origen_a.id},
        )
        origenes_desde_destino_b = reference_lookup_service.search(
            "viaje.origen_id",
            "",
            context={"cliente_id": cliente.id, "destino_id": destino_b.id},
        )

    assert [option.label for option in destinos_desde_origen_a] == [destino_a.descripcion]
    assert [option.label for option in origenes_desde_destino_b] == [origen_b.descripcion]
