"""Domain service for Factura use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from ...domain.modelo.dtos import CatalogRecordDTO
from ...domain.modelo.field_validation import format_field_value_for_ui
from ...domain.modelo.repositories.catalog import ModeloCatalogRepository
from ...infrastructure.persistence.modelo.workflow_orm import (
    DetalleFactura,
    DetalleOperacion,
    EstadoFacturacion,
    EstadoViaje,
    Factura,
    Impuesto,
    Moneda,
    TarifaFlete,
    TipoDetalle,
    TipoGasto,
    TipoImpuesto,
    TipoViaje,
    Viaje,
)
from ...infrastructure.reports.export import FacturaExcelExporter
from ..common.uow import SQLAlchemyUnitOfWork
from ..modelo.use_cases import (
    CreateFacturaConDetallesUseCase,
    DeleteFacturaUseCase,
    GetModelUseCase,
    ListModelUseCase,
    UpdateFacturaUseCase,
)
from .contracts import InvalidIdentifierError, InvalidPayloadError
from .workflow_dtos import CreateFacturaCommand, UpdateFacturaCommand


def _route_label(viaje: Viaje) -> str:
    ruta = getattr(viaje, "_ruta", None)
    if ruta is None:
        return str(getattr(viaje, "_ruta_id", "") or "")
    origen = getattr(getattr(ruta, "origen", None), "descripcion", "") or ""
    destino = getattr(getattr(ruta, "destino", None), "descripcion", "") or ""
    if origen and destino:
        return f"{origen} -> {destino}"
    return origen or destino or str(getattr(viaje, "_ruta_id", "") or "")


def _conductor_label(viaje: Viaje) -> str:
    conductor = getattr(viaje, "conductor", None)
    if conductor is None:
        return str(getattr(viaje, "conductor_id", "") or "")
    nombre = getattr(conductor, "nombre", "") or ""
    apellido = getattr(conductor, "apellido", "") or ""
    full_name = f"{nombre} {apellido}".strip()
    return full_name or str(getattr(viaje, "conductor_id", "") or "")


def _dias_viajados(viaje: Viaje) -> int | None:
    detalle = getattr(viaje, "detalle_operacion", None)
    descarga = getattr(detalle, "descarga", None) if detalle is not None else None
    fecha_descarga = getattr(descarga, "fecha_descarga", None)
    fecha_posicionamiento = getattr(viaje, "fecha_posicionamiento", None)
    if fecha_descarga is None or fecha_posicionamiento is None:
        return None
    return int((fecha_descarga - fecha_posicionamiento).days)


def _money_text(value: Any) -> str:
    return format(float(value or 0), ".2f")


def _rate_text(value: Any) -> str:
    return format(float(value or 0), ".4f")


def _invoice_currency_value(currency: Any) -> str:
    if isinstance(currency, Moneda):
        return currency.value
    return str(currency or Moneda.NIO.value)


def _enum_value(value: Any) -> str:
    return str(value.value if hasattr(value, "value") else value or "")


class FacturaWorkflowService:
    """Orchestrates factura use cases and read models for UI workflows."""

    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        list_factura_use_case: ListModelUseCase,
        get_factura_use_case: GetModelUseCase,
        create_factura_use_case: CreateFacturaConDetallesUseCase,
        update_factura_use_case: UpdateFacturaUseCase,
        delete_factura_use_case: DeleteFacturaUseCase,
    ):
        self.repository = repository
        self.unit_of_work = unit_of_work
        self.list_factura_use_case = list_factura_use_case
        self.get_factura_use_case = get_factura_use_case
        self.create_factura_use_case = create_factura_use_case
        self.update_factura_use_case = update_factura_use_case
        self.delete_factura_use_case = delete_factura_use_case

    @staticmethod
    def _as_payload(payload: Mapping[str, object], *, message: str) -> dict[str, object]:
        if payload is None or not isinstance(payload, Mapping):
            raise InvalidPayloadError(message)
        return dict(payload)

    @staticmethod
    def _as_record_id(record_id: int) -> int:
        if not isinstance(record_id, int) or record_id <= 0:
            raise InvalidIdentifierError("Se requiere identificador valido de factura")
        return record_id

    def list(self, filters: Mapping[str, Any] | None = None) -> list[CatalogRecordDTO]:
        return self.list_factura_use_case.execute(filters)

    def get(self, record_id: int) -> CatalogRecordDTO | None:
        return self.get_factura_use_case.execute(self._as_record_id(record_id))

    def create(self, payload: Mapping[str, object] | CreateFacturaCommand) -> CatalogRecordDTO | None:
        if isinstance(payload, CreateFacturaCommand):
            data = payload.to_payload()
        else:
            data = self._as_payload(payload, message="Se requiere payload para crear factura")
        factura = self.create_factura_use_case.execute(data)
        return self.repository.get_record("factura", cast(int, factura.id))

    def update(
        self,
        record_id_or_payload: int | Mapping[str, object] | UpdateFacturaCommand,
        payload: Mapping[str, object] | None = None,
    ) -> CatalogRecordDTO | None:
        if isinstance(record_id_or_payload, UpdateFacturaCommand):
            data = record_id_or_payload.to_payload()
        else:
            data = self._normalize_update_payload(record_id_or_payload, payload)
        factura = self.update_factura_use_case.execute(data)
        return self.repository.get_record("factura", cast(int, factura.id))

    def delete(self, payload: Mapping[str, object] | int) -> bool:
        if payload is None:
            raise InvalidIdentifierError("Se requiere identificador para eliminar factura")
        return self.delete_factura_use_case.execute(payload)

    def export_excel(self, factura_ids: Sequence[int], target_path: str | Path) -> str:
        normalized_ids = [self._as_record_id(int(factura_id)) for factura_id in factura_ids]
        if not normalized_ids:
            raise InvalidIdentifierError("Se requiere al menos una factura para exportar")
        return self.unit_of_work.run_in_transaction(
            lambda session: self._export_excel(session, normalized_ids, target_path)
        )

    def get_form_state(self, record_id: int) -> dict[str, Any]:
        normalized_record_id = self._as_record_id(record_id)
        return self.unit_of_work.run_in_transaction(
            lambda session: self._load_form_state(session, normalized_record_id)
        )

    def list_tax_options(self) -> list[dict[str, Any]]:
        return self.unit_of_work.run_in_transaction(self._load_tax_options)

    def search_viaje_candidates(
        self,
        cliente_id: int,
        term: str,
        *,
        include_non_finalized: bool = False,
        excluded_viaje_ids: Sequence[int] = (),
    ) -> list[dict[str, Any]]:
        normalized_cliente_id = self._as_record_id(int(cliente_id))
        excluded_ids = {int(viaje_id) for viaje_id in excluded_viaje_ids if int(viaje_id) > 0}
        normalized_term = str(term or "").strip()
        return self.unit_of_work.run_in_transaction(
            lambda session: self._search_viajes(
                session,
                normalized_cliente_id,
                normalized_term,
                include_non_finalized=include_non_finalized,
                excluded_viaje_ids=excluded_ids,
            )
        )

    def crear(self, payload: Mapping[str, object]):
        return self.create(payload)

    def eliminar(self, payload: Mapping[str, object] | int):
        return self.delete(payload)

    def crear_factura(self, payload: Mapping[str, object]):
        return self.create(payload)

    def create_factura(self, payload: Mapping[str, object]):
        return self.create(payload)

    def create_factura_full(self, payload: Mapping[str, object]):
        return self.create(payload)

    def _export_excel(self, session, factura_ids: Sequence[int], target_path: str | Path) -> str:
        facturas = (
            session.execute(
                select(Factura)
                .options(
                    joinedload(Factura.cliente),
                    joinedload(Factura.detalles).joinedload(DetalleFactura.viaje),
                    joinedload(Factura.detalles).joinedload(DetalleFactura.gasto),
                )
                .where(Factura.id.in_(factura_ids))
            )
            .unique()
            .scalars()
            .all()
        )
        by_id = {int(factura.id): factura for factura in facturas}
        ordered_facturas = []
        missing_ids: list[int] = []
        for factura_id in factura_ids:
            factura = by_id.get(int(factura_id))
            if factura is None:
                missing_ids.append(int(factura_id))
            else:
                ordered_facturas.append(factura)
        if missing_ids:
            missing_text = ", ".join(str(factura_id) for factura_id in missing_ids)
            raise ValueError(f"No se encontraron facturas para exportar: {missing_text}")

        FacturaExcelExporter().export(ordered_facturas, target_path)
        return str(Path(target_path))

    def _normalize_update_payload(
        self,
        record_id_or_payload,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if payload is None:
            if not isinstance(record_id_or_payload, Mapping):
                raise InvalidPayloadError("Se requiere payload para actualizar factura")
            return dict(record_id_or_payload)

        record_id = self._as_record_id(record_id_or_payload)
        update_payload = self._as_payload(payload, message="Se requiere payload para actualizar factura")
        return {"id": record_id, **update_payload}

    def _load_form_state(self, session, record_id: int) -> dict[str, Any]:
        factura = session.execute(
            select(Factura)
            .options(
                joinedload(Factura.detalles).joinedload(DetalleFactura.viaje),
                joinedload(Factura.detalles).joinedload(DetalleFactura.gasto),
                joinedload(Factura.impuestos),
            )
            .where(Factura.id == record_id)
        ).unique().scalar_one_or_none()
        if factura is None:
            raise ValueError(f"No se encontro factura con id={record_id}")

        values = {
            "numero_factura": str(factura.numero_factura or ""),
            "fecha_emision": format_field_value_for_ui(kind="datetime", value=factura.fecha_emision),
            "cliente_id": int(factura.cliente_id),
            "dias_credito": str(factura.dias_credito or 0),
            "moneda": _invoice_currency_value(factura.moneda),
            "tasa_cambio": _rate_text(factura.tasa_cambio),
        }
        details: list[dict[str, Any]] = []
        for detail in factura.detalles:
            if detail.tipo == TipoDetalle.GASTO:
                gasto = detail.gasto
                details.append(
                    {
                        "id": int(detail.id),
                        "tipo": TipoDetalle.GASTO.value,
                        "viaje_id": None,
                        "gasto_id": int(detail.gasto_id) if detail.gasto_id is not None else None,
                        "label": str(getattr(gasto, "descripcion", "") or f"Gasto #{detail.id}"),
                        "descripcion": str(getattr(gasto, "descripcion", "") or ""),
                        "gasto_tipo": str(getattr(getattr(gasto, "tipo", None), "value", TipoGasto.OTRO.value)),
                        "source_costo": _money_text(getattr(gasto, "costo", detail.costo)),
                        "source_moneda": _invoice_currency_value(getattr(gasto, "moneda", factura.moneda)),
                        "costo": _money_text(detail.costo),
                    }
                )
                continue

            viaje = detail.viaje
            source_cost = detail.costo
            source_currency = _invoice_currency_value(factura.moneda)
            if viaje is not None:
                tarifas = self._tarifas_for_route(session, int(factura.cliente_id), int(viaje._ruta_id))
                if len(tarifas) == 1:
                    source_cost = tarifas[0].costo
                    source_currency = _invoice_currency_value(tarifas[0].moneda)
            details.append(
                {
                    "id": int(detail.id),
                    "tipo": TipoDetalle.VIAJE.value,
                    "viaje_id": int(detail.viaje_id) if detail.viaje_id is not None else None,
                    "gasto_id": None,
                    "tarifa_id": None,
                    "label": str(getattr(viaje, "referencia", None) or f"Viaje #{detail.viaje_id}"),
                    "descripcion": str(getattr(viaje, "descripcion", "") or ""),
                    "ruta_label": _route_label(viaje) if viaje is not None else "",
                    "conductor_label": _conductor_label(viaje) if viaje is not None else "",
                    "fecha_posicionamiento": format_field_value_for_ui(
                        kind="datetime",
                        value=getattr(viaje, "fecha_posicionamiento", None),
                    ) if viaje is not None else "",
                    "tipo_viaje": _enum_value(getattr(viaje, "tipo_viaje", "")) if viaje is not None else "",
                    "gasto_tipo": "",
                    "source_costo": _money_text(source_cost),
                    "source_moneda": source_currency,
                    "costo": _money_text(detail.costo),
                }
            )

        return {
            "values": values,
            "details": details,
            "tax_ids": [int(impuesto.id) for impuesto in factura.impuestos],
        }

    def _load_tax_options(self, session) -> list[dict[str, Any]]:
        impuestos = session.execute(select(Impuesto).order_by(Impuesto.codigo.asc())).scalars().all()
        return [
            {
                "id": int(impuesto.id),
                "codigo": str(impuesto.codigo),
                "tipo": str(impuesto.tipo.value if hasattr(impuesto.tipo, "value") else impuesto.tipo),
                "porcentaje": _money_text(impuesto.porcentaje),
                "label": f"{impuesto.codigo} ({impuesto.tipo.value} {impuesto.porcentaje}%)",
            }
            for impuesto in impuestos
        ]

    def _search_viajes(
        self,
        session,
        cliente_id: int,
        term: str,
        *,
        include_non_finalized: bool,
        excluded_viaje_ids: set[int],
    ) -> list[dict[str, Any]]:
        stmt = (
            select(Viaje)
            .options(
                joinedload(Viaje.conductor),
                joinedload(Viaje._ruta),
                joinedload(Viaje.detalle_operacion).joinedload(DetalleOperacion.descarga),
            )
            .where(Viaje.cliente_id == cliente_id)
            .where(Viaje._estado_facturacion == EstadoFacturacion.REGISTRADO)
            .where(Viaje.tipo_viaje != TipoViaje.VACIO)
        )
        if not include_non_finalized:
            stmt = stmt.where(Viaje.estado == EstadoViaje.FINALIZADO)
        if term:
            like_value = f"%{term}%"
            stmt = stmt.where(
                or_(
                    Viaje.referencia.ilike(like_value),
                    Viaje.descripcion.ilike(like_value),
                )
            )

        viajes = session.execute(
            stmt.order_by(Viaje.fecha_posicionamiento.desc(), Viaje.id.desc()).limit(20)
        ).scalars().all()
        rows: list[dict[str, Any]] = []
        for viaje in viajes:
            if int(viaje.id) in excluded_viaje_ids:
                continue
            tarifas = [self._tarifa_payload(tarifa) for tarifa in self._tarifas_for_route(session, cliente_id, int(viaje._ruta_id))]
            tarifa_unica = tarifas[0] if len(tarifas) == 1 else None
            rows.append(
                {
                    "value": int(viaje.id),
                    "label": str(viaje.referencia or f"Viaje #{viaje.id}"),
                    "id": int(viaje.id),
                    "referencia": str(viaje.referencia or f"Viaje #{viaje.id}"),
                    "descripcion": str(viaje.descripcion or ""),
                    "ruta_id": int(viaje._ruta_id),
                    "ruta_label": _route_label(viaje),
                    "conductor_label": _conductor_label(viaje),
                    "fecha_posicionamiento": format_field_value_for_ui(
                        kind="datetime",
                        value=viaje.fecha_posicionamiento,
                    ),
                    "tipo_viaje": _enum_value(viaje.tipo_viaje),
                    "dias_viajados": _dias_viajados(viaje),
                    "estado": _enum_value(viaje.estado),
                    "tiene_tarifa": bool(tarifas),
                    "tarifa_count": len(tarifas),
                    "tarifas": tarifas,
                    "tarifa_costo": str(tarifa_unica.get("costo", "0.00") if tarifa_unica else "0.00"),
                    "tarifa_moneda": str(tarifa_unica.get("moneda", Moneda.NIO.value) if tarifa_unica else Moneda.NIO.value),
                }
            )
        return rows

    def _tarifas_for_route(self, session, cliente_id: int, ruta_id: int) -> list[TarifaFlete]:
        return list(
            session.execute(
                select(TarifaFlete)
                .where(
                    TarifaFlete.cliente_id == int(cliente_id),
                    TarifaFlete.ruta_id == int(ruta_id),
                )
                .order_by(TarifaFlete.id.asc())
            ).scalars()
        )

    def _tarifa_payload(self, tarifa: TarifaFlete) -> dict[str, Any]:
        descripcion = str(getattr(tarifa, "descripcion", "") or "").strip()
        moneda = _invoice_currency_value(tarifa.moneda)
        costo = _money_text(tarifa.costo)
        label = f"{moneda} {costo}"
        if descripcion:
            label = f"{label} - {descripcion}"
        return {
            "id": int(tarifa.id),
            "label": label,
            "costo": costo,
            "moneda": moneda,
            "descripcion": descripcion,
        }
