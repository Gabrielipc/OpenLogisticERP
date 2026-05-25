"""Domain service for Circuito use cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ...domain.modelo.dtos import CatalogRecordDTO, FieldKind
from ...domain.modelo.field_validation import format_field_value_for_ui
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from ...infrastructure.persistence.modelo.workflow_orm import (
    Circuito,
    GastoRealCamion,
    MovimientoAdicional,
    Ruta,
    TipoViaje,
    Viaje,
)
from ..common.uow import SQLAlchemyUnitOfWork
from ..modelo.use_cases import (
    CloseCircuitoUseCase,
    CreateModelUseCase,
    DeleteCircuitoUseCase,
    GetModelUseCase,
    ListModelUseCase,
    UpdateCircuitoSectionsUseCase,
    UpdateModelUseCase,
)
from .contracts import InvalidIdentifierError, InvalidPayloadError
from .consumo_analysis_service import ConsumoAnalysisService
from .workflow_dtos import CloseCircuitoCommand, UpdateCircuitoSectionsCommand


class CircuitoWorkflowService:
    """Orchestrates circuito use cases."""

    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        list_circuito_use_case: ListModelUseCase,
        get_circuito_use_case: GetModelUseCase,
        create_circuito_use_case: CreateModelUseCase,
        update_circuito_use_case: UpdateModelUseCase,
        delete_circuito_use_case: DeleteCircuitoUseCase,
        close_circuito_use_case: CloseCircuitoUseCase,
        update_circuito_sections_use_case: UpdateCircuitoSectionsUseCase,
    ):
        self.repository = repository
        self.unit_of_work = unit_of_work
        self.list_circuito_use_case = list_circuito_use_case
        self.get_circuito_use_case = get_circuito_use_case
        self.create_circuito_use_case = create_circuito_use_case
        self.update_circuito_use_case = update_circuito_use_case
        self.delete_circuito_use_case = delete_circuito_use_case
        self.close_circuito_use_case = close_circuito_use_case
        self.update_circuito_sections_use_case = update_circuito_sections_use_case
        self._consumo_analysis_service = ConsumoAnalysisService()

    @staticmethod
    def _as_payload(payload: Mapping[str, object], *, message: str) -> dict[str, object]:
        if payload is None or not isinstance(payload, Mapping):
            raise InvalidPayloadError(message)
        return dict(payload)

    @staticmethod
    def _as_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("Se requiere identificador valido de circuito")
        return record_id

    def list(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        return self.list_circuito_use_case.execute(filters)

    def get(self, record_id: int) -> CatalogRecordDTO | None:
        return self.get_circuito_use_case.execute(self._as_record_id(record_id))

    def get_detail_summary(self, record_id: int) -> dict[str, Any]:
        normalized_record_id = self._as_record_id(record_id)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._load_detail_summary(session, normalized_record_id)
        )

    def create(self, payload: Mapping[str, object]) -> CatalogRecordDTO:
        data = self._as_payload(payload, message="Se requiere payload para crear circuito")
        return self.create_circuito_use_case.execute(data)

    def update(self, record_id_or_payload, payload: Mapping[str, object] | None = None) -> CatalogRecordDTO:
        data = self._normalize_update_payload(record_id_or_payload, payload)
        return self.update_circuito_use_case.execute(data)

    def delete(self, payload: Mapping[str, object] | int) -> bool:
        if payload is None:
            raise InvalidIdentifierError("Se requiere identificador para eliminar circuito")
        return self.delete_circuito_use_case.execute(payload)

    def cerrar(self, circuito: object | CloseCircuitoCommand):
        target = circuito.to_payload() if isinstance(circuito, CloseCircuitoCommand) else circuito
        if target is None:
            raise InvalidPayloadError("Se requiere circuito")
        return self.close_circuito_use_case.execute(target)

    def actualizar_secciones(self, circuito, secciones_data=None):
        if isinstance(circuito, UpdateCircuitoSectionsCommand):
            payload = circuito.to_payload()
            circuito = payload if not isinstance(payload, dict) else payload.get("circuito")
            secciones_data = payload.get("secciones_data") if isinstance(payload, dict) else None
        if circuito is None:
            raise InvalidPayloadError("Se requiere circuito")
        if secciones_data is None:
            return self.update_circuito_sections_use_case.execute(circuito)
        return self.update_circuito_sections_use_case.execute(
            {
                "circuito": circuito,
                "secciones_data": secciones_data,
            }
        )

    def guardar_secciones_circuito(self, circuito, secciones_data=None):
        return self.actualizar_secciones(circuito, secciones_data)

    def chequear_y_cerrar_circuito(self, circuito):
        return self.cerrar(circuito)

    def close_circuito(self, circuito):
        return self.cerrar(circuito)

    def _load_detail_summary(self, session, record_id: int) -> dict[str, Any]:
        circuito = session.execute(
            select(Circuito)
            .options(
                joinedload(Circuito.viajes).joinedload(Viaje.cliente),
                joinedload(Circuito.viajes).joinedload(Viaje.conductor),
                joinedload(Circuito.viajes).joinedload(Viaje.furgon),
                joinedload(Circuito.viajes).joinedload(Viaje.camion),
                joinedload(Circuito.viajes).joinedload(Viaje.thermo),
                joinedload(Circuito.viajes).joinedload(Viaje._ruta).joinedload(Ruta.origen),
                joinedload(Circuito.viajes).joinedload(Viaje._ruta).joinedload(Ruta.destino),
                joinedload(Circuito.gasto_real_camion),
                joinedload(Circuito.movimientos_adicionales).joinedload(MovimientoAdicional.ruta).joinedload(Ruta.origen),
                joinedload(Circuito.movimientos_adicionales).joinedload(MovimientoAdicional.ruta).joinedload(Ruta.destino),
            )
            .where(Circuito.id == record_id)
        ).unique().scalar_one_or_none()
        if circuito is None:
            raise ValueError("No se encontro el circuito seleccionado.")

        viajes = sorted(list(circuito.viajes or []), key=lambda viaje: int(viaje.id or 0))
        viaje_ida = next((viaje for viaje in viajes if viaje.tipo_viaje == TipoViaje.EXPOR), None)
        if viaje_ida is None and viajes:
            viaje_ida = viajes[0]
        viaje_vuelta = next(
            (viaje for viaje in viajes if viaje is not viaje_ida and viaje.tipo_viaje in {TipoViaje.IMPOR, TipoViaje.VACIO}),
            None,
        )

        return {
            "circuito": self._serialize_circuito(circuito),
            "viaje_ida": self._serialize_viaje(viaje_ida),
            "viaje_vuelta": self._serialize_viaje(viaje_vuelta),
            "viajes": [self._serialize_viaje(viaje) for viaje in viajes],
            "gasto_real_camion": self._serialize_gasto_real_camion(circuito.gasto_real_camion),
            "movimientos_adicionales": [
                self._serialize_movimiento_adicional(item)
                for item in sorted(circuito.movimientos_adicionales or [], key=lambda row: int(row.id or 0))
            ],
            "consumo_camion_analysis": self._consumo_analysis_service.analyze_camion(session, record_id),
            "visible_sections": ["gasto_real_camion", "movimientos_adicionales"],
            "can_add_return_trip": viaje_vuelta is None,
        }

    @staticmethod
    def _serialize_circuito(circuito: Circuito) -> dict[str, Any]:
        return {
            "id": int(circuito.id),
            "fecha_inicio": format_field_value_for_ui(kind=FieldKind.DATETIME, value=circuito.fecha_inicio),
            "fecha_fin": format_field_value_for_ui(kind=FieldKind.DATETIME, value=circuito.fecha_fin),
            "estado": CircuitoWorkflowService._enum_ui(circuito.estado),
        }

    @staticmethod
    def _serialize_gasto_real_camion(gasto: GastoRealCamion | None) -> dict[str, Any]:
        if gasto is None:
            return {"combustible_base_camion": "60", "retorno_camion": "", "_consumo_camion": ""}
        return {
            "id": int(gasto.id),
            "circuito_id": int(gasto.circuito_id),
            "combustible_base_camion": CircuitoWorkflowService._format_decimal_ui(gasto.combustible_base_camion),
            "retorno_camion": CircuitoWorkflowService._format_decimal_ui(gasto.retorno_camion),
            "_consumo_camion": CircuitoWorkflowService._format_decimal_ui(gasto._consumo_camion),
        }

    @staticmethod
    def _serialize_movimiento_adicional(movimiento: MovimientoAdicional) -> dict[str, Any]:
        ruta = getattr(movimiento, "ruta", None)
        return {
            "id": int(movimiento.id),
            "circuito_id": int(movimiento.circuito_id),
            "ruta_id": int(movimiento.ruta_id) if movimiento.ruta_id is not None else None,
            "ruta_label": CircuitoWorkflowService._ruta_label(ruta),
            "fecha_movimiento": format_field_value_for_ui(kind=FieldKind.DATETIME, value=movimiento.fecha_movimiento),
            "descripcion": str(movimiento.descripcion or ""),
            "es_triangulado": bool(getattr(movimiento, "es_triangulado", False)),
        }

    @staticmethod
    def _serialize_viaje(viaje: Viaje | None) -> dict[str, Any]:
        if viaje is None:
            return {}
        ruta = getattr(viaje, "_ruta", None)
        return {
            "id": int(viaje.id),
            "referencia": str(viaje.referencia or f"Viaje #{viaje.id}"),
            "descripcion": str(viaje.descripcion or ""),
            "tipo_viaje": CircuitoWorkflowService._enum_ui(viaje.tipo_viaje),
            "estado": CircuitoWorkflowService._enum_ui(viaje.estado),
            "cliente_label": CircuitoWorkflowService._cliente_label(viaje),
            "conductor_label": CircuitoWorkflowService._conductor_label(viaje),
            "camion_label": str(getattr(getattr(viaje, "camion", None), "placa", "") or ""),
            "furgon_label": str(getattr(getattr(viaje, "furgon", None), "placa", "") or ""),
            "thermo_label": str(getattr(getattr(viaje, "thermo", None), "codigo", "") or ""),
            "ruta_label": CircuitoWorkflowService._ruta_label(ruta),
            "fecha_posicionamiento": format_field_value_for_ui(
                kind=FieldKind.DATETIME,
                value=viaje.fecha_posicionamiento,
            ),
        }

    @staticmethod
    def _ruta_label(ruta: Ruta | None) -> str:
        if ruta is None:
            return ""
        origen = str(getattr(getattr(ruta, "origen", None), "descripcion", "") or "")
        destino = str(getattr(getattr(ruta, "destino", None), "descripcion", "") or "")
        if origen and destino:
            return f"{origen} -> {destino}"
        return str(getattr(ruta, "id", "") or "")

    @staticmethod
    def _cliente_label(viaje: Viaje) -> str:
        cliente = getattr(viaje, "cliente", None)
        return str(getattr(cliente, "nombre", "") or getattr(viaje, "cliente_id", "") or "")

    @staticmethod
    def _conductor_label(viaje: Viaje) -> str:
        conductor = getattr(viaje, "conductor", None)
        nombre = str(getattr(conductor, "nombre", "") or "")
        apellido = str(getattr(conductor, "apellido", "") or "")
        return f"{nombre} {apellido}".strip() or str(getattr(viaje, "conductor_id", "") or "")

    @staticmethod
    def _format_decimal_ui(value: Any) -> str:
        if value in (None, ""):
            return ""
        try:
            return format(float(value), ".0f") if float(value).is_integer() else format(float(value), ".2f")
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _enum_ui(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def _normalize_update_payload(self, record_id_or_payload, payload: Mapping[str, object] | None = None) -> dict[str, object]:
        if payload is None:
            if not isinstance(record_id_or_payload, Mapping):
                raise InvalidPayloadError("Se requiere payload para actualizar circuito")
            return dict(record_id_or_payload)

        record_id = self._as_record_id(record_id_or_payload)
        update_payload = self._as_payload(payload, message="Se requiere payload para actualizar circuito")
        return {"id": record_id, **update_payload}
