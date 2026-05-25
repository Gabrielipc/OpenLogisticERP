from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TypedDict, cast

from openlogistic_erp.infrastructure.persistence.modelo.model_entities.base import (
    EstadoCamion,
    EstadoConductor,
    Moneda,
    TipoCarga,
    TipoDetalle,
    TipoImpuesto,
    TipoViaje,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.contabilidad.impuesto import (
    Impuesto,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.circuito import (
    Circuito,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.operacion.viaje import Viaje
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.camion import (
    Camion,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.cliente import (
    Cliente,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.conductor import (
    Conductor,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.furgon import (
    Furgon,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.ruta import Ruta
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.tarifa_flete import (
    TarifaFlete,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.thermo import (
    Thermo,
)
from openlogistic_erp.infrastructure.persistence.modelo.model_entities.planificacion.ubicacion import (
    Ubicacion,
)


class ViajeExportPayload(TypedDict):
    viaje: dict[str, object]
    circuito: dict[str, datetime]
    detalle_operacion: dict[str, object]


def _orm_int(value: object) -> int:
    return cast(int, value)


def create_cliente(session, **overrides) -> Cliente:
    payload = {
        "nombre": "Cliente Demo",
        "ruc": f"J{datetime.now().strftime('%H%M%S%f')}",
        "direccion": "Managua",
        "facturable": True,
    }
    payload.update(overrides)
    cliente = Cliente(**payload)
    session.add(cliente)
    session.flush()
    return cliente


def create_ubicacion(session, **overrides) -> Ubicacion:
    payload = {
        "codigo": f"UB-{datetime.now().strftime('%H%M%S%f')}",
        "descripcion": "Ubicacion Demo",
    }
    payload.update(overrides)
    ubicacion = Ubicacion(**payload)
    session.add(ubicacion)
    session.flush()
    return ubicacion


def create_ruta(session, **overrides) -> Ruta:
    origen = overrides.pop("origen", None) or create_ubicacion(session, descripcion="Origen Demo")
    destino = overrides.pop("destino", None) or create_ubicacion(session, descripcion="Destino Demo")
    payload = {
        "origen_id": _orm_int(origen.id),
        "destino_id": _orm_int(destino.id),
    }
    payload.update(overrides)
    ruta = Ruta(**payload)
    session.add(ruta)
    session.flush()
    return ruta


def create_camion(session, **overrides) -> Camion:
    payload = {
        "placa": f"M-{datetime.now().strftime('%H%M%S')}",
        "numero_caat": "CAAT-1",
        "codigo_aduanero": "ADU-1",
        "marca": "Freightliner",
        "modelo": "Cascadia",
        "color": "Blanco",
        "motor": "Detroit",
        "chasis": f"CH-{datetime.now().strftime('%f')}",
        "anio": 2020,
        "estado": EstadoCamion.ACTIVO,
    }
    payload.update(overrides)
    camion = Camion(**payload)
    session.add(camion)
    session.flush()
    return camion


def create_furgon(session, **overrides) -> Furgon:
    payload = {
        "placa": f"F-{datetime.now().strftime('%H%M%S')}",
        "numero_economico": "FG-1",
        "codigo_aduanero": "FGA-1",
        "marca": "Utility",
        "modelo": "3000R",
        "color": "Gris",
        "chasis": f"FG-CH-{datetime.now().strftime('%f')}",
        "anio": 2021,
        "tamanio": "53",
        "tipo_carga": TipoCarga.SECA,
        "estado": EstadoCamion.ACTIVO,
    }
    payload.update(overrides)
    furgon = Furgon(**payload)
    session.add(furgon)
    session.flush()
    return furgon


def create_thermo(session, **overrides) -> Thermo:
    payload = {
        "codigo": f"TH-{datetime.now().strftime('%H%M%S')}",
        "marca": "Carrier",
        "modelo": "X4",
        "estado": EstadoCamion.ACTIVO,
    }
    payload.update(overrides)
    thermo = Thermo(**payload)
    session.add(thermo)
    session.flush()
    return thermo


def create_conductor(session, **overrides) -> Conductor:
    payload = {
        "nombre": "Juan",
        "apellido": "Perez",
        "cedula": "001-000000-0000A",
        "licencia": "LIC-1",
        "pasaporte": "P-1",
        "telefono": "88880000",
        "estado": EstadoConductor.DISPONIBLE,
    }
    payload.update(overrides)
    conductor = Conductor(**payload)
    session.add(conductor)
    session.flush()
    return conductor


def create_impuesto(session, **overrides) -> Impuesto:
    payload = {
        "codigo": f"IVA-{datetime.now().strftime('%H%M%S%f')}",
        "tipo": TipoImpuesto.IVA,
        "porcentaje": Decimal("15.00"),
    }
    payload.update(overrides)
    impuesto = Impuesto(**payload)
    session.add(impuesto)
    session.flush()
    return impuesto


def seed_viaje_dependencies(session) -> dict[str, int]:
    cliente = create_cliente(session)
    ruta = create_ruta(session)
    tarifa = TarifaFlete(
        cliente_id=_orm_int(cliente.id),
        ruta_id=_orm_int(ruta.id),
        costo=Decimal("100.00"),
        moneda=Moneda.USD,
    )
    session.add(tarifa)
    session.flush()
    camion = create_camion(session)
    furgon = create_furgon(session)
    thermo = create_thermo(session)
    conductor = create_conductor(session)
    session.commit()
    return {
        "cliente_id": _orm_int(cliente.id),
        "ruta_id": _orm_int(ruta.id),
        "origen_id": _orm_int(ruta.origen_id),
        "destino_id": _orm_int(ruta.destino_id),
        "camion_id": _orm_int(camion.id),
        "furgon_id": _orm_int(furgon.id),
        "thermo_id": _orm_int(thermo.id),
        "conductor_id": _orm_int(conductor.id),
    }


def build_viaje_export_payload(deps: dict[str, int], **overrides) -> ViajeExportPayload:
    viaje = {
        "cliente_id": deps["cliente_id"],
        "conductor_id": deps["conductor_id"],
        "furgon_id": deps["furgon_id"],
        "camion_id": deps["camion_id"],
        "thermo_id": deps["thermo_id"],
        "tipo_viaje": TipoViaje.EXPOR,
        "_ruta_id": deps["ruta_id"],
        "fecha_posicionamiento": datetime(2026, 1, 15, 8, 0, 0),
        "descripcion": "Viaje de exportacion de prueba",
    }
    viaje_overrides = overrides.pop("viaje", {})
    if isinstance(viaje_overrides, dict):
        viaje.update(viaje_overrides)

    circuito_payload = {"fecha_inicio": datetime(2026, 1, 15, 7, 0, 0)}
    circuito_overrides = overrides.pop("circuito", {})
    if isinstance(circuito_overrides, dict):
        circuito_payload.update(circuito_overrides)

    detalle_operacion = overrides.pop("detalle_operacion", {})
    if not isinstance(detalle_operacion, dict):
        detalle_operacion = {}

    payload: ViajeExportPayload = {
        "viaje": viaje,
        "circuito": circuito_payload,
        "detalle_operacion": detalle_operacion,
    }
    return payload


def build_factura_payload(cliente_id: object, impuesto_ids: list[object] | None = None) -> dict[str, object]:
    normalized_cliente_id = _orm_int(cliente_id)
    normalized_impuesto_ids = [_orm_int(impuesto_id) for impuesto_id in (impuesto_ids or [])]
    return {
        "factura": {
            "numero_factura": "FAC-001",
            "fecha_emision": datetime(2026, 1, 20, 10, 0, 0),
            "cliente_id": normalized_cliente_id,
            "dias_credito": 30,
            "moneda": Moneda.NIO,
            "tasa_cambio": Decimal("1.0000"),
        },
        "detalles_data": [
            {
                "tipo": TipoDetalle.GASTO,
                "costo": Decimal("100.00"),
            },
            {
                "tipo": TipoDetalle.GASTO,
                "costo": Decimal("50.00"),
            },
        ],
        "impuestos": normalized_impuesto_ids,
    }


def get_camion(session_factory, camion_id: int) -> Camion | None:
    with session_factory() as session:
        return session.get(Camion, camion_id)


def get_conductor(session_factory, conductor_id: int) -> Conductor | None:
    with session_factory() as session:
        return session.get(Conductor, conductor_id)


def get_thermo(session_factory, thermo_id: int) -> Thermo | None:
    with session_factory() as session:
        return session.get(Thermo, thermo_id)


def get_viaje(session_factory, viaje_id: int) -> Viaje | None:
    with session_factory() as session:
        return session.get(Viaje, viaje_id)


def get_circuito(session_factory, circuito_id: int) -> Circuito | None:
    with session_factory() as session:
        return session.get(Circuito, circuito_id)
