"""Dashboard KPI services."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..infrastructure.persistence.modelo.workflow_orm import (
    Camion,
    Circuito,
    Conductor,
    EstadoCamion,
    EstadoCircuito,
    EstadoConductor,
    EstadoFactura,
    EstadoFacturacion,
    EstadoRecibo,
    EstadoViaje,
    Factura,
    Moneda,
    Recibo,
    ReciboFactura,
    Viaje,
    q2,
    _to_decimal,
)


class DashboardService:
    """Read-only KPI service for the dashboard."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def get_kpis(self) -> dict[str, int | dict[str, int]]:
        with self._session_factory() as session:
            active_trips = _scalar_count(
                session.query(func.count(Viaje.id)).filter(Viaje.estado == EstadoViaje.ENCURSO)
            )
            active_circuits = _scalar_count(
                session.query(func.count(Circuito.id)).filter(Circuito.estado == EstadoCircuito.ENPROGRESO)
            )
            trucks_in_trip = _scalar_count(
                session.query(func.count(func.distinct(Viaje.camion_id))).filter(Viaje.estado == EstadoViaje.ENCURSO)
            )
            active_trucks = _scalar_count(
                session.query(func.count(Camion.id)).filter(Camion.estado == EstadoCamion.ACTIVO)
            )
            overdue_invoices = _scalar_count(
                session.query(func.count(Factura.id)).filter(Factura.estado == EstadoFactura.ATRASADA)
            )
            pending_billing = _scalar_count(
                session.query(func.count(Viaje.id)).filter(
                    Viaje.estado == EstadoViaje.FINALIZADO,
                    Viaje._estado_facturacion == EstadoFacturacion.REGISTRADO,
                )
            )
            truck_status_counts = _enum_counts(
                session.query(Camion.estado, func.count(Camion.id)).group_by(Camion.estado).all()
            )
            driver_status_counts = _enum_counts(
                session.query(Conductor.estado, func.count(Conductor.id)).group_by(Conductor.estado).all()
            )
            open_debt_clients = _count_clients_with_open_debt(
                session.query(Factura)
                .options(joinedload(Factura.recibos_facturas).joinedload(ReciboFactura.recibo))
                .filter(Factura.estado != EstadoFactura.ANULADA)
                .all()
            )

        fleet_status = {
            "camiones_disponibles": active_trucks,
            "camiones_en_viaje": trucks_in_trip,
            "camiones_mantenimiento": truck_status_counts.get(EstadoCamion.MANTENIMIENTO, 0),
            "camiones_baja": truck_status_counts.get(EstadoCamion.BAJA, 0),
            "camiones_vendidos": truck_status_counts.get(EstadoCamion.VENDIDO, 0),
            "camiones_agregados": truck_status_counts.get(EstadoCamion.AGREGADO, 0),
        }
        driver_status = {
            "conductores_disponibles": driver_status_counts.get(EstadoConductor.DISPONIBLE, 0),
            "conductores_en_viaje": driver_status_counts.get(EstadoConductor.VIAJE, 0),
            "conductores_instrucciones": driver_status_counts.get(EstadoConductor.INSTRUCCIONES, 0),
            "conductores_baja": driver_status_counts.get(EstadoConductor.BAJA, 0),
            "conductores_agregados": driver_status_counts.get(EstadoConductor.AGREGADO, 0),
        }
        summary = {
            "circuitos_en_progreso": active_circuits,
            "viajes_en_progreso": active_trips,
        }
        finance = {
            "facturacion_pendiente": pending_billing,
            "cuentas_por_cobrar_clientes": open_debt_clients,
            "facturas_atrasadas": overdue_invoices,
        }

        return {
            "viajes_activos": active_trips,
            "circuitos_en_progreso": active_circuits,
            "camiones_disponibles": fleet_status["camiones_disponibles"],
            "camiones_en_viaje": trucks_in_trip,
            "cuentas_por_cobrar_clientes": open_debt_clients,
            "facturacion_pendiente": pending_billing,
            "facturas_atrasadas": overdue_invoices,
            "fleet_status": fleet_status,
            "driver_status": driver_status,
            "summary": summary,
            "finance": finance,
        }

    def get_client_debt_rows(self) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            facturas = (
                session.query(Factura)
                .options(
                    joinedload(Factura.cliente),
                    joinedload(Factura.recibos_facturas).joinedload(ReciboFactura.recibo),
                )
                .filter(Factura.estado != EstadoFactura.ANULADA)
                .all()
            )
        grouped: dict[int, dict[str, Any]] = {}
        for factura in facturas:
            saldo = _invoice_open_balance(factura)
            if saldo <= Decimal("0"):
                continue
            cliente_id = int(factura.cliente_id)
            row = grouped.setdefault(
                cliente_id,
                {
                    "cliente_id": cliente_id,
                    "cliente_label": str(getattr(factura.cliente, "nombre", "") or f"Cliente #{cliente_id}"),
                    "saldo_total": Decimal("0"),
                    "saldos_por_moneda": {},
                    "facturas": [],
                },
            )
            moneda = _currency_value(getattr(factura, "moneda", None))
            row["saldo_total"] += saldo
            row["saldos_por_moneda"][moneda] = row["saldos_por_moneda"].get(moneda, Decimal("0")) + saldo
            row["facturas"].append(
                {
                    "id": int(factura.id),
                    "numero_factura": str(factura.numero_factura or f"Factura #{factura.id}"),
                    "estado": str(getattr(factura.estado, "value", factura.estado)),
                    "moneda": moneda,
                    "saldo": f"{saldo:.2f}",
                    "saldo_display": _format_money(saldo, moneda),
                }
            )
        return [
            {
                **row,
                "saldo_total": f"{row['saldo_total']:.2f}",
                "saldo_total_display": _format_currency_totals(row["saldos_por_moneda"]),
                "saldos_por_moneda": [
                    {
                        "moneda": moneda,
                        "saldo": f"{saldo:.2f}",
                        "saldo_display": _format_money(saldo, moneda),
                    }
                    for moneda, saldo in _ordered_currency_totals(row["saldos_por_moneda"])
                ],
            }
            for row in grouped.values()
        ]

    def get_billing_timeline(
        self,
        *,
        months: int = 12,
        reference_date: datetime | None = None,
        include_receipts: bool = True,
    ) -> list[dict[str, Any]]:
        month_count = max(1, int(months or 12))
        anchor = reference_date or datetime.now()
        start_month = _add_months(_month_start(anchor), -(month_count - 1))
        end_month = _add_months(_month_start(anchor), 1)
        month_dates = [_add_months(start_month, index) for index in range(month_count)]
        month_keys = [_month_key(month_date) for month_date in month_dates]
        months_by_key = dict(zip(month_keys, month_dates, strict=True))
        totals: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

        with self._session_factory() as session:
            invoices = (
                session.query(Factura)
                .filter(Factura.fecha_emision >= start_month)
                .filter(Factura.fecha_emision < end_month)
                .filter(Factura.estado != EstadoFactura.ANULADA)
                .all()
            )
            receipt_allocations = (
                session.query(ReciboFactura)
                .options(joinedload(ReciboFactura.recibo))
                .join(Recibo, ReciboFactura.recibo_id == Recibo.id)
                .filter(Recibo.fecha_emision >= start_month)
                .filter(Recibo.fecha_emision < end_month)
                .filter(Recibo.estado != EstadoRecibo.ANULADO)
                .all()
                if include_receipts
                else []
            )

        active_currencies: set[str] = set()
        for factura in invoices:
            currency = _currency_value(getattr(factura, "moneda", None))
            period_key = _month_key(factura.fecha_emision)
            bucket = _billing_bucket(totals, currency, period_key)
            bucket["facturado"] += _to_decimal(getattr(factura, "_total", None)) or Decimal("0")
            bucket["facturas_count"] += 1
            active_currencies.add(currency)

        for allocation in receipt_allocations:
            recibo = getattr(allocation, "recibo", None)
            if recibo is None:
                continue
            currency = _currency_value(getattr(recibo, "moneda", None))
            period_key = _month_key(recibo.fecha_emision)
            bucket = _billing_bucket(totals, currency, period_key)
            bucket["pagado"] += _to_decimal(getattr(allocation, "monto_pagado", None)) or Decimal("0")
            bucket["recibos_count"] += 1
            active_currencies.add(currency)

        rows: list[dict[str, Any]] = []
        for currency in _ordered_currency_keys(active_currencies):
            currency_buckets = totals.get(currency, {})
            currency_max = Decimal("0")
            for period_key in month_keys:
                bucket = currency_buckets.get(period_key, _empty_billing_bucket())
                currency_max = max(currency_max, bucket["facturado"], bucket["pagado"])

            for period_key in month_keys:
                bucket = currency_buckets.get(period_key, _empty_billing_bucket())
                facturado = q2(bucket["facturado"])
                pagado = q2(bucket["pagado"])
                rows.append(
                    {
                        "period_key": period_key,
                        "period_label": _month_label(months_by_key[period_key]),
                        "moneda": currency,
                        "facturado": f"{facturado:.2f}",
                        "pagado": f"{pagado:.2f}",
                        "facturado_display": _format_money(facturado, currency),
                        "pagado_display": _format_money(pagado, currency),
                        "facturas_count": int(bucket["facturas_count"]),
                        "recibos_count": int(bucket["recibos_count"]),
                        "max_value": f"{q2(currency_max):.2f}",
                    }
                )
        return rows


