from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    summary: str
    filters: tuple[Mapping[str, Any], ...]
    layout_key: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "filters",
            tuple(MappingProxyType(dict(filter_definition)) for filter_definition in self.filters),
        )

    def to_map(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "summary": self.summary,
            "filters": [dict(filter_definition) for filter_definition in self.filters],
            "layout_key": self.layout_key,
        }


def build_default_report_definitions() -> dict[str, ReportDefinition]:
    definitions = (
        ReportDefinition(
            key="viajes_por_conductor",
            title="Viajes por conductor",
            summary="Resumen de viajes agrupados por conductor.",
            layout_key="viajes_por_conductor",
            filters=(
                _filter("rango_fechas", "Rango de fechas", "date_range", required=True),
                _filter("conductor_id", "Conductor", "select", option_source="conductores"),
                _filter("cliente_id", "Cliente", "select", option_source="clientes"),
                _filter("estado_viaje", "Estado", "select", option_source="estado_viaje"),
                _filter("incluir_detalle", "Incluir detalle", "checkbox", default=True),
            ),
        ),
        ReportDefinition(
            key="cuentas_por_cobrar_aging",
            title="Cuentas por cobrar aging",
            summary="Saldos pendientes clasificados por antiguedad.",
            layout_key="cuentas_por_cobrar_aging",
            filters=(
                _filter("fecha_corte", "Fecha de corte", "date", required=True),
                _filter("cliente_id", "Cliente", "select", option_source="clientes"),
                _filter(
                    "bucket_scheme",
                    "Esquema de periodos",
                    "select",
                    option_source="bucket_scheme",
                    default="30_60_90",
                ),
            ),
        ),
        ReportDefinition(
            key="facturacion_por_cliente",
            title="Facturacion por cliente",
            summary="Facturacion emitida agrupada por cliente.",
            layout_key="facturacion_por_cliente",
            filters=(
                _filter("rango_fechas", "Rango de fechas", "date_range", required=True),
                _filter("cliente_id", "Cliente", "select", option_source="clientes"),
                _filter("estado_factura", "Estado de factura", "select", option_source="estado_factura"),
                _filter("incluir_detalle", "Incluir detalle", "checkbox", default=True),
            ),
        ),
        ReportDefinition(
            key="estado_cuenta_cliente",
            title="Estado de cuenta de cliente",
            summary="Movimientos y saldos de un cliente.",
            layout_key="estado_cuenta_cliente",
            filters=(
                _filter("cliente_id", "Cliente", "select", required=True, option_source="clientes"),
                _filter("rango_fechas", "Rango de fechas", "date_range"),
                _filter("estado_factura", "Estado de factura", "select", option_source="estado_factura"),
            ),
        ),
    )
    return {definition.key: definition for definition in definitions}


def _filter(
    key: str,
    label: str,
    filter_type: str,
    *,
    required: bool = False,
    default: Any = None,
    option_source: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": filter_type,
        "required": required,
        "default": default,
        "option_source": option_source,
    }
