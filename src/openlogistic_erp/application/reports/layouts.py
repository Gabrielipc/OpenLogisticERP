from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ReportKpi:
    key: str
    label: str


@dataclass(frozen=True)
class ReportLayout:
    report_key: str
    title: str
    subtitle: str
    kpis: tuple[ReportKpi, ...]
    sheet_names: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kpis", tuple(self.kpis))
        object.__setattr__(self, "sheet_names", MappingProxyType(dict(self.sheet_names)))


def build_default_report_layouts() -> dict[str, ReportLayout]:
    layouts = (
        ReportLayout(
            report_key="viajes_por_conductor",
            title="Viajes por conductor",
            subtitle="Resumen de viajes agrupados por conductor.",
            kpis=(
                ReportKpi("conductores_activos", "Conductores activos"),
                ReportKpi("viajes_totales", "Viajes totales"),
                ReportKpi("dias_ocupados", "Dias ocupados"),
                ReportKpi("promedio_dias_viaje", "Promedio dias/viaje"),
            ),
            sheet_names={
                "resumen": "Resumen",
                "detalle": "Detalle de viajes",
            },
        ),
        ReportLayout(
            report_key="cuentas_por_cobrar_aging",
            title="Cuentas por cobrar aging",
            subtitle="Saldos pendientes clasificados por antiguedad.",
            kpis=(
                ReportKpi("saldo_total", "Saldo total"),
                ReportKpi("porcentaje_vencido", "Porcentaje vencido"),
                ReportKpi("clientes_en_mora", "Clientes en mora"),
                ReportKpi("ticket_promedio", "Ticket promedio"),
            ),
            sheet_names={
                "resumen": "Resumen",
                "aging": "Aging de saldos",
            },
        ),
        ReportLayout(
            report_key="facturacion_por_cliente",
            title="Facturacion por cliente",
            subtitle="Facturacion emitida agrupada por cliente.",
            kpis=(
                ReportKpi("facturado", "Facturado"),
                ReportKpi("cobrado", "Cobrado"),
                ReportKpi("porcentaje_cobrado", "Porcentaje cobrado"),
                ReportKpi("saldo", "Saldo"),
            ),
            sheet_names={
                "resumen": "Resumen",
                "detalle": "Detalle de facturacion",
            },
        ),
        ReportLayout(
            report_key="estado_cuenta_cliente",
            title="Estado de cuenta de cliente",
            subtitle="Movimientos y saldos de un cliente.",
            kpis=(
                ReportKpi("total_facturado", "Total facturado"),
                ReportKpi("total_cobrado", "Total cobrado"),
                ReportKpi("saldo_pendiente", "Saldo pendiente"),
            ),
            sheet_names={
                "resumen": "Resumen",
                "movimientos": "Movimientos",
            },
        ),
    )
    return {layout.report_key: layout for layout in layouts}


def build_report_layout_registry() -> dict[str, ReportLayout]:
    return build_default_report_layouts()


def layout_for(report_key: str) -> ReportLayout | None:
    return build_default_report_layouts().get(report_key)
