"""SQLAlchemy reader for facturacion por cliente."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
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


class FacturacionPorClienteReportReader(ReportReaderBase):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def generate(self, params: dict[str, Any]) -> ReportPayload:
        start_dt, end_dt = self.parse_date_range(params.get("rango_fechas"))
        if start_dt is None or end_dt is None:
            raise ValueError("Debes indicar un rango de fechas valido.")
        cliente_id = self.parse_int(params.get("cliente_id"))
        estado = _parse_estado_factura(params.get("estado_factura"))
        incluir_detalle = bool(params.get("incluir_detalle"))

        with self._session_factory() as session:
            query = (
                session.query(Factura)
                .options(
                    joinedload(Factura.cliente),
                    joinedload(Factura.recibos_facturas).joinedload(ReciboFactura.recibo),
                )
                .filter(Factura.fecha_emision >= start_dt)
                .filter(Factura.fecha_emision <= end_dt)
            )
            if cliente_id is not None:
                query = query.filter(Factura.cliente_id == cliente_id)
            if estado is not None:
                query = query.filter(Factura.estado == estado)
            facturas = query.all()

        resumen = defaultdict(_empty_facturacion_summary)
        detalle_rows: list[dict[str, Any]] = []
        currencies: set[Moneda] = set()

        for factura in facturas:
            cliente = factura.cliente
            moneda = _to_moneda(getattr(factura, "moneda", None))
            if cliente is None or moneda is None:
                continue
            currencies.add(moneda)
            total = float(factura._total or 0)
            pagado = _sumar_pagos(factura)
            saldo = round(max(total - pagado, 0.0), 2)

            row = resumen[(int(cliente.id), moneda)]
            row["cliente"] = cliente.nombre
            row["moneda"] = moneda.value
            row["moneda_key"] = moneda.name
            row["facturas"] += 1
            row["total_facturado"] = round(row["total_facturado"] + total, 2)
            row["total_pagado"] = round(row["total_pagado"] + pagado, 2)
            row["saldo"] = round(row["saldo"] + saldo, 2)
            if factura.fecha_emision and (row["ultima_factura"] is None or factura.fecha_emision > row["ultima_factura"]):
                row["ultima_factura"] = factura.fecha_emision

            detalle_rows.append(
                {
                    "cliente": cliente.nombre,
                    "numero": factura.numero_factura,
                    "fecha_emision": factura.fecha_emision,
                    "total": round(total, 2),
                    "pagado": round(pagado, 2),
                    "saldo": saldo,
                    "estado": factura.estado.value if factura.estado else "",
                    "moneda": moneda.value,
                    "moneda_key": moneda.name,
                }
            )

        resumen_rows = list(resumen.values())
        resumen_rows.sort(key=lambda row: (str(row["cliente"]).lower(), str(row["moneda_key"])))

        tables = [
            ReportTable(
                key="facturacion_cliente",
                title="Facturacion por cliente",
                columns=(
                    ReportColumn("cliente", "Cliente"),
                    ReportColumn("total_facturado", "Total facturado", "currency"),
                    ReportColumn("total_pagado", "Total cobrado", "currency"),
                    ReportColumn("saldo", "Saldo", "currency"),
                    ReportColumn("moneda", "Moneda"),
                    ReportColumn("facturas", "# facturas", "int"),
                    ReportColumn("ultima_factura", "Ultima factura", "datetime"),
                ),
                rows=tuple(resumen_rows),
                currency_field="moneda_key",
            )
        ]

        if incluir_detalle and detalle_rows:
            detalle_rows.sort(key=lambda row: (str(row["cliente"]).lower(), row["fecha_emision"] or start_dt))
            tables.append(
                ReportTable(
                    key="facturacion_detalle_facturas",
                    title="Detalle de facturas",
                    columns=(
                        ReportColumn("cliente", "Cliente"),
                        ReportColumn("numero", "Factura"),
                        ReportColumn("fecha_emision", "Fecha emision", "datetime"),
                        ReportColumn("total", "Total", "currency"),
                        ReportColumn("pagado", "Pagado", "currency"),
                        ReportColumn("saldo", "Saldo", "currency"),
                        ReportColumn("estado", "Estado"),
                        ReportColumn("moneda", "Moneda"),
                    ),
                    rows=tuple(detalle_rows),
                    currency_field="moneda_key",
                )
            )

        return ReportPayload(
            title="Facturacion por cliente",
            generated_at=datetime.now(),
            message="" if resumen_rows else "No se encontraron facturas en el rango indicado.",
            tables=tuple(tables),
            currencies=_currency_list(currencies),
        )


def _empty_facturacion_summary() -> dict[str, Any]:
    return {
        "cliente": "",
        "total_facturado": 0.0,
        "total_pagado": 0.0,
        "saldo": 0.0,
        "moneda": "",
        "moneda_key": "",
        "facturas": 0,
        "ultima_factura": None,
    }


def _parse_estado_factura(value: Any) -> EstadoFactura | None:
    if value in (None, ""):
        return None
    if isinstance(value, EstadoFactura):
        return value
    return EstadoFactura(str(value))


def _sumar_pagos(factura: Factura) -> float:
    total = 0.0
    for rf in factura.recibos_facturas:
        recibo = rf.recibo
        if not recibo or recibo.estado == EstadoRecibo.ANULADO:
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