def _scalar_count(query: Any) -> int:
    return int(query.scalar() or 0)


def _enum_counts(rows: list[tuple[Any, Any]]) -> dict[Any, int]:
    return {status: int(count or 0) for status, count in rows if status is not None}


def _count_clients_with_open_debt(facturas: list[Factura]) -> int:
    client_ids: set[int] = set()
    for factura in facturas:
        saldo = _invoice_open_balance(factura)
        if saldo > Decimal("0"):
            client_id = getattr(factura, "cliente_id", None)
            if client_id is not None:
                client_ids.add(int(client_id))
    return len(client_ids)


def _invoice_open_balance(factura: Factura) -> Decimal:
    total = _to_decimal(getattr(factura, "_total", None)) or Decimal("0")
    paid = Decimal("0")
    for relation in getattr(factura, "recibos_facturas", []) or []:
        recibo = getattr(relation, "recibo", None)
        if recibo is not None and getattr(recibo, "estado", None) == EstadoRecibo.ANULADO:
            continue
        paid += _to_decimal(getattr(relation, "monto_pagado", None)) or Decimal("0")
    saldo = total - paid
    return saldo if saldo > Decimal("0") else Decimal("0")


def _currency_value(currency: Any) -> str:
    return str(getattr(currency, "value", currency) or Moneda.NIO.value).strip().upper()


