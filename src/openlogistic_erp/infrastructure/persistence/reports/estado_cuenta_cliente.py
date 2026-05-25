"""SQLAlchemy reader for estado de cuenta cliente."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload

from openlogistic_erp.domain.reports import ReportColumn, ReportPayload, ReportTable
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    Cliente,
    EstadoFactura,
    EstadoRecibo,
    Factura,
    Moneda,
    ReciboFactura,
)

from .base import ReportReaderBase


class EstadoCuentaClienteReportReader(ReportReaderBase):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        cliente_id = self.parse_int(params.get("cliente_id"))
        if cliente_id is None:
            raise ValueError("Debes seleccionar un cliente.")
        start_dt, end_dt = _parse_optional_date_range(params.get("rango_fechas"))
        estado = _parse_estado_factura(params.get("estado_factura"))

        with self._session_factory() as session:
            cliente = session.get(Cliente, cliente_id)
            query = (
                session.query(Factura)
                .options(
                    joinedload(Factura.cliente),
                    joinedload(Factura.recibos_facturas).joinedload(ReciboFactura.recibo),
                )
                .filter(Factura.cliente_id == cliente_id)
            )
            if start_dt is not None:
                query = query.filter(Factura.fecha_emision >= start_dt)
            if end_dt is not None:
                query = query.filter(Factura.fecha_emision <= end_dt)
            if estado is not None:
                query = query.filter(Factura.estado == estado)
            else:
                query = query.filter(Factura.estado != EstadoFactura.ANULADA)
            facturas = query.all()

        nombre_cliente = cliente.nombre if cliente is not None else "Cliente"
        currencies: set[Moneda] = set()
        totals: dict[Moneda, dict[str, float]] = {moneda: {"facturado": 0.0, "pagado": 0.0} for moneda in Moneda}
        factura_rows: list[dict[str, Any]] = []
        pagos_rows: list[dict[str, Any]] = []

        for factura in facturas:
            moneda = _to_moneda(getattr(factura, "moneda", None))
            if moneda is None:
                continue
            currencies.add(moneda)
            total = float(factura._total or 0)
            pagado = _sumar_pagos(factura, start_dt, end_dt)
            saldo = round(max(total - pagado, 0.0), 2)
            totals[moneda]["facturado"] += total
            totals[moneda]["pagado"] += pagado

            factura_rows.append(
                {
                    "factura": factura.numero_factura,
                    "fecha_emision": factura.fecha_emision,
                    "fecha_vencimiento": _fecha_vencimiento(factura),
                    "total": round(total, 2),
                    "pagado": round(pagado, 2),
                    "saldo": saldo,
                    "estado": factura.estado.value if factura.estado else "",
                    "ultimo_pago": _ultimo_pago(factura, start_dt, end_dt),
                    "moneda": moneda.value,
                    "moneda_key": moneda.name,
                }
            )

            for rf in factura.recibos_facturas:
                recibo = rf.recibo
                if not _payment_applies_to_report(recibo, start_dt, end_dt):
                    continue
                pagos_rows.append(
                    {
                        "recibo": recibo.referencia,
                        "fecha": recibo.fecha_emision,
                        "factura": factura.numero_factura,
                        "monto": round(float(rf.monto_pagado or 0), 2),
                        "moneda": moneda.value,
                        "moneda_key": moneda.name,
                    }
                )

        resumen_rows = []
        for moneda in sorted(currencies, key=lambda item: item.value):
            total_facturado = round(totals[moneda]["facturado"], 2)
            total_pagado = round(totals[moneda]["pagado"], 2)
            resumen_rows.append(
                {
                    "moneda": moneda.value,
                    "moneda_key": moneda.name,
                    "total_facturado": total_facturado,
                    "total_pagado": total_pagado,
                    "saldo": round(max(total_facturado - total_pagado, 0.0), 2),
                }
            )

        factura_rows.sort(key=lambda row: row["fecha_emision"] or datetime.min)
        pagos_rows.sort(key=lambda row: row["fecha"] or datetime.min)

        tables = [
            ReportTable(
                key="estado_cuenta_resumen",
                title=f"Resumen - {nombre_cliente}",
                columns=(
                    ReportColumn("moneda", "Moneda"),
                    ReportColumn("total_facturado", "Total facturado", "currency"),
                    ReportColumn("total_pagado", "Total cobrado", "currency"),
                    ReportColumn("saldo", "Saldo pendiente", "currency"),
                ),
                rows=tuple(resumen_rows),
                currency_field="moneda_key",
            ),
            ReportTable(
                key="estado_cuenta_facturas",
                title="Detalle de facturas",
                columns=(
                    ReportColumn("factura", "Factura"),
                    ReportColumn("fecha_emision", "Fecha emision", "datetime"),
                    ReportColumn("fecha_vencimiento", "Fecha vencimiento", "datetime"),
                    ReportColumn("total", "Total", "currency"),
                    ReportColumn("pagado", "Pagado", "currency"),
                    ReportColumn("saldo", "Saldo", "currency"),
                    ReportColumn("estado", "Estado"),
                    ReportColumn("ultimo_pago", "Ultimo pago", "datetime"),
                    ReportColumn("moneda", "Moneda"),
                ),
                rows=tuple(factura_rows),
                currency_field="moneda_key",
            ),
        ]

        if pagos_rows:
            tables.append(
                ReportTable(
                    key="estado_cuenta_pagos",
                    title="Pagos registrados",
                    columns=(
                        ReportColumn("recibo", "Recibo"),
                        ReportColumn("fecha", "Fecha", "datetime"),
                        ReportColumn("factura", "Factura aplicada"),
                        ReportColumn("monto", "Monto", "currency"),
                        ReportColumn("moneda", "Moneda"),
                    ),
                    rows=tuple(pagos_rows),
                    currency_field="moneda_key",
                )
            )

        return ReportPayload(
            title=f"Estado de cuenta - {nombre_cliente}",
            generated_at=datetime.now(),
            tables=tuple(tables),
            currencies=_currency_list(currencies),
        )


def _parse_estado_factura(value: Any) -> EstadoFactura | None:
    if value in (None, ""):
        return None
    if isinstance(value, EstadoFactura):
        return value
    return EstadoFactura(str(value))


def _parse_optional_date_range(raw: Any) -> tuple[datetime | None, datetime | None]:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        for endpoint in raw:
            if _has_date_value(endpoint) and ReportReaderBase.parse_date(endpoint) is None:
                raise ValueError("Debes indicar un rango de fechas valido.")
    return ReportReaderBase.parse_date_range(raw)


def _has_date_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _fecha_vencimiento(factura: Factura) -> datetime | None:
    if factura.fecha_emision is None:
        return None
    return factura.fecha_emision + timedelta(days=int(factura.dias_credito or 0))


def _sumar_pagos(factura: Factura, start_dt: datetime | None, end_dt: datetime | None) -> float:
    total = 0.0
    for rf in factura.recibos_facturas:
        if not _payment_applies_to_report(rf.recibo, start_dt, end_dt):
            continue
        total += float(rf.monto_pagado or 0)
    return round(total, 2)


def _ultimo_pago(factura: Factura, start_dt: datetime | None, end_dt: datetime | None) -> datetime | None:
    ultima_fecha: datetime | None = None
    for rf in factura.recibos_facturas:
        recibo = rf.recibo
        if not _payment_applies_to_report(recibo, start_dt, end_dt) or recibo.fecha_emision is None:
            continue
        if ultima_fecha is None or recibo.fecha_emision > ultima_fecha:
            ultima_fecha = recibo.fecha_emision
    return ultima_fecha


def _payment_applies_to_report(
    recibo: Any,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> bool:
    if not recibo or recibo.estado == EstadoRecibo.ANULADO:
        return False
    fecha_emision = recibo.fecha_emision
    if fecha_emision is None:
        return start_dt is None and end_dt is None
    if start_dt is not None and fecha_emision < start_dt:
        return False
    if end_dt is not None and fecha_emision > end_dt:
        return False
    return True


def _to_moneda(moneda: Any) -> Moneda | None:
    if isinstance(moneda, Moneda):
        return moneda
    if moneda is None:
        return None
    try:
        return Moneda(moneda)
    except Exception:
        try:
            return Moneda(moneda.value)
        except Exception:
            return None


def _currency_list(currencies: set[Moneda]) -> tuple[dict[str, str], ...]:
    return tuple({"key": moneda.name, "label": moneda.value} for moneda in sorted(currencies, key=lambda item: item.value))
