"""SQLAlchemy reader for cuentas por cobrar aging."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import joinedload

from openlogistic_erp.domain.reports import ReportColumn, ReportPayload, ReportTable
from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import (
    EstadoFactura,
    EstadoRecibo,
    Factura,
    Moneda,
    ReciboFactura,
)

from .base import ReportReaderBase


class CuentasPorCobrarAgingReportReader(ReportReaderBase):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        fecha_corte_dt = _end_of_day(_parse_required_fecha_corte(params.get("fecha_corte"), self))
        fecha_corte = fecha_corte_dt.date()
        cliente_id = self.parse_int(params.get("cliente_id"))

        with self._session_factory() as session:
            query = (
                session.query(Factura)
                .options(
                    joinedload(Factura.cliente),
                    joinedload(Factura.recibos_facturas).joinedload(ReciboFactura.recibo),
                )
                .filter(Factura.estado != EstadoFactura.ANULADA)
                .filter(Factura.fecha_emision <= fecha_corte_dt)
            )
            if cliente_id is not None:
                query = query.filter(Factura.cliente_id == cliente_id)
            facturas = query.all()

        resumen = defaultdict(_empty_aging_summary)
        detalle_rows: list[dict[str, Any]] = []
        currencies: set[Moneda] = set()
        bucket_labels = _bucket_labels()

        for factura in facturas:
            cliente = factura.cliente
            moneda = _to_moneda(getattr(factura, "moneda", None))
            if cliente is None or moneda is None:
                continue

            total = float(factura._total or 0)
            pagado = _sumar_pagos_hasta(factura, fecha_corte_dt)
            saldo = round(max(total - pagado, 0.0), 2)
            if saldo <= 0:
                continue

            currencies.add(moneda)
            fecha_vencimiento = _fecha_vencimiento(factura)
            dias_atraso, bucket_key = _aging_bucket(fecha_vencimiento, fecha_corte)

            row = resumen[(int(cliente.id), moneda)]
            row["cliente"] = cliente.nombre
            row["moneda"] = moneda.value
            row["moneda_key"] = moneda.name
            row["facturas"] += 1
            row["saldo_total"] = round(row["saldo_total"] + saldo, 2)
            row[bucket_key] = round(row[bucket_key] + saldo, 2)

            detalle_rows.append(
                {
                    "cliente": cliente.nombre,
                    "numero": factura.numero_factura,
                    "fecha_emision": factura.fecha_emision,
                    "fecha_vencimiento": fecha_vencimiento,
                    "dias_atraso": dias_atraso,
                    "saldo": saldo,
                    "bucket": bucket_labels[bucket_key],
                    "estado": factura.estado.value if factura.estado else "",
                    "moneda": moneda.value,
                    "moneda_key": moneda.name,
                }
            )

        resumen_rows = list(resumen.values())
        resumen_rows.sort(key=lambda row: (str(row["cliente"]).lower(), str(row["moneda_key"])))
        detalle_rows.sort(key=lambda row: (str(row["cliente"]).lower(), row["fecha_vencimiento"] or fecha_corte_dt))

        tables = [
            ReportTable(
                key="aging_resumen",
                title=f"Antiguedad de saldos al {self.format_date(fecha_corte_dt)}",
                columns=(
                    ReportColumn("cliente", "Cliente"),
                    ReportColumn("saldo_total", "Saldo", "currency"),
                    ReportColumn("1_30", "1-30 dias", "currency"),
                    ReportColumn("31_60", "31-60 dias", "currency"),
                    ReportColumn("61_90", "61-90 dias", "currency"),
                    ReportColumn("91_plus", "91+ dias", "currency"),
                    ReportColumn("no_vencido", "No vencido", "currency"),
                    ReportColumn("moneda", "Moneda"),
                    ReportColumn("facturas", "# facturas", "int"),
                ),
                rows=tuple(resumen_rows),
                currency_field="moneda_key",
            )
        ]
        if detalle_rows:
            tables.append(
                ReportTable(
                    key="aging_detalle_facturas",
                    title="Detalle de facturas pendientes",
                    columns=(
                        ReportColumn("cliente", "Cliente"),
                        ReportColumn("numero", "Factura"),
                        ReportColumn("fecha_emision", "Fecha emision", "datetime"),
                        ReportColumn("fecha_vencimiento", "Fecha vencimiento", "datetime"),
                        ReportColumn("dias_atraso", "Dias atraso", "int"),
                        ReportColumn("saldo", "Saldo", "currency"),
                        ReportColumn("bucket", "Bucket"),
                        ReportColumn("estado", "Estado"),
                        ReportColumn("moneda", "Moneda"),
                    ),
                    rows=tuple(detalle_rows),
                    currency_field="moneda_key",
                )
            )

        return ReportPayload(
            title="Cuentas por cobrar",
            generated_at=datetime.now(),
            message="" if resumen_rows else "No se encontraron facturas con saldo pendiente.",
            tables=tuple(tables),
            currencies=_currency_list(currencies),
        )


def _empty_aging_summary() -> dict[str, Any]:
    return {
        "cliente": "",
        "saldo_total": 0.0,
        "1_30": 0.0,
        "31_60": 0.0,
        "61_90": 0.0,
        "91_plus": 0.0,
        "no_vencido": 0.0,
        "moneda": "",
        "moneda_key": "",
        "facturas": 0,
    }


def _end_of_day(value: datetime) -> datetime:
    return value.replace(hour=23, minute=59, second=59, microsecond=999999)


def _parse_required_fecha_corte(value: Any, reader: ReportReaderBase) -> datetime:
    parsed = reader.parse_date(value)
    if parsed is None:
        raise ValueError("Debes indicar una fecha de corte valida.")
    return parsed


def _bucket_labels() -> dict[str, str]:
    return {
        "no_vencido": "No vencido",
        "1_30": "1-30 dias",
        "31_60": "31-60 dias",
        "61_90": "61-90 dias",
        "91_plus": "91+ dias",
    }


def _fecha_vencimiento(factura: Factura) -> datetime | None:
    if factura.fecha_emision is None:
        return None
    return factura.fecha_emision + timedelta(days=int(factura.dias_credito or 0))


def _aging_bucket(fecha_vencimiento: datetime | None, fecha_corte) -> tuple[int, str]:
    if fecha_vencimiento is None or fecha_vencimiento.date() >= fecha_corte:
        return 0, "no_vencido"
    dias_atraso = max((fecha_corte - fecha_vencimiento.date()).days, 0)
    if dias_atraso <= 30:
        return dias_atraso, "1_30"
    if dias_atraso <= 60:
        return dias_atraso, "31_60"
    if dias_atraso <= 90:
        return dias_atraso, "61_90"
    return dias_atraso, "91_plus"


def _sumar_pagos_hasta(factura: Factura, fecha_limite: datetime) -> float:
    total = 0.0
    for rf in factura.recibos_facturas:
        recibo = rf.recibo
        if not recibo or recibo.estado == EstadoRecibo.ANULADO:
            continue
        if recibo.fecha_emision and recibo.fecha_emision > fecha_limite:
            continue
        total += float(rf.monto_pagado or 0)
    return round(total, 2)


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
