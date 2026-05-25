"""Domain service for Viaje use cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from sqlalchemy import String, func, or_, select
from sqlalchemy import cast as sql_cast
from sqlalchemy.orm import joinedload

from ...domain.modelo.catalog_queries import CatalogSort, CatalogSortDirection
from ...domain.modelo.dtos import CatalogPageDTO, CatalogRecordDTO, CatalogSchemaDTO, FieldKind
from ...domain.modelo.field_validation import format_field_value_for_ui, normalize_field_value
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from ...infrastructure.persistence.modelo.workflow_orm import (
    ActividadThermo,
    Camion,
    Cliente,
    Conductor,
    Descarga,
    DetalleOperacion,
    EstadoCamion,
    EstadoDetalle,
    EstadoFacturacion,
    EstadoViaje,
    Furgon,
    GastoRealCamion,
    GastoRealThermo,
    Moneda,
    OrdenCombustible,
    Ruta,
    TarifaFlete,
    Thermo,
    TipoOrdenCombustible,
    TipoViaje,
    Ubicacion,
    Viaje,
)
from ..common.uow import SQLAlchemyUnitOfWork
from ..modelo.use_cases import (
    CreateViajeUseCase,
    DeleteViajeUseCase,
    GetModelUseCase,
    ListModelUseCase,
    TerminarViajeUseCase,
    UpdateViajeUseCase,
)
from .consumo_analysis_service import ConsumoAnalysisService
from .contracts import InvalidIdentifierError, InvalidPayloadError
from .workflow_dtos import CreateViajeCommand, UpdateViajeCommand


class ViajeWorkflowService:
    """Orchestrates viaje use cases and read models for UI workflows."""

    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        list_viaje_use_case: ListModelUseCase,
        get_viaje_use_case: GetModelUseCase,
        create_viaje_use_case: CreateViajeUseCase,
        update_viaje_use_case: UpdateViajeUseCase,
        delete_viaje_use_case: DeleteViajeUseCase,
        terminar_viaje_use_case: TerminarViajeUseCase,
    ):
        self.repository = repository
        self.unit_of_work = unit_of_work
        self.list_viaje_use_case = list_viaje_use_case
        self.get_viaje_use_case = get_viaje_use_case
        self.create_viaje_use_case = create_viaje_use_case
        self.update_viaje_use_case = update_viaje_use_case
        self.delete_viaje_use_case = delete_viaje_use_case
        self.terminar_viaje_use_case = terminar_viaje_use_case
        self._consumo_analysis_service = ConsumoAnalysisService()

    @staticmethod
    def _as_payload(payload: Mapping[str, object], *, message: str) -> dict[str, object]:
        if payload is None or not isinstance(payload, Mapping):
            raise InvalidPayloadError(message)
        return dict(payload)

    @staticmethod
    def _as_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("Se requiere identificador valido de viaje")
        return record_id

    def list(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        return self.list_viaje_use_case.execute(filters)

    def get(self, record_id: int) -> CatalogRecordDTO | None:
        return self.get_viaje_use_case.execute(self._as_record_id(record_id))

    def create(self, payload: Mapping[str, object] | CreateViajeCommand) -> CatalogRecordDTO | None:
        if isinstance(payload, CreateViajeCommand):
            data = payload.to_payload()
        else:
            data = self._as_payload(payload, message="Se requiere payload para crear viaje")
        viaje = self.create_viaje_use_case.execute(data)
        return self.repository.get_record("viaje", cast(int, viaje.id))

    def update(
        self,
        record_id_or_payload: int | Mapping[str, object] | UpdateViajeCommand,
        payload: Mapping[str, object] | None = None,
    ) -> CatalogRecordDTO | None:
        if isinstance(record_id_or_payload, UpdateViajeCommand):
            data = record_id_or_payload.to_payload()
        else:
            data = self._normalize_update_payload(record_id_or_payload, payload)
        viaje = self.update_viaje_use_case.execute(data)
        return self.repository.get_record("viaje", cast(int, viaje.id))

    def delete(self, payload: Mapping[str, object] | int) -> bool:
        if payload is None:
            raise InvalidIdentifierError("Se requiere identificador para eliminar viaje")
        return self.delete_viaje_use_case.execute(payload)

    def get_form_schema(self) -> CatalogSchemaDTO:
        return self.repository.get_schema("viaje")

    def get_form_state(self, record_id: int) -> dict[str, Any]:
        normalized_record_id = self._as_record_id(record_id)
        record = self.get(normalized_record_id)
        if record is None:
            raise ValueError(f"No se encontro viaje con id={record_id}")
        field_index = {field.name: field for field in self.get_form_schema().form_fields}
        values = self._default_form_values()
        values.update(self._values_from_record(record, field_index))
        nested_state = self.unit_of_work.run_in_transaction(
            lambda session: self._load_nested_state(session, normalized_record_id)
        )
        values.update(nested_state["value_updates"])
        return {
            "values": values,
            "fuel_orders": nested_state["fuel_orders"],
            "detalle_operacion_id": nested_state["detalle_operacion_id"],
            "circuito_id": nested_state["circuito_id"],
        }

    def validate_import_constraints(
        self,
        circuito_id: int,
        current_values: Mapping[str, Any],
        *,
        exclude_viaje_id: int | None = None,
    ) -> dict[str, str]:
        normalized_circuito_id = self._as_record_id(int(circuito_id))
        payload = dict(current_values)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._validate_import_constraints(
                session,
                normalized_circuito_id,
                payload,
                exclude_viaje_id=exclude_viaje_id,
            )
        )

    def resolve_route(
        self,
        cliente_id: int,
        origen_id: int,
        destino_id: int,
    ) -> int:
        normalized_cliente_id = self._as_record_id(int(cliente_id))
        normalized_origen_id = self._as_record_id(int(origen_id))
        normalized_destino_id = self._as_record_id(int(destino_id))
        return self.unit_of_work.run_in_transaction(
            lambda session: self._resolve_route(
                session,
                normalized_cliente_id,
                normalized_origen_id,
                normalized_destino_id,
            )
        )

    def resolve_conductor_equipment_defaults(self, conductor_id: int) -> dict[str, int | None]:
        normalized_conductor_id = self._as_record_id(int(conductor_id))
        return self.unit_of_work.run_in_transaction(
            lambda session: self._resolve_conductor_equipment_defaults(
                session,
                normalized_conductor_id,
            )
        )

    def resolve_viaje_ida_circuito(self, viaje_ida_id: int) -> int | None:
        normalized_viaje_id = self._as_record_id(int(viaje_ida_id))
        return self.unit_of_work.run_in_transaction(
            lambda session: self._resolve_viaje_ida_circuito(session, normalized_viaje_id)
        )

    def resolve_circuito_viaje_ida(self, circuito_id: int) -> int | None:
        normalized_circuito_id = self._as_record_id(int(circuito_id))
        return self.unit_of_work.run_in_transaction(
            lambda session: self._resolve_circuito_viaje_ida(session, normalized_circuito_id)
        )

    def resolve_empty_return_route(self, viaje_ida_id: int) -> dict[str, int]:
        normalized_viaje_id = self._as_record_id(int(viaje_ida_id))
        return self.unit_of_work.run_in_transaction(
            lambda session: self._resolve_empty_return_route(session, normalized_viaje_id)
        )

    def list_screen_page(
        self,
        *,
        page: int = 0,
        page_size: int = 20,
        sort: CatalogSort | None = None,
        search_text: str | None = None,
    ) -> CatalogPageDTO:
        normalized_page = max(0, int(page))
        normalized_page_size = max(1, int(page_size))
        normalized_search = str(search_text or "").strip()
        resolved_sort = sort or CatalogSort(field="fecha_posicionamiento", direction=CatalogSortDirection.DESC)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._list_screen_page(
                session,
                page=normalized_page,
                page_size=normalized_page_size,
                sort=resolved_sort,
                search_text=normalized_search,
            )
        )

    def get_detail_summary(self, record_id: int) -> dict[str, Any]:
        normalized_record_id = self._as_record_id(record_id)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._load_detail_summary(session, normalized_record_id)
        )

    def list_unbilled_trips(self) -> list[dict[str, Any]]:
        return self.unit_of_work.run_in_transaction(self._list_unbilled_trips_grouped_by_client)
    
    def crear_viaje(self, payload: Mapping[str, object]):
        return self.create(payload)

    def crear_viaje_completo(self, payload: Mapping[str, object]):
        return self.create(payload)

    def actualizar_viaje(self, payload: Mapping[str, object]):
        return self.update(payload)

    def eliminar_viaje(self, payload: Mapping[str, object] | int):
        return self.delete(payload)

    def terminar_viaje(self, viaje, detalle_operacion=None):
        if detalle_operacion is None:
            return self.terminar_viaje_use_case.execute(viaje)
        return self.terminar_viaje_use_case.execute({"viaje": viaje, "detalle_operacion": detalle_operacion})

    def reabrir_viaje(self, viaje):
        normalized_record_id = self._as_record_id(int(viaje))

        def _action(session):
            record = session.get(Viaje, normalized_record_id)
            if record is None:
                raise ValueError(f"No se encontro viaje con id={normalized_record_id}")
            detalle = getattr(record, "detalle_operacion", None)
            if detalle is None:
                raise ValueError("El viaje no tiene detalle de operacion asociado")
            detalle.estado = EstadoDetalle.ABIERTO
            record.estado = EstadoViaje.ENCURSO
            return record

        return self.unit_of_work.run_in_transaction(_action)

    def create_viaje(self, payload: Mapping[str, object]):
        return self.create(payload)

    def update_viaje(self, payload: Mapping[str, object]):
        return self.update(payload)

    def delete_viaje(self, payload: Mapping[str, object] | int):
        return self.delete(payload)

    def terminar_viaje_short(self, payload: Mapping[str, object]):
        return self.terminar_viaje(payload)

    def _normalize_update_payload(
        self,
        record_id_or_payload,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if payload is None:
            if not isinstance(record_id_or_payload, Mapping):
                raise InvalidPayloadError("Se requiere payload para actualizar viaje")
            return dict(record_id_or_payload)

        record_id = self._as_record_id(record_id_or_payload)
        update_payload = self._as_payload(payload, message="Se requiere payload para actualizar viaje")
        return {"id": record_id, **update_payload}

    def _list_unbilled_trips_grouped_by_client(self, session) -> list[dict[str, Any]]:
        rows = (
            session.query(Viaje)
            .options(
                joinedload(Viaje.cliente),
                joinedload(Viaje._ruta),
            )
            .filter(
                Viaje.estado == EstadoViaje.FINALIZADO,
                Viaje._estado_facturacion == EstadoFacturacion.REGISTRADO,
            )
            .order_by(
                Viaje.fecha_posicionamiento.desc(),
                Viaje.id.desc(),
            )
            .all()
        )

        clients_by_id: dict[str, dict[str, Any]] = {}

        for row in rows:
            cliente_id = int(row.cliente_id) if row.cliente_id is not None else None
            conductor_id = int(row.conductor_id) if row.conductor_id is not None else None
            cliente_key = str(cliente_id) if cliente_id is not None else "sin_cliente"

            cliente_label = self._cliente_label(row)
            conductor_label = self._conductor_label(row)

            if cliente_key not in clients_by_id:
                clients_by_id[cliente_key] = {
                    "cliente_id": cliente_id,
                    "cliente_label": cliente_label,
                    "cantidad_viajes": 0,
                    "viajes": [],
                }

            clients_by_id[cliente_key]["viajes"].append(
                {
                    "id": int(row.id),
                    "referencia": str(row.referencia or f"Viaje #{row.id}"),
                    "cliente_id": cliente_id,
                    "cliente_label": cliente_label,
                    "conductor_id": conductor_id,
                    "conductor_label": conductor_label,
                    "descripcion": str(row.descripcion or ""),
                    "fecha_posicionamiento": format_field_value_for_ui(
                        kind="datetime",
                        value=row.fecha_posicionamiento,
                    ),
                    "ruta_label": str(getattr(row._ruta, "descripcion", "") or ""),
                }
            )

            clients_by_id[cliente_key]["cantidad_viajes"] += 1

        return list(clients_by_id.values())

    @staticmethod
    def _default_form_values() -> dict[str, Any]:
        return {
            "referencia": "",
            "cliente_id": "",
            "origen_id": "",
            "destino_id": "",
            "conductor_id": "",
            "furgon_id": "",
            "camion_id": "",
            "thermo_id": "",
            "_ruta_id": "",
            "_circuito_id": "",
            "viaje_ida_id": "",
            "fecha_posicionamiento": "",
            "descripcion": "",
            "viaticos_monto": "",
            "viaticos_moneda": str(Moneda.USD.value),
            "temperatura": "",
            "combustible_base_thermo": "40.0",
            "combustible_base_camion": "60.0",
        }

    def _values_from_record(
        self,
        record: Mapping[str, Any],
        field_index: Mapping[str, Any],
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field_name in (
            "referencia",
            "cliente_id",
            "conductor_id",
            "furgon_id",
            "camion_id",
            "thermo_id",
            "_ruta_id",
            "_circuito_id",
            "fecha_posicionamiento",
            "descripcion",
            "viaticos_monto",
            "viaticos_moneda",
            "temperatura",
        ):
            field = field_index.get(field_name)
            if field is None:
                continue
            values[field_name] = self._format_for_ui(field.kind, record.get(field_name))
        return values

    def _load_nested_state(self, session, viaje_id: int) -> dict[str, Any]:
        detail = session.execute(
            select(DetalleOperacion)
            .options(
                joinedload(DetalleOperacion.ordenes_combustible),
                joinedload(DetalleOperacion.gasto_real_thermo),
            )
            .where(DetalleOperacion.viaje_id == viaje_id)
        ).unique().scalar_one_or_none()
        value_updates: dict[str, Any] = {}
        fuel_orders = [self._serialize_fuel_order(order) for order in detail.ordenes_combustible] if detail else []
        if not fuel_orders:
            fuel_orders = [self._empty_fuel_order()]
        if detail is not None and detail.gasto_real_thermo is not None:
            value_updates["combustible_base_thermo"] = self._format_decimal_ui(
                detail.gasto_real_thermo.combustible_base_thermo
            )

        viaje = session.execute(select(Viaje).where(Viaje.id == viaje_id)).scalar_one()
        ruta = session.execute(select(Ruta).where(Ruta.id == int(viaje._ruta_id))).scalar_one_or_none()
        if ruta is not None:
            value_updates["origen_id"] = int(ruta.origen_id)
            value_updates["destino_id"] = int(ruta.destino_id)
        circuito_id = self._coerce_positive_int(getattr(viaje, "_circuito_id", None))
        if circuito_id is not None:
            value_updates["viaje_ida_id"] = self._resolve_circuito_viaje_ida(session, circuito_id) or ""
            camion = session.execute(
                select(GastoRealCamion).where(GastoRealCamion.circuito_id == circuito_id)
            ).scalar_one_or_none()
            if camion is not None:
                value_updates["combustible_base_camion"] = self._format_decimal_ui(
                    camion.combustible_base_camion
                )

        return {
            "value_updates": value_updates,
            "fuel_orders": fuel_orders,
            "detalle_operacion_id": int(detail.id) if detail is not None else None,
            "circuito_id": circuito_id,
        }

    def _resolve_route(
        self,
        session,
        cliente_id: int,
        origen_id: int,
        destino_id: int,
    ) -> int:
        rows = session.execute(
            select(Ruta.id)
            .join(TarifaFlete, TarifaFlete.ruta_id == Ruta.id)
            .where(TarifaFlete.cliente_id == cliente_id)
            .where(Ruta.origen_id == origen_id)
            .where(Ruta.destino_id == destino_id)
            .distinct()
            .order_by(Ruta.id.asc())
        ).scalars().all()
        if not rows:
            origen = session.get(Ubicacion, origen_id)
            destino = session.get(Ubicacion, destino_id)
            origen_label = getattr(origen, "descripcion", origen_id)
            destino_label = getattr(destino, "descripcion", destino_id)
            raise ValueError(
                f"No existe una ruta tarifada para el cliente seleccionado entre {origen_label} y {destino_label}."
            )
        if len(rows) > 1:
            raise ValueError("La selección de origen y destino es ambigua; hay múltiples rutas para ese cliente.")
        return int(rows[0])

    def _resolve_conductor_equipment_defaults(
        self,
        session,
        conductor_id: int,
    ) -> dict[str, int | None]:
        conductor = session.get(Conductor, conductor_id)
        if conductor is None:
            raise ValueError(f"No se encontro conductor con id={conductor_id}")
        return {
            "camion_id": self._available_equipment_id(session, Camion, getattr(conductor, "camion_id", None)),
            "furgon_id": self._available_equipment_id(session, Furgon, getattr(conductor, "furgon_id", None)),
            "thermo_id": self._available_equipment_id(session, Thermo, getattr(conductor, "thermo_id", None)),
        }

    def _available_equipment_id(self, session, model_cls, value: Any) -> int | None:
        equipment_id = self._coerce_positive_int(value)
        if equipment_id is None:
            return None
        equipment = session.get(model_cls, equipment_id)
        if equipment is None or getattr(equipment, "estado", None) != EstadoCamion.ACTIVO:
            return None
        return equipment_id

    def _resolve_viaje_ida_circuito(self, session, viaje_ida_id: int) -> int | None:
        viaje = session.execute(
            select(Viaje)
            .where(Viaje.id == int(viaje_ida_id))
            .where(Viaje.tipo_viaje == TipoViaje.EXPOR)
        ).scalar_one_or_none()
        if viaje is None:
            raise ValueError("El viaje de ida seleccionado no existe o no es una exportacion.")
        return self._coerce_positive_int(getattr(viaje, "_circuito_id", None))

    def _resolve_circuito_viaje_ida(self, session, circuito_id: int) -> int | None:
        viaje = session.execute(
            select(Viaje.id)
            .where(Viaje._circuito_id == int(circuito_id))
            .where(Viaje.tipo_viaje == TipoViaje.EXPOR)
            .order_by(Viaje.id.asc())
        ).scalar_one_or_none()
        return self._coerce_positive_int(viaje)

    def _resolve_empty_return_route(self, session, viaje_ida_id: int) -> dict[str, int]:
        viaje = session.execute(
            select(Viaje)
            .options(joinedload(Viaje._ruta))
            .where(Viaje.id == int(viaje_ida_id))
            .where(Viaje.tipo_viaje == TipoViaje.EXPOR)
        ).scalar_one_or_none()
        if viaje is None:
            raise ValueError("El viaje de ida seleccionado no existe o no es una exportacion.")
        ruta_ida = getattr(viaje, "_ruta", None)
        if ruta_ida is None:
            raise ValueError("El viaje de ida no tiene ruta asociada.")
        rows = session.execute(
            select(Ruta.id)
            .where(Ruta.origen_id == int(ruta_ida.destino_id))
            .where(Ruta.destino_id == int(ruta_ida.origen_id))
            .order_by(Ruta.id.asc())
        ).scalars().all()
        if not rows:
            raise ValueError("No existe una ruta de retorno valida para crear el viaje vacio.")
        if len(rows) > 1:
            raise ValueError("La ruta de retorno para el viaje vacio es ambigua.")
        return {
            "_ruta_id": int(rows[0]),
            "origen_id": int(ruta_ida.destino_id),
            "destino_id": int(ruta_ida.origen_id),
        }

    def _validate_import_constraints(
        self,
        session,
        circuito_id: int,
        current_values: Mapping[str, Any],
        *,
        exclude_viaje_id: int | None,
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        ida = session.execute(
            select(Viaje)
            .where(Viaje._circuito_id == circuito_id)
            .where(Viaje.tipo_viaje == TipoViaje.EXPOR)
            .order_by(Viaje.id.asc())
        ).scalar_one_or_none()
        if ida is None or (exclude_viaje_id is not None and int(ida.id) == int(exclude_viaje_id)):
            other_export = session.execute(
                select(Viaje)
                .where(Viaje._circuito_id == circuito_id)
                .where(Viaje.tipo_viaje == TipoViaje.EXPOR)
                .where(Viaje.id != int(exclude_viaje_id or 0))
                .order_by(Viaje.id.asc())
            ).scalar_one_or_none()
            ida = other_export
        if ida is None:
            errors["_circuito_id"] = "El circuito seleccionado no tiene viaje de ida disponible."
            return errors

        for field_name, label in (
            ("camion_id", "Camion"),
            ("furgon_id", "Furgon"),
            ("thermo_id", "Thermo"),
        ):
            current = self._coerce_positive_int(current_values.get(field_name))
            expected = self._coerce_positive_int(getattr(ida, field_name, None))
            if current is not None and expected is not None and current != expected:
                errors[field_name] = f"{label} debe coincidir con el viaje de ida del circuito."

        detalle = session.execute(
            select(DetalleOperacion).where(DetalleOperacion.viaje_id == int(ida.id))
        ).scalar_one_or_none()
        if detalle is None:
            errors["_circuito_id"] = "El viaje de ida no tiene detalle de operacion."
            return errors

        descarga = session.execute(
            select(Descarga).where(Descarga.detalle_operacion_id == int(detalle.id))
        ).scalar_one_or_none()
        if descarga is None:
            errors["_circuito_id"] = "El viaje de ida no tiene descarga registrada."
            return errors

        try:
            normalized_posicionamiento = normalize_field_value(
                kind=FieldKind.DATETIME,
                value=current_values.get("fecha_posicionamiento"),
                required=True,
                nullable=False,
            )
        except ValueError:
            errors["fecha_posicionamiento"] = "Este campo es obligatorio."
            return errors

        if descarga.fecha_descarga is None:
            errors["_circuito_id"] = "El viaje de ida no tiene fecha de descarga."
        elif normalized_posicionamiento <= descarga.fecha_descarga.strftime("%Y-%m-%dT%H:%M"):
            errors["fecha_posicionamiento"] = (
                "La fecha de posicionamiento debe ser posterior a la descarga del viaje de ida."
            )
        return errors

    def _list_screen_page(
        self,
        session,
        *,
        page: int,
        page_size: int,
        sort: CatalogSort,
        search_text: str,
    ) -> CatalogPageDTO:
        stmt = select(Viaje).options(joinedload(Viaje.cliente), joinedload(Viaje.conductor))
        if search_text:
            like_value = f"%{search_text}%"
            stmt = stmt.where(
                or_(
                    Viaje.referencia.ilike(like_value),
                    Viaje.descripcion.ilike(like_value),
                    sql_cast(Viaje.cliente_id, String).ilike(like_value),
                    sql_cast(Viaje.conductor_id, String).ilike(like_value),
                    Viaje.cliente.has(Cliente.nombre.ilike(like_value)),
                    Viaje.conductor.has(
                        or_(
                            Conductor.nombre.ilike(like_value),
                            Conductor.apellido.ilike(like_value),
                        )
                    ),
                )
            )

        total_count = session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ).scalar_one()

        stmt = stmt.order_by(*self._screen_ordering(sort))
        rows = session.execute(stmt.offset(page * page_size).limit(page_size)).scalars().all()
        serialized = tuple(
            CatalogRecordDTO(catalog_name="viaje", values=self._serialize_screen_row(viaje))
            for viaje in rows
        )
        return CatalogPageDTO(rows=serialized, total_count=int(total_count), page=page, page_size=page_size)

    def _load_detail_summary(self, session, record_id: int) -> dict[str, Any]:
        viaje = session.execute(
            select(Viaje)
            .options(
                joinedload(Viaje.cliente),
                joinedload(Viaje.conductor),
                joinedload(Viaje.furgon),
                joinedload(Viaje.camion),
                joinedload(Viaje.thermo),
                joinedload(Viaje._ruta).joinedload(Ruta.origen),
                joinedload(Viaje._ruta).joinedload(Ruta.destino),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.ordenes_combustible),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.descarga).joinedload(Descarga.lugar_carga),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.actividad_thermo),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.gasto_real_thermo),
            )
            .where(Viaje.id == record_id)
        ).unique().scalar_one_or_none()
        if viaje is None:
            raise ValueError("No se encontro el viaje seleccionado.")

        detalle = viaje.detalle_operacion
        descarga = detalle.descarga if detalle is not None else None
        actividad = detalle.actividad_thermo if detalle is not None else None
        gasto = detalle.gasto_real_thermo if detalle is not None else None
        viaje_summary = self._serialize_viaje_summary(viaje, descarga)
        return {
            "viaje": dict(viaje_summary),
            "viaje_summary": viaje_summary,
            "detalle_operacion": self._serialize_detalle(detalle),
            "descarga": self._serialize_descarga(descarga, viaje),
            "actividad_thermo": self._serialize_actividad_thermo(actividad),
            "gasto_real_thermo": self._serialize_gasto_real_thermo(gasto),
            "ordenes_combustible": [self._serialize_fuel_order(order) for order in detalle.ordenes_combustible] if detalle is not None else [],
            "ordenes_count": len(detalle.ordenes_combustible) if detalle is not None else 0,
            "consumo_thermo_analysis": self._consumo_analysis_service.analyze_thermo(session, record_id),
            "visible_sections": self._visible_detail_sections(viaje),
        }

    @staticmethod
    def _screen_ordering(sort: CatalogSort) -> list[Any]:
        sort_field = str(sort.field or "fecha_posicionamiento").strip()
        sort_direction = sort.direction
        sort_columns = {
            "referencia": Viaje.referencia,
            "tipo_viaje": Viaje.tipo_viaje,
            "estado": Viaje.estado,
            "fecha_posicionamiento": Viaje.fecha_posicionamiento,
        }
        column = sort_columns.get(sort_field, Viaje.fecha_posicionamiento)
        clauses: list[Any] = []
        clauses.append(column.desc() if sort_direction == CatalogSortDirection.DESC else column.asc())
        if column is not Viaje.id:
            clauses.append(Viaje.id.desc() if sort_direction == CatalogSortDirection.DESC else Viaje.id.asc())
        return clauses

    def _serialize_screen_row(self, viaje: Viaje) -> dict[str, Any]:
        return {
            "id": int(viaje.id),
            "referencia": str(viaje.referencia or f"Viaje #{viaje.id}"),
            "tipo_viaje": self._enum_ui(viaje.tipo_viaje),
            "estado": self._enum_ui(viaje.estado),
            "cliente": self._cliente_label(viaje),
            "cliente_id": int(viaje.cliente_id) if viaje.cliente_id is not None else None,
            "cliente_label": self._cliente_label(viaje),
            "conductor": self._conductor_label(viaje),
            "conductor_id": int(viaje.conductor_id) if viaje.conductor_id is not None else None,
            "conductor_label": self._conductor_label(viaje),
            "fecha_posicionamiento": self._format_for_ui(FieldKind.DATETIME, viaje.fecha_posicionamiento),
        }

    @staticmethod
    def _serialize_detalle(detalle: DetalleOperacion | None) -> dict[str, Any]:
        if detalle is None:
            return {}
        return {
            "id": int(detalle.id),
            "viaje_id": int(detalle.viaje_id),
            "estado": ViajeWorkflowService._enum_ui(detalle.estado),
        }

    @staticmethod
    def _serialize_descarga(descarga: Descarga | None, viaje: Viaje | None = None) -> dict[str, Any]:
        if descarga is None:
            return {}
        return {
            "id": int(descarga.id),
            "detalle_operacion_id": int(descarga.detalle_operacion_id),
            "fecha_posicionamiento": ViajeWorkflowService._format_for_ui(FieldKind.DATETIME, descarga.fecha_posicionamiento),
            "fecha_despacho": ViajeWorkflowService._format_for_ui(FieldKind.DATETIME, descarga.fecha_despacho),
            "fecha_descarga": ViajeWorkflowService._format_for_ui(FieldKind.DATETIME, descarga.fecha_descarga),
            "peso": str(descarga.peso or ""),
            "_lugar_carga_id": int(descarga._lugar_carga_id) if descarga._lugar_carga_id is not None else None,
            "lugar_carga_label": (
                str(descarga.lugar_carga.descripcion)
                if getattr(descarga, "lugar_carga", None) is not None
                else ""
            ),
            "_dias_viajados": ViajeWorkflowService._dias_viajados(viaje, descarga),
        }

    @staticmethod
    def _serialize_gasto_real_thermo(gasto: GastoRealThermo | None) -> dict[str, Any]:
        if gasto is None:
            return {}
        return {
            "id": int(gasto.id),
            "detalle_operacion_id": int(gasto.detalle_operacion_id),
            "combustible_base_thermo": ViajeWorkflowService._format_decimal_ui(gasto.combustible_base_thermo),
            "restante_thermo": ViajeWorkflowService._format_decimal_ui(gasto.restante_thermo),
            "_consumo_thermo": ViajeWorkflowService._format_decimal_ui(gasto._consumo_thermo),
        }

    @staticmethod
    def _serialize_actividad_thermo(actividad: ActividadThermo | None) -> dict[str, Any]:
        if actividad is None:
            return {}
        return {
            "id": int(actividad.id),
            "detalle_operacion_id": int(actividad.detalle_operacion_id),
            "fecha_hora_encendido": ViajeWorkflowService._format_for_ui(
                FieldKind.DATETIME,
                actividad.fecha_hora_encendido,
            ),
            "fecha_hora_apagado": ViajeWorkflowService._format_for_ui(
                FieldKind.DATETIME,
                actividad.fecha_hora_apagado,
            ),
            "_duracion_horas": ViajeWorkflowService._format_decimal_ui(actividad._duracion_horas),
        }

    @staticmethod
    def _serialize_fuel_order(order: OrdenCombustible) -> dict[str, Any]:
        return {
            "id": int(order.id),
            "gasolinera": ViajeWorkflowService._enum_ui(order.gasolinera),
            "numero_orden": order.numero_orden or "",
            "galones_autorizados": ViajeWorkflowService._format_decimal_ui(order.galones_autorizados),
            "tipo": ViajeWorkflowService._enum_ui(order.tipo),
        }

    @staticmethod
    def _empty_fuel_order() -> dict[str, Any]:
        return {
            "id": None,
            "gasolinera": "",
            "numero_orden": "",
            "galones_autorizados": "",
            "tipo": str(TipoOrdenCombustible.CAMION.value),
        }

    def _serialize_viaje_summary(
        self,
        viaje: Viaje,
        descarga: Descarga | None,
    ) -> dict[str, Any]:
        ruta = getattr(viaje, "_ruta", None)
        origen = getattr(ruta, "origen", None)
        destino = getattr(ruta, "destino", None)
        return {
            "id": int(viaje.id),
            "referencia": str(viaje.referencia or f"Viaje #{viaje.id}"),
            "descripcion": str(viaje.descripcion or ""),
            "tipo_viaje": self._enum_ui(viaje.tipo_viaje),
            "estado": self._enum_ui(viaje.estado),
            "cliente_id": int(viaje.cliente_id) if viaje.cliente_id is not None else None,
            "conductor_id": int(viaje.conductor_id) if viaje.conductor_id is not None else None,
            "furgon_id": int(viaje.furgon_id) if viaje.furgon_id is not None else None,
            "camion_id": int(viaje.camion_id) if viaje.camion_id is not None else None,
            "thermo_id": int(viaje.thermo_id) if viaje.thermo_id is not None else None,
            "_ruta_id": int(viaje._ruta_id) if viaje._ruta_id is not None else None,
            "_circuito_id": int(viaje._circuito_id) if viaje._circuito_id is not None else None,
            "cliente_label": self._cliente_label(viaje),
            "conductor_label": self._conductor_label(viaje),
            "furgon_label": self._furgon_label(getattr(viaje, "furgon", None)),
            "camion_label": self._camion_label(getattr(viaje, "camion", None)),
            "thermo_label": self._thermo_label(getattr(viaje, "thermo", None)),
            "ruta_label": self._ruta_label(ruta),
            "origen_label": str(getattr(origen, "descripcion", "") or ""),
            "destino_label": str(getattr(destino, "descripcion", "") or ""),
            "fecha_posicionamiento": self._format_for_ui(FieldKind.DATETIME, viaje.fecha_posicionamiento),
            "fecha_descarga": self._format_for_ui(FieldKind.DATETIME, getattr(descarga, "fecha_descarga", None)),
        }

    @staticmethod
    def _dias_viajados(viaje: Viaje | None, descarga: Descarga | None) -> int | None:
        if viaje is None:
            return None
        fecha_posicionamiento = getattr(viaje, "fecha_posicionamiento", None)
        fecha_descarga = getattr(descarga, "fecha_descarga", None)
        if fecha_posicionamiento is None or fecha_descarga is None:
            return None
        return int((fecha_descarga.date() - fecha_posicionamiento.date()).days) + 1

    @staticmethod
    def _visible_detail_sections(viaje: Viaje) -> list[str]:
        if viaje.tipo_viaje == TipoViaje.EXPOR:
            return ["descarga", "combustible_thermo", "ordenes_combustible"]
        if viaje.tipo_viaje == TipoViaje.VACIO:
            return ["descarga"]
        return ["descarga", "ordenes_combustible"]

    @staticmethod
    def _camion_label(camion: Camion | None) -> str:
        if camion is None:
            return ""
        return str(camion.placa or camion.id)

    @staticmethod
    def _furgon_label(furgon: Furgon | None) -> str:
        if furgon is None:
            return ""
        return str(furgon.placa or furgon.id)

    @staticmethod
    def _thermo_label(thermo: Thermo | None) -> str:
        if thermo is None:
            return ""
        return str(thermo.codigo or thermo.id)

    @staticmethod
    def _ruta_label(ruta: Ruta | None) -> str:
        if ruta is None:
            return ""
        origen = getattr(ruta, "origen", None)
        destino = getattr(ruta, "destino", None)
        origen_label = str(getattr(origen, "descripcion", "") or "")
        destino_label = str(getattr(destino, "descripcion", "") or "")
        if origen_label and destino_label:
            return f"{origen_label} -> {destino_label}"
        return str(getattr(ruta, "id", "") or "")

    @staticmethod
    def _format_for_ui(kind: FieldKind | str, value: Any) -> Any:
        return format_field_value_for_ui(kind=kind, value=value)

    @staticmethod
    def _format_decimal_ui(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _enum_ui(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _cliente_label(viaje: Viaje) -> str:
        cliente = getattr(viaje, "cliente", None)
        if cliente is None:
            return str(getattr(viaje, "cliente_id", "") or "")
        return str(getattr(cliente, "nombre", "") or getattr(viaje, "cliente_id", "") or "")

    @staticmethod
    def _conductor_label(viaje: Viaje) -> str:
        conductor = getattr(viaje, "conductor", None)
        if conductor is None:
            return str(getattr(viaje, "conductor_id", "") or "")
        nombre = getattr(conductor, "nombre", "") or ""
        apellido = getattr(conductor, "apellido", "") or ""
        full_name = f"{nombre} {apellido}".strip()
        return full_name or str(getattr(viaje, "conductor_id", "") or "")

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            normalized = int(value)
            return normalized if normalized > 0 else None
        return None
