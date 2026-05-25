"""Use case for creating viaje with domain rules and one transaction."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    Camion,
    Circuito,
    Cliente,
    Conductor,
    Descarga,
    EstadoCamion,
    EstadoConductor,
    EstadoFacturacion,
    Furgon,
    Thermo,
    TipoViaje,
    Viaje,
    Ruta,
)
from ...factories.circuito_factory import CircuitoFactory
from ...factories.detalle_operacion_factory import DetalleOperacionFactory
from ...factories.viaje_factory import ViajeFactory


class CreateViajeUseCase:
    def __init__(
        self,
        *,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        viaje_factory: ViajeFactory,
        circuito_factory: CircuitoFactory,
        detalle_operacion_factory: DetalleOperacionFactory,
    ):
        self._repository = repository
        self._uow = unit_of_work
        self._viaje_factory = viaje_factory
        self._circuito_factory = circuito_factory
        self._detalle_factory = detalle_operacion_factory

    def execute(self, payload: dict[str, Any]):
        data = dict(payload)
        viaje_payload = dict(data.get("viaje", {}))
        detalle_payload = dict(data.get("detalle_operacion", {}) or {})
        circuito_payload = dict(data.get("circuito", {}) or {})

        def _action(session):
            tipo_viaje = TipoViaje(viaje_payload.get("tipo_viaje"))
            self._validate_cliente_constraints(tipo_viaje, viaje_payload)
            self._hydrate_estado_facturacion(session, viaje_payload)

            if tipo_viaje == TipoViaje.EXPOR:
                viaje = self._create_expor(session, viaje_payload, circuito_payload)
            elif tipo_viaje == TipoViaje.IMPOR:
                viaje = self._create_impor(session, viaje_payload)
            elif tipo_viaje == TipoViaje.VACIO:
                viaje = self._create_vacio(session, viaje_payload)
            else:
                raise ValueError(f"Tipo de viaje no soportado: {tipo_viaje}")

            self._inject_descarga_posicionamiento(detalle_payload, viaje)
            detalle = self._detalle_factory.create(viaje=viaje, data=detalle_payload)
            session.add(detalle)

            session.add(viaje)
            session.flush()
            if tipo_viaje == TipoViaje.VACIO:
                viaje.referencia = f"Viaje vacío #{viaje.id}"
            self._set_equipo_ocupado(session, viaje)
            return viaje

        return self._uow.run_in_transaction(_action)

    def _hydrate_estado_facturacion(self, session, viaje_data: dict[str, Any]) -> None:
        cliente_id = viaje_data.get("cliente_id")
        if cliente_id is None:
            viaje_data["_estado_facturacion"] = EstadoFacturacion.SIN_FACTURA
            return

        cliente = session.get(Cliente, int(cliente_id))
        if cliente is not None and not cast(bool, cliente.facturable):
            viaje_data["_estado_facturacion"] = EstadoFacturacion.SIN_FACTURA
        else:
            viaje_data.setdefault("_estado_facturacion", EstadoFacturacion.REGISTRADO)

    @staticmethod
    def _validate_cliente_constraints(tipo_viaje: TipoViaje, viaje_payload: dict[str, Any]) -> None:
        cliente_id = viaje_payload.get("cliente_id")
        if tipo_viaje in {TipoViaje.EXPOR, TipoViaje.IMPOR} and cliente_id is None:
            raise ValueError("cliente_id es obligatorio para viajes de exportacion e importacion")
        if tipo_viaje == TipoViaje.VACIO and cliente_id is not None:
            raise ValueError("Un viaje vacio no debe tener cliente")

    def _create_expor(self, session, viaje_payload: dict[str, Any], circuito_payload: dict[str, Any]) -> Viaje:
        circuito = self._circuito_factory.create(circuito_payload)
        session.add(circuito)
        session.flush()

        if "fecha_posicionamiento" not in viaje_payload:
            viaje_payload["fecha_posicionamiento"] = datetime.now()

        viaje = self._viaje_factory.create_expor(viaje_payload, circuito_id=cast(int, circuito.id))
        return viaje

    def _create_impor(self, session, viaje_payload: dict[str, Any]) -> Viaje:
        self._resolve_circuito_from_viaje_ida(session, viaje_payload)
        circuito_id = viaje_payload.get("_circuito_id")
        if not isinstance(circuito_id, int) or circuito_id <= 0:
            raise ValueError("Se requiere '_circuito_id' para viajes de importación")

        circuito = session.get(Circuito, circuito_id)
        if circuito is None:
            raise ValueError("Circuito de importación no encontrado")

        viaje_ida = self._resolve_viaje_ida(circuito)
        self._validate_no_return_trip(circuito, viaje_ida)
        self._validate_impor_constraints(session, viaje_payload, viaje_ida)

        return self._viaje_factory.create_impor(viaje_payload, circuito_id=cast(int, circuito.id))

    def _create_vacio(self, session, viaje_payload: dict[str, Any]) -> Viaje:
        self._resolve_circuito_from_viaje_ida(session, viaje_payload)
        circuito_id = viaje_payload.get("_circuito_id")
        if not isinstance(circuito_id, int) or circuito_id <= 0:
            raise ValueError("Se requiere '_circuito_id' para viajes vacíos")

        circuito = session.get(Circuito, circuito_id)
        if circuito is None:
            raise ValueError("Circuito no encontrado para viaje vacío")

        viaje_ida = self._resolve_viaje_ida(circuito)
        self._validate_no_return_trip(circuito, viaje_ida)
        ruta_retorno_id = self._resolve_reverse_route_id(session, viaje_ida)
        viaje_vacio = self._viaje_factory.create_vacio(
            viaje_ida,
            circuito_id=cast(int, circuito.id),
            _ruta_id=ruta_retorno_id,
        )
        referencia_ida = str(viaje_ida.referencia or f"Viaje #{viaje_ida.id}")
        viaje_vacio.descripcion = f"Viaje de vuelta vacío para el viaje de exportación {referencia_ida}"
        return viaje_vacio

    def _resolve_circuito_from_viaje_ida(self, session, viaje_payload: dict[str, Any]) -> None:
        viaje_ida_id = viaje_payload.pop("viaje_ida_id", None)
        if viaje_ida_id in (None, ""):
            return
        viaje_ida = session.get(Viaje, int(viaje_ida_id))
        if viaje_ida is None or viaje_ida.tipo_viaje != TipoViaje.EXPOR:
            raise ValueError("El viaje de ida seleccionado no existe o no es una exportacion")
        circuito_id = cast(int | None, viaje_ida._circuito_id)
        if circuito_id is None or int(circuito_id) <= 0:
            raise ValueError("El viaje de ida seleccionado no tiene circuito asociado")
        viaje_payload["_circuito_id"] = int(circuito_id)

    def _resolve_viaje_ida(self, circuito: Circuito) -> Viaje:
        viajes = [viaje for viaje in (circuito.viajes or []) if viaje is not None]
        if not viajes:
            raise ValueError("El circuito no tiene viaje de ida asociado")

        for candidate in viajes:
            if candidate.tipo_viaje == TipoViaje.EXPOR:
                return candidate

        for candidate in viajes:
            if candidate.tipo_viaje != TipoViaje.VACIO:
                return candidate

        return viajes[0]

    def _validate_no_return_trip(self, circuito: Circuito, viaje_ida: Viaje) -> None:
        for viaje in circuito.viajes or []:
            if viaje is None or int(viaje.id or 0) == int(viaje_ida.id or 0):
                continue
            if viaje.tipo_viaje in {TipoViaje.IMPOR, TipoViaje.VACIO}:
                raise ValueError("El viaje de ida seleccionado ya tiene viaje de vuelta asociado")

    @staticmethod
    def _resolve_reverse_route_id(session, viaje_ida: Viaje) -> int:
        ruta_ida = getattr(viaje_ida, "_ruta", None)
        if ruta_ida is None:
            ruta_id = getattr(viaje_ida, "_ruta_id", None)
            ruta_ida = session.get(Ruta, int(ruta_id)) if ruta_id is not None else None
        if ruta_ida is None:
            raise ValueError("El viaje de ida no tiene ruta asociada")

        rows = session.execute(
            select(Ruta.id)
            .where(Ruta.origen_id == int(ruta_ida.destino_id))
            .where(Ruta.destino_id == int(ruta_ida.origen_id))
            .order_by(Ruta.id.asc())
        ).scalars().all()
        if not rows:
            raise ValueError("No existe una ruta de retorno valida para crear el viaje vacio")
        if len(rows) > 1:
            raise ValueError("La ruta de retorno para el viaje vacio es ambigua")
        return int(rows[0])

    def _validate_impor_constraints(self, session, viaje_payload: dict[str, Any], viaje_ida: Viaje) -> None:
        fecha_posicionamiento = viaje_payload.get("fecha_posicionamiento")
        if fecha_posicionamiento is None:
            raise ValueError("fecha_posicionamiento es obligatoria para importación")

        detalle = viaje_ida.detalle_operacion
        descarga: Descarga | None = detalle.descarga if detalle is not None else None
        if descarga is None or descarga.fecha_descarga is None:
            raise ValueError("El viaje de ida no tiene fecha de descarga")

        if fecha_posicionamiento < descarga.fecha_descarga:
            raise ValueError("La fecha de posicionamiento del viaje importación debe ser posterior a la descarga")

        for field in ("camion_id", "furgon_id", "thermo_id"):
            expected = getattr(viaje_ida, field)
            current = viaje_payload.get(field)
            if current is not None and expected is not None and int(current) != int(expected):
                raise ValueError(f"{field} debe coincidir con el viaje de ida del circuito")

    @staticmethod
    def _inject_descarga_posicionamiento(detalle_payload: dict[str, Any], viaje: Viaje) -> None:
        descarga_payload = detalle_payload.get("descarga")
        if not isinstance(descarga_payload, dict):
            descarga_payload = {}
            detalle_payload["descarga"] = descarga_payload
        descarga_payload.setdefault("fecha_posicionamiento", viaje.fecha_posicionamiento)

    def _set_equipo_ocupado(self, session, viaje: Viaje) -> None:
        conductor = session.get(Conductor, viaje.conductor_id)
        if conductor is not None and cast(EstadoConductor, conductor.estado) != EstadoConductor.AGREGADO:
            conductor.estado = EstadoConductor.VIAJE

        for model, equip_id in ((Camion, viaje.camion_id), (Furgon, viaje.furgon_id), (Thermo, viaje.thermo_id)):
            entity = session.get(model, equip_id)
            if entity is not None and cast(EstadoCamion, entity.estado) != EstadoCamion.AGREGADO:
                entity.estado = EstadoCamion.ENVIAJE
