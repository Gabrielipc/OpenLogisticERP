"""QML-facing dashboard view model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..application.dashboard import DashboardService
from .qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from .viewmodels.base_view_model import BaseViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@dataclass(frozen=True)
class DashboardMetricDefinition:
    key: str
    title: str
    caption: str
    monogram: str
    accent_tone: str
    module_id: str
    icon_source: str = ""
    target: str = "list"
    filters: tuple[dict[str, Any], ...] = ()
    subpage: str = ""
    subpage_context: tuple[tuple[str, Any], ...] = ()
    permission_requirements: tuple[tuple[str, str], ...] = ()


METRIC_DEFINITIONS: tuple[DashboardMetricDefinition, ...] = (
    DashboardMetricDefinition(
        key="viajes_activos",
        title="Operacion",
        caption="Viajes actualmente en curso",
        monogram="VA",
        icon_source="qrc:/actions/general/speed_truck",
        accent_tone="success",
        module_id="viaje",

    ),
    DashboardMetricDefinition(
        key="circuitos_en_progreso",
        title="Circuitos",
        caption="Circuitos operativos abiertos",
        monogram="CA",
        icon_source="qrc:/actions/general/pin_road",
        accent_tone="primary",
        module_id="circuito",
    ),
    DashboardMetricDefinition(
        key="camiones_disponibles",
        title="Flota",
        caption="Camiones activos sin viaje en curso",
        monogram="CL",
        icon_source="qrc:/icons/modules/truck",
        accent_tone="success",
        module_id="camion",
    ),
    DashboardMetricDefinition(
        key="camiones_en_viaje",
        title="Flota",
        caption="Camiones asignados a viajes activos",
        monogram="CV",
        icon_source="qrc:/actions/general/speed_truck",
        accent_tone="warning",
        module_id="camion",
    ),
    DashboardMetricDefinition(
        key="cuentas_por_cobrar_clientes",
        title="Cobros",
        caption="Clientes con facturas pendientes de cobro",
        icon_source="qrc:/actions/general/person_alert",
        monogram="CC",
        accent_tone="warning",
        module_id="cliente",
        permission_requirements=(("cliente", "read"), ("factura", "read"), ("recibo", "read")),
    ),
    DashboardMetricDefinition(
        key="facturacion_pendiente",
        title="Facturacion",
        caption="Viajes finalizados pendientes de factura",
        monogram="PF",
        icon_source="qrc:/icons/modules/receipt_long",
        accent_tone="warning",
        module_id="viaje",
        permission_requirements=(("factura", "read"), ("viaje", "create")),
    ),
    DashboardMetricDefinition(
        key="facturas_atrasadas",
        title="Cobros",
        caption="Facturas vencidas pendientes",
        monogram="FA",
        icon_source="qrc:/actions/general/receipt_off",
        accent_tone="danger",
        module_id="factura",
    ),
)

FLEET_STATUS_DEFINITIONS: tuple[DashboardMetricDefinition, ...] = (
    DashboardMetricDefinition("camiones_disponibles", "Disponibles", "", "CD", "success", "camion"),
    DashboardMetricDefinition("camiones_en_viaje", "En viaje", "", "CV", "warning", "camion"),
    DashboardMetricDefinition("camiones_mantenimiento", "Mantenimiento", "", "CM", "warning", "camion"),
    DashboardMetricDefinition("camiones_baja", "De baja", "", "CB", "danger", "camion"),
    DashboardMetricDefinition("camiones_vendidos", "Vendidos", "", "CV", "soft", "camion"),
    DashboardMetricDefinition("camiones_agregados", "Agregados", "", "CA", "soft", "camion"),
)

DRIVER_STATUS_DEFINITIONS: tuple[DashboardMetricDefinition, ...] = (
    DashboardMetricDefinition("conductores_disponibles", "Disponibles", "", "DD", "success", "conductor"),
    DashboardMetricDefinition("conductores_en_viaje", "En viaje", "", "DV", "warning", "conductor"),
    DashboardMetricDefinition("conductores_instrucciones", "Esperando instrucciones", "", "DI", "primary", "conductor"),
    DashboardMetricDefinition("conductores_baja", "De baja", "", "DB", "danger", "conductor"),
    DashboardMetricDefinition("conductores_agregados", "Agregados", "", "DA", "soft", "conductor"),
)

SUMMARY_DEFINITIONS: tuple[DashboardMetricDefinition, ...] = (
    DashboardMetricDefinition(
        "circuitos_en_progreso",
        "Circuitos abiertos",
        "",
        "CI",
        "primary",
        "circuito",
        icon_source="qrc:/actions/general/pin_road",
        target="filtered_list",
        filters=({"field": "estado", "operator": "eq", "value": "ENPROGRESO"},),
    ),
    DashboardMetricDefinition(
        "viajes_en_progreso",
        "Viajes en progreso",
        "",
        "VP",
        "warning",
        "viaje",
        icon_source="qrc:/actions/general/speed_truck",
        target="filtered_list",
        filters=({"field": "estado", "operator": "eq", "value": "ENCURSO"},),
    ),
)

FINANCE_DEFINITIONS: tuple[DashboardMetricDefinition, ...] = (
    DashboardMetricDefinition(
        "facturacion_pendiente",
        "Viajes sin facturar",
        "",
        "VF",
        "warning",
        "viaje",
        target="subpage",
        icon_source="qrc:/icons/modules/receipt_long",
        subpage="unbilled_trips",
        permission_requirements=(("factura", "read"), ("viaje", "create")),
    ),
    DashboardMetricDefinition(
        "cuentas_por_cobrar_clientes",
        "Cuentas por cobrar por cliente",
        "",
        "CC",
        "warning",
        "cliente",
        icon_source="qrc:/actions/general/person_alert",
        target="subpage",
        subpage="client_debt",
        permission_requirements=(("cliente", "read"), ("factura", "read"), ("recibo", "read")),
    ),
    DashboardMetricDefinition(
        "facturas_atrasadas",
        "Facturas atrasadas",
        "",
        "FA",
        "danger",
        "factura",
        target="filtered_list",
        icon_source="qrc:/actions/general/receipt_off",
        filters=({"field": "estado", "operator": "eq", "value": "Atrasada"},),
    ),
)

FLEET_STATUS_ROUTE_VALUES = {
    "camiones_disponibles": "ACTIVO",
    "camiones_en_viaje": "ENVIAJE",
    "camiones_mantenimiento": "MANTENIMIENTO",
    "camiones_baja": "BAJA",
    "camiones_vendidos": "VENDIDO",
    "camiones_agregados": "AGREGADO",
}

DRIVER_STATUS_ROUTE_VALUES = {
    "conductores_disponibles": "DISPONIBLE",
    "conductores_en_viaje": "VIAJE",
    "conductores_instrucciones": "INSTRUCCIONES",
    "conductores_baja": "BAJA",
    "conductores_agregados": "AGREGADO",
}


@QmlNamedElement("DashboardViewModel")
@QmlUncreatable("DashboardViewModel instances are created in Python and injected into QML.")
class DashboardViewModel(BaseViewModel):
    metricsChanged = Signal()
    errorMessageChanged = Signal(str)
    clientDebtChanged = Signal()
    statusVisibilityChanged = Signal()
    billingTimelineChanged = Signal()
    billingTimelineCurrencyChanged = Signal(str)
    billingTimelineReceiptsVisibilityChanged = Signal(bool)

    def __init__(self, service: DashboardService, *, authorization_service: Any | None = None) -> None:
        super().__init__()
        self._service = service
        self._authorization = authorization_service
        self._last_kpis: dict[str, Any] = {}
        self._hidden_status_metrics: dict[str, set[str]] = {
            "fleet": set(),
            "driver": set(),
        }
        self._metrics = self._empty_metrics()
        self._fleet_status_metrics = self._empty_status_metrics(FLEET_STATUS_DEFINITIONS)
        self._driver_status_metrics = self._empty_status_metrics(DRIVER_STATUS_DEFINITIONS)
        self._summary_metrics = self._empty_tile_metrics(SUMMARY_DEFINITIONS)
        self._finance_metrics = self._empty_tile_metrics(FINANCE_DEFINITIONS)
        self._error_message = ""
        self._client_debt_rows: list[dict[str, Any]] = []
        self._billing_timeline_all_rows: list[dict[str, Any]] = []
        self._billing_timeline_rows: list[dict[str, Any]] = []
        self._billing_timeline_currencies: list[dict[str, str]] = [{"key": "", "label": "Todas"}]
        self._selected_billing_timeline_currency = ""
        self._show_billing_timeline_receipts = False

    @Property("QVariantList", notify=metricsChanged)
    def metrics(self) -> list[dict[str, Any]]:
        return [dict(metric) for metric in self._metrics]

    @Property("QVariantList", notify=metricsChanged)
    def fleetStatusMetrics(self) -> list[dict[str, Any]]:
        return [dict(metric) for metric in self._fleet_status_metrics]

    @Property("QVariantList", notify=metricsChanged)
    def driverStatusMetrics(self) -> list[dict[str, Any]]:
        return [dict(metric) for metric in self._driver_status_metrics]

    @Property("QVariantList", notify=statusVisibilityChanged)
    def fleetStatusVisibilityOptions(self) -> list[dict[str, Any]]:
        return self._status_visibility_options("fleet", FLEET_STATUS_DEFINITIONS)

    @Property("QVariantList", notify=statusVisibilityChanged)
    def driverStatusVisibilityOptions(self) -> list[dict[str, Any]]:
        return self._status_visibility_options("driver", DRIVER_STATUS_DEFINITIONS)

    @Property("QVariantList", notify=metricsChanged)
    def summaryMetrics(self) -> list[dict[str, Any]]:
        return [dict(metric) for metric in self._summary_metrics]

    @Property("QVariantList", notify=metricsChanged)
    def financeMetrics(self) -> list[dict[str, Any]]:
        return [dict(metric) for metric in self._finance_metrics]

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property("QVariantList", notify=clientDebtChanged)
    def clientDebtRows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._client_debt_rows]

    @Property("QVariantList", notify=billingTimelineChanged)
    def billingTimelineRows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._billing_timeline_rows]

    @Property("QVariantList", notify=billingTimelineChanged)
    def billingTimelineCurrencies(self) -> list[dict[str, str]]:
        return [dict(option) for option in self._billing_timeline_currencies]

    @Property(str, notify=billingTimelineCurrencyChanged)
    def selectedBillingTimelineCurrency(self) -> str:
        return self._selected_billing_timeline_currency

    @Property(bool, notify=billingTimelineReceiptsVisibilityChanged)
    def showBillingTimelineReceipts(self) -> bool:
        return self._show_billing_timeline_receipts

    @Property(bool, notify=billingTimelineChanged)
    def canViewBillingTimeline(self) -> bool:
        return self._can_view_billing_timeline()

    @Property(bool, notify=billingTimelineChanged)
    def canCompareBillingTimelineReceipts(self) -> bool:
        return self._can_compare_billing_timeline_receipts()

    @Slot(result=bool)
    def refresh(self) -> bool:
        self.is_busy = True
        try:
            kpis = self._service.get_kpis()
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self.is_busy = False

        self._last_kpis = dict(kpis)
        self._metrics = self._metrics_from_kpis(kpis)
        self._fleet_status_metrics = self._status_metrics_from_kpis(
            kpis.get("fleet_status", {}),
            FLEET_STATUS_DEFINITIONS,
            group="fleet",
        )
        self._driver_status_metrics = self._status_metrics_from_kpis(
            kpis.get("driver_status", {}),
            DRIVER_STATUS_DEFINITIONS,
            group="driver",
        )
        self._summary_metrics = self._tile_metrics_from_kpis(kpis.get("summary", {}), SUMMARY_DEFINITIONS)
        self._finance_metrics = self._tile_metrics_from_kpis(kpis.get("finance", {}), FINANCE_DEFINITIONS)
        self.metricsChanged.emit()
        try:
            if not self._can_view_billing_timeline():
                self._set_billing_timeline_rows([])
            else:
                can_compare_receipts = self._can_compare_billing_timeline_receipts()
                if not can_compare_receipts and self._show_billing_timeline_receipts:
                    self._show_billing_timeline_receipts = False
                    self.billingTimelineReceiptsVisibilityChanged.emit(False)
                timeline_loader = getattr(self._service, "get_billing_timeline", None)
                self._set_billing_timeline_rows(
                    timeline_loader(include_receipts=can_compare_receipts)
                    if callable(timeline_loader)
                    else []
                )
        except Exception as exc:
            self._set_billing_timeline_rows([])
            self._set_error_message(str(exc))
            return False
        self._set_error_message("")
        return True

    @Slot(result=bool)
    def load_client_debt(self) -> bool:
        try:
            self._client_debt_rows = self._service.get_client_debt_rows()
            self.clientDebtChanged.emit()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

    @Slot(str, str, bool, result=bool)
    def setStatusMetricVisible(self, group: str, key: str, visible: bool) -> bool:
        normalized_group = self._normalize_status_group(group)
        if normalized_group == "":
            return False
        normalized_key = str(key or "")
        valid_keys = self._status_definition_keys(normalized_group)
        if normalized_key not in valid_keys:
            return False

        hidden_keys = self._hidden_status_metrics[normalized_group]
        if visible:
            hidden_keys.discard(normalized_key)
        else:
            hidden_keys.add(normalized_key)
        self._rebuild_status_metrics()
        self.metricsChanged.emit()
        self.statusVisibilityChanged.emit()
        return True

    @Slot(str, result=bool)
    def resetStatusMetricVisibility(self, group: str) -> bool:
        normalized_group = self._normalize_status_group(group)
        if normalized_group == "":
            return False
        self._hidden_status_metrics[normalized_group].clear()
        self._rebuild_status_metrics()
        self.metricsChanged.emit()
        self.statusVisibilityChanged.emit()
        return True

    @Slot(str, result=bool)
    def selectBillingTimelineCurrency(self, currency_key: str) -> bool:
        normalized = str(currency_key or "").strip().upper()
        valid_keys = {str(option["key"]) for option in self._billing_timeline_currencies}
        if normalized not in valid_keys:
            return False
        if self._selected_billing_timeline_currency == normalized:
            return True
        self._selected_billing_timeline_currency = normalized
        self._refresh_visible_billing_timeline_rows()
        self.billingTimelineCurrencyChanged.emit(normalized)
        self.billingTimelineChanged.emit()
        return True

    @Slot(bool, result=bool)
    def setBillingTimelineReceiptsVisible(self, visible: bool) -> bool:
        normalized = bool(visible)
        if normalized and not self._can_compare_billing_timeline_receipts():
            if self._show_billing_timeline_receipts:
                self._show_billing_timeline_receipts = False
                self.billingTimelineReceiptsVisibilityChanged.emit(False)
                self.billingTimelineChanged.emit()
            return False
        if self._show_billing_timeline_receipts == normalized:
            return True
        self._show_billing_timeline_receipts = normalized
        self.billingTimelineReceiptsVisibilityChanged.emit(normalized)
        self.billingTimelineChanged.emit()
        return True

    def _metrics_from_kpis(self, kpis: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {
                "key": definition.key,
                "title": definition.title,
                "value": str(int(kpis.get(definition.key, 0) or 0)),
                "caption": definition.caption,
                "monogram": definition.monogram,
                "iconSource": self._icon_source_for_definition(definition),
                "accentTone": definition.accent_tone,
                "moduleId": definition.module_id,
                "target": definition.target,
            }
            for definition in METRIC_DEFINITIONS
            if self._can_show_metric(definition)
        ]

    def _empty_metrics(self) -> list[dict[str, Any]]:
        return self._metrics_from_kpis({})

    def _status_metrics_from_kpis(
        self,
        kpis: Any,
        definitions: tuple[DashboardMetricDefinition, ...],
        *,
        group: str = "",
    ) -> list[dict[str, Any]]:
        source = kpis if isinstance(kpis, dict) else {}
        status_values = FLEET_STATUS_ROUTE_VALUES if definitions is FLEET_STATUS_DEFINITIONS else DRIVER_STATUS_ROUTE_VALUES
        hidden_keys = self._hidden_status_metrics.get(group, set())
        return [
            {
                "key": definition.key,
                "title": definition.title,
                "value": int(source.get(definition.key, 0) or 0),
                "caption": definition.caption,
                "accentTone": definition.accent_tone,
                "monogram": definition.monogram,
                "iconSource": self._icon_source_for_definition(definition),
                "moduleId": definition.module_id,
                "target": "filtered_list",
                "filters": [
                    {
                        "field": "estado",
                        "operator": "eq",
                        "value": status_values.get(definition.key, ""),
                    }
                ],
            }
            for definition in definitions
            if definition.key not in hidden_keys and self._can_show_metric(definition)
        ]

    def _tile_metrics_from_kpis(
        self,
        kpis: Any,
        definitions: tuple[DashboardMetricDefinition, ...],
    ) -> list[dict[str, Any]]:
        source = kpis if isinstance(kpis, dict) else {}
        return [
            {
                "key": definition.key,
                "title": definition.title,
                "value": str(int(source.get(definition.key, 0) or 0)),
                "caption": definition.caption,
                "accentTone": definition.accent_tone,
                "monogram": definition.monogram,
                "iconSource": self._icon_source_for_definition(definition),
                "moduleId": definition.module_id,
                "target": definition.target,
                **({"filters": [dict(item) for item in definition.filters]} if definition.filters else {}),
                **({"subpage": definition.subpage} if definition.subpage else {}),
                **({"subpageContext": dict(definition.subpage_context)} if definition.subpage_context else {}),
            }
            for definition in definitions
            if self._can_show_metric(definition)
        ]

    def _empty_status_metrics(self, definitions: tuple[DashboardMetricDefinition, ...]) -> list[dict[str, Any]]:
        group = "fleet" if definitions is FLEET_STATUS_DEFINITIONS else "driver"
        return self._status_metrics_from_kpis({}, definitions, group=group)

    def _empty_tile_metrics(self, definitions: tuple[DashboardMetricDefinition, ...]) -> list[dict[str, Any]]:
        return self._tile_metrics_from_kpis({}, definitions)

    @staticmethod
    def _icon_source_for_definition(definition: DashboardMetricDefinition) -> str:
        return definition.icon_source

    def _can_show_metric(self, definition: DashboardMetricDefinition) -> bool:
        if self._authorization is None:
            return True
        requirements = definition.permission_requirements or ((definition.module_id, "read"),)
        return all(self._authorization.can(resource, action) for resource, action in requirements)

    def _can_view_billing_timeline(self) -> bool:
        return self._authorization is None or self._authorization.can("factura", "read")

    def _can_compare_billing_timeline_receipts(self) -> bool:
        if self._authorization is None:
            return True
        return self._authorization.can("factura", "read") and self._authorization.can("recibo", "read")

    def _rebuild_status_metrics(self) -> None:
        self._fleet_status_metrics = self._status_metrics_from_kpis(
            self._last_kpis.get("fleet_status", {}),
            FLEET_STATUS_DEFINITIONS,
            group="fleet",
        )
        self._driver_status_metrics = self._status_metrics_from_kpis(
            self._last_kpis.get("driver_status", {}),
            DRIVER_STATUS_DEFINITIONS,
            group="driver",
        )

    def _status_visibility_options(
        self,
        group: str,
        definitions: tuple[DashboardMetricDefinition, ...],
    ) -> list[dict[str, Any]]:
        hidden_keys = self._hidden_status_metrics.get(group, set())
        return [
            {
                "key": definition.key,
                "title": definition.title,
                "visible": definition.key not in hidden_keys,
            }
            for definition in definitions
            if self._can_show_metric(definition)
        ]

    def _status_definition_keys(self, group: str) -> set[str]:
        definitions = FLEET_STATUS_DEFINITIONS if group == "fleet" else DRIVER_STATUS_DEFINITIONS
        return {definition.key for definition in definitions}

    def _normalize_status_group(self, group: str) -> str:
        normalized = str(group or "").strip().lower()
        if normalized in {"fleet", "camion", "camiones"}:
            return "fleet"
        if normalized in {"driver", "conductor", "conductores"}:
            return "driver"
        return ""

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _set_billing_timeline_rows(self, rows: object) -> None:
        mapped_rows = [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        self._billing_timeline_all_rows = mapped_rows
        self._billing_timeline_currencies = self._billing_timeline_currency_options(mapped_rows)
        valid_keys = {str(option["key"]) for option in self._billing_timeline_currencies}
        if self._selected_billing_timeline_currency not in valid_keys:
            self._selected_billing_timeline_currency = ""
            self.billingTimelineCurrencyChanged.emit("")
        self._refresh_visible_billing_timeline_rows()
        self.billingTimelineChanged.emit()

    def _refresh_visible_billing_timeline_rows(self) -> None:
        selected = self._selected_billing_timeline_currency
        if selected == "":
            self._billing_timeline_rows = [dict(row) for row in self._billing_timeline_all_rows]
            return
        self._billing_timeline_rows = [
            dict(row)
            for row in self._billing_timeline_all_rows
            if str(row.get("moneda") or "").upper() == selected
        ]

    @staticmethod
    def _billing_timeline_currency_options(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
        currencies = sorted(
            {str(row.get("moneda") or "").upper() for row in rows if str(row.get("moneda") or "").strip()},
            key=lambda value: ({"USD": 0, "NIO": 1}.get(value, 99), value),
        )
        return [{"key": "", "label": "Todas"}, *[{"key": currency, "label": currency} for currency in currencies]]
