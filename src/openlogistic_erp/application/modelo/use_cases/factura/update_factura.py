"""Use case to update factura details, taxes and totals atomically."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from .....application.common.uow import SQLAlchemyUnitOfWork
from .....domain.modelo.repositories.catalog import ModeloCatalogRepository
from .....infrastructure.persistence.modelo.workflow_orm import (
    EstadoFacturacion,
    Factura,
    Gasto,
    Impuesto,
    Moneda,
    TipoImpuesto,
    TipoDetalle,
    TipoGasto,
    Viaje,
    parse_money,
    parse_percent,
    q2,
    q4,
)
from ...contracts import InvalidIdentifierError, InvalidPayloadError
from ...factories.detalle_factura_factory import DetalleFacturaFactory


class UpdateFacturaUseCase:
    def __init__(
        self,
        repository: ModeloCatalogRepository,
        unit_of_work: SQLAlchemyUnitOfWork,
        detalle_factura_factory: DetalleFacturaFactory,
    ):
        self._repository = repository
        self._uow = unit_of_work
        self._detalle_factory = detalle_factura_factory

    def execute(self, payload: dict[str, Any]) -> Factura:
        if not isinstance(payload, Mapping):
            raise InvalidPayloadError("Se requiere payload para actualizar factura")

        payload = dict(payload)
        factura_id = self._resolve_factura_id(payload)
        factura_data = payload.get("factura", {})
        detalles_data = payload.get("detalles_data", []) or []
        impuestos_data = payload.get("impuestos", []) or []

        def _action(session):
            factura = session.get(Factura, factura_id)
            if factura is None:
                raise ValueError(f"Factura no encontrada: id={factura_id}")

            if isinstance(factura_data, Mapping):
                self._update_factura_fields(factura, dict(factura_data))

            self._update_detalles(session, factura, detalles_data)
            factura.impuestos = self._resolve_impuestos(session, impuestos_data)

            subtotal = self._calcular_subtotal(factura)
            total = self._calcular_total(factura, subtotal)
            factura._subtotal = subtotal
            factura._total = total
            session.add(factura)
            session.flush()
            return factura

        return self._uow.run_in_transaction(_action)

    def _resolve_factura_id(self, payload: dict[str, Any]) -> int:
        factura_id = payload.get("id")
        factura_data = payload.get("factura")
        if factura_id is None and isinstance(factura_data, Mapping):
            factura_id = factura_data.get("id")
        if not isinstance(factura_id, int) or factura_id <= 0:
            raise InvalidIdentifierError("Se requiere id de factura para actualizar")
        return factura_id

    def _update_factura_fields(self, factura: Factura, factura_data: dict[str, Any]) -> None:
        for field, value in factura_data.items():
            if field == "id":
                continue
            if hasattr(factura, field):
                value = self._normalize_factura_field(field, value)
                setattr(factura, field, value)

    def _update_detalles(self, session, factura: Factura, nuevos_detalles: list[dict[str, Any]]) -> None:
        current_detalles = factura.detalles if factura.detalles is not None else []
        detalles_por_id = {
            detalle.id: detalle for detalle in current_detalles if getattr(detalle, "id", None) is not None
        }
        incoming_ids = {
            item["id"] for item in nuevos_detalles if isinstance(item, Mapping) and item.get("id") is not None
        }

        for detalle in list(current_detalles):
            detalle_id = getattr(detalle, "id", None)
            if detalle_id is not None and detalle_id not in incoming_ids:
                session.delete(detalle)
                current_detalles.remove(detalle)

        for item_data in nuevos_detalles:
            if not isinstance(item_data, Mapping):
                continue

            item_data = dict(item_data)
            detalle_id = item_data.get("id")
            if detalle_id is not None and detalle_id in detalles_por_id:
                self._update_existing_detalle(session, detalles_por_id[detalle_id], item_data)
                continue

            nueva_instancia = self._create_detalle(session, item_data, factura_id=cast(int, factura.id))
            current_detalles.append(nueva_instancia)
            session.add(nueva_instancia)

    def _resolve_impuestos(self, session, impuestos_data) -> list[Impuesto]:
        resolved: list[Impuesto] = []
        for item in impuestos_data:
            impuesto = session.get(Impuesto, int(item)) if isinstance(item, int) else item
            if impuesto is not None:
                resolved.append(impuesto)
        return resolved

    def _calcular_subtotal(self, factura: Factura) -> Decimal:
        return q2(sum((parse_money(detalle.costo) for detalle in factura.detalles), Decimal("0")))

    def _calcular_total(self, factura: Factura, subtotal: Decimal) -> Decimal:
        base = q2(subtotal)
        impuestos = Decimal("0")
        retenciones = Decimal("0")

        for impuesto in factura.impuestos:
            porcentaje = parse_percent(impuesto.porcentaje or 0)
            if impuesto.tipo == TipoImpuesto.RETENCION:
                retenciones += porcentaje
            else:
                impuestos += porcentaje

        total = base + base * (impuestos / Decimal("100")) - base * (retenciones / Decimal("100"))
        return q2(total)

    def _update_existing_detalle(self, session, instance, data: dict[str, Any]) -> None:
        old_viaje_id = getattr(instance, "viaje_id", None)
        old_gasto_id = getattr(instance, "gasto_id", None)
        old_tipo = getattr(instance, "tipo", None)
        payload = dict(data)
        gasto_payload = payload.pop("gasto_data", None)
        if gasto_payload is not None:
            gasto = instance.gasto if getattr(instance, "gasto", None) is not None else None
            gasto = self._create_or_update_gasto(gasto, dict(gasto_payload))
            session.add(gasto)
            session.flush()
            payload["gasto_id"] = cast(int, gasto.id)
            payload.setdefault("costo", gasto_payload.get("costo", gasto.costo))
        self._update_instance(instance, payload)
        self._sync_related_entities(session, old_tipo=old_tipo, old_viaje_id=old_viaje_id, old_gasto_id=old_gasto_id, instance=instance)

    def _update_instance(self, instance, data: dict[str, Any]) -> None:
        for attr, value in data.items():
            if attr == "id":
                continue
            if hasattr(instance, attr):
                if attr == "costo":
                    value = parse_money(value)
                setattr(instance, attr, value)

    def _normalize_factura_field(self, field: str, value: Any) -> Any:
        if field in {"_subtotal", "_total"}:
            return parse_money(value)
        if field == "tasa_cambio":
            return q4(value)
        return value

    def _create_detalle(self, session, detalle_payload: dict[str, Any], *, factura_id: int):
        payload = dict(detalle_payload)
        gasto_payload = payload.pop("gasto_data", None)
        if gasto_payload is not None:
            gasto = self._create_or_update_gasto(None, dict(gasto_payload))
            session.add(gasto)
            session.flush()
            payload["gasto_id"] = cast(int, gasto.id)
            payload.setdefault("costo", gasto_payload.get("costo", gasto.costo))
        return self._detalle_factory.create_with_data(payload, factura_id=factura_id)

    @staticmethod
    def _create_or_update_gasto(existing: Gasto | None, gasto_payload: dict[str, Any]) -> Gasto:
        gasto = existing or Gasto(
            tipo=TipoGasto.OTRO,
            descripcion=None,
            costo=Decimal("0.00"),
            moneda=Moneda.NIO,
        )
        tipo = gasto_payload.get("tipo")
        if tipo is not None:
            gasto.tipo = tipo if isinstance(tipo, TipoGasto) else TipoGasto(tipo)
        gasto.descripcion = gasto_payload.get("descripcion")
        if "costo" in gasto_payload:
            gasto.costo = parse_money(gasto_payload.get("costo"))
        moneda = gasto_payload.get("moneda")
        if moneda is not None:
            gasto.moneda = moneda if isinstance(moneda, Moneda) else Moneda(moneda)
        return gasto

    @staticmethod
    def _sync_related_entities(session, *, old_tipo, old_viaje_id, old_gasto_id, instance) -> None:
        new_tipo = getattr(instance, "tipo", None)
        new_viaje_id = getattr(instance, "viaje_id", None)
        new_gasto_id = getattr(instance, "gasto_id", None)

        if old_viaje_id and (old_viaje_id != new_viaje_id or new_tipo != TipoDetalle.VIAJE):
            viaje = session.get(Viaje, int(old_viaje_id))
            if viaje is not None:
                viaje.estado_facturacion = EstadoFacturacion.REGISTRADO
        if new_viaje_id and (old_viaje_id != new_viaje_id or old_tipo != TipoDetalle.VIAJE):
            viaje = session.get(Viaje, int(new_viaje_id))
            if viaje is not None:
                viaje.estado_facturacion = EstadoFacturacion.FACTURADO
        if old_gasto_id and (old_gasto_id != new_gasto_id or new_tipo != TipoDetalle.GASTO):
            gasto = session.get(Gasto, int(old_gasto_id))
            if gasto is not None:
                session.delete(gasto)