def _currency_symbol(currency: Any) -> str:
    code = _currency_value(currency)
    if code == Moneda.USD.value:
        return "$"
    if code == Moneda.NIO.value:
        return "C$"
    return code or "$"


def _format_money(amount: Decimal, currency: Any) -> str:
    return f"{_currency_symbol(currency)} {amount:,.2f}"


def _format_currency_totals(totals_by_currency: dict[str, Decimal]) -> str:
    return " / ".join(_format_money(saldo, moneda) for moneda, saldo in _ordered_currency_totals(totals_by_currency))


def _ordered_currency_totals(totals_by_currency: dict[str, Decimal]) -> list[tuple[str, Decimal]]:
    preferred_order = {Moneda.USD.value: 0, Moneda.NIO.value: 1}
    return sorted(
        totals_by_currency.items(),
        key=lambda item: (preferred_order.get(item[0], 99), item[0]),
    )


def _month_start(value: datetime) -> datetime:
    return datetime(int(value.year), int(value.month), 1)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + int(months)
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1)


def _month_key(value: datetime) -> str:
    return f"{int(value.year):04d}-{int(value.month):02d}"


def _month_label(value: datetime) -> str:
    labels = (
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    )
    return f"{labels[int(value.month) - 1]} {int(value.year)}"


def _empty_billing_bucket() -> dict[str, Any]:
    return {
        "facturado": Decimal("0"),
        "pagado": Decimal("0"),
        "facturas_count": 0,
        "recibos_count": 0,
    }


def _billing_bucket(
    totals: dict[str, dict[str, dict[str, Any]]],
    currency: str,
    period_key: str,
) -> dict[str, Any]:
    currency_buckets = totals.setdefault(currency, {})
    if period_key not in currency_buckets:
        currency_buckets[period_key] = _empty_billing_bucket()
    return currency_buckets[period_key]


def _ordered_currency_keys(currencies: set[str]) -> list[str]:
    preferred_order = {Moneda.USD.value: 0, Moneda.NIO.value: 1}
    return sorted(currencies, key=lambda currency: (preferred_order.get(currency, 99), currency))
