"""QML-facing view models for unified reports."""

from __future__ import annotations

from typing import Any

from openlogistic_erp.application.reports import ReportCatalogService, ReportExportService, ReportGenerationService
from openlogistic_erp.domain.reports import ReportFormat, ReportPayload, ReportRequest

from ..qt import Property, QmlNamedElement, QmlUncreatable, QObject, Signal, Slot
from .table_model import ReportTableModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("ReportsModuleViewModel")
@QmlUncreatable("ReportsModuleViewModel instances are created in Python and injected into QML.")
class ReportsModuleViewModel(QObject):
    reportsChanged = Signal()
    selectedReportKeyChanged = Signal(str)
    selectedReportChanged = Signal()
    filtersChanged = Signal()
    payloadChanged = Signal()
    tablesChanged = Signal()
    currenciesChanged = Signal()
    selectedCurrencyKeyChanged = Signal(str)
    busyChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    activeTableModelChanged = Signal()
    activeTableIndexChanged = Signal(int)

    def __init__(
        self,
        *,
        catalog_service: ReportCatalogService,
        generation_service: ReportGenerationService,
        export_service: ReportExportService,
    ) -> None:
        super().__init__()
        self._catalog_service = catalog_service
        self._generation_service = generation_service
        self._export_service = export_service
        self._reports = self._catalog_service.list_definitions()
        self._selected_report_key = ""
        self._selected_report: dict[str, Any] = {}
        self._filters: list[dict[str, Any]] = []
        self._payload: dict[str, Any] = {}
        self._tables: list[dict[str, Any]] = []
        self._currencies: list[dict[str, Any]] = []
        self._selected_currency_key = ""
        self._busy = False
        self._error_message = ""
        self._latest_payload: ReportPayload | None = None
        self._active_table_index = -1
        self._active_table_model = ReportTableModel()

    @Property("QVariantList", notify=reportsChanged)
    def reports(self) -> object:
        return [dict(report) for report in self._reports]

    @Property(str, notify=selectedReportKeyChanged)
    def selected_report_key(self) -> str:
        return self._selected_report_key

    @Property("QVariantMap", notify=selectedReportChanged)
    def selected_report(self) -> object:
        return dict(self._selected_report)

    @Property("QVariantList", notify=filtersChanged)
    def filters(self) -> object:
        return [dict(filter_definition) for filter_definition in self._filters]

    @Property("QVariantMap", notify=payloadChanged)
    def payload(self) -> object:
        return dict(self._payload)

    @Property("QVariantList", notify=tablesChanged)
    def tables(self) -> object:
        return [dict(table) for table in self._tables]

    @Property("QVariantList", notify=currenciesChanged)
    def currencies(self) -> object:
        return [dict(currency) for currency in self._currencies]

    @Property(str, notify=selectedCurrencyKeyChanged)
    def selected_currency_key(self) -> str:
        return self._selected_currency_key

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(ReportTableModel, notify=activeTableModelChanged)
    def active_table_model(self) -> ReportTableModel:
        return self._active_table_model

    @Property(ReportTableModel, notify=activeTableModelChanged)
    def table_model(self) -> ReportTableModel:
        return self._active_table_model

    @Property(int, notify=activeTableIndexChanged)
    def active_table_index(self) -> int:
        return self._active_table_index

    @property
    def latest_payload(self) -> ReportPayload | None:
        return self._latest_payload

    @Slot(str)
    def select_report(self, report_key: str) -> None:
        normalized = str(report_key or "").strip()
        if normalized == self._selected_report_key:
            return
        previous_report_key = self._selected_report_key
        try:
            definition = self._catalog_service.get_definition(normalized)
            selected_report = definition.to_map()
            self._set_error_message("")
        except Exception as exc:
            selected_report = {}
            self._set_error_message(str(exc))

        self._selected_report_key = normalized if selected_report else ""
        self.selectedReportKeyChanged.emit(self._selected_report_key)
        self._selected_report = selected_report
        self.selectedReportChanged.emit()
        self._filters = self._filters_for_qml(selected_report.get("filters", []))
        self.filtersChanged.emit()
        if previous_report_key != self._selected_report_key:
            self._clear_generated_state()

    @Slot(str, result=object)
    def options_for(self, source: str) -> object:
        try:
            return self._catalog_service.options_for(str(source or "").strip())
        except Exception as exc:
            self._set_error_message(str(exc))
            return []

    @Slot("QVariant", result=bool)
    def generate(self, params: object = None) -> bool:

        if not self._selected_report_key:
            self._set_error_message("Se requiere seleccionar un reporte")
            return False
        self._set_busy(True)
        try:
            coerced_params = self._coerce_params(params)
            request = ReportRequest(
                report_key=self._selected_report_key,
                params=coerced_params
            )
            payload = self._generation_service.generate(request)
        except Exception as exc:
            self._clear_generated_state()
            self._set_error_message(str(exc))
            return False
        finally:
            self._set_busy(False)

        self._apply_payload(payload)
        self._set_error_message("")
        return True

    @Slot(str)
    def select_currency(self, currency_key: str) -> None:
        normalized = str(currency_key or "").strip()
        if self._selected_currency_key != normalized:
            self._selected_currency_key = normalized
            self.selectedCurrencyKeyChanged.emit(normalized)
            self._reset_active_table_model()
            self.activeTableModelChanged.emit()

    @Slot(int)
    def select_table(self, index: int) -> None:
        if self._latest_payload is None or index < 0 or index >= len(self._latest_payload.tables):
            self._active_table_index = -1
            self.activeTableIndexChanged.emit(-1)
            self._active_table_model.set_report_table(None)
            self.activeTableModelChanged.emit()
            return

        self._active_table_index = index
        self.activeTableIndexChanged.emit(index)
        self._reset_active_table_model()
        self.activeTableModelChanged.emit()

    @Slot(str, result=bool)
    def export_pdf(self, target_path: str) -> bool:
        return self._export(target_path, ReportFormat.PDF)

    @Slot(str, result=bool)
    def export_xlsx(self, target_path: str) -> bool:
        return self._export(target_path, ReportFormat.XLSX)

    def _export(self, target_path: str, export_format: ReportFormat) -> bool:
        if self._latest_payload is None:
            self._set_error_message("No hay reporte generado para exportar")
            return False
        self._set_busy(True)
        try:
            self._export_service.export(
                self._latest_payload,
                target_path,
                export_format,
                currency_key=self._selected_currency_key,
            )
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self._set_busy(False)
        self._set_error_message("")
        return True

    def _apply_payload(self, payload: ReportPayload) -> None:
        mapped = payload.to_map()
        self._latest_payload = payload
        self._payload = mapped
        self.payloadChanged.emit()
        self._tables = [dict(table) for table in mapped.get("tables", [])]
        self.tablesChanged.emit()
        self._currencies = self._currencies_for_qml(mapped.get("currencies", []))
        self.currenciesChanged.emit()
        self._selected_currency_key = ""
        self.selectedCurrencyKeyChanged.emit(self._selected_currency_key)
        self.select_table(0 if payload.tables else -1)

    def _clear_generated_state(self) -> None:
        self._latest_payload = None
        self._payload = {}
        self.payloadChanged.emit()
        self._tables = []
        self.tablesChanged.emit()
        self._currencies = []
        self.currenciesChanged.emit()
        self._selected_currency_key = ""
        self.selectedCurrencyKeyChanged.emit("")
        self._active_table_index = -1
        self.activeTableIndexChanged.emit(-1)
        self._active_table_model.set_report_table(None)
        self.activeTableModelChanged.emit()

    def _reset_active_table_model(self) -> None:
        if self._latest_payload is None or self._active_table_index < 0:
            self._active_table_model.set_report_table(None)
            return
        if self._active_table_index >= len(self._latest_payload.tables):
            self._active_table_model.set_report_table(None)
            return
        self._active_table_model.set_report_table(
            self._latest_payload.tables[self._active_table_index],
            self._selected_currency_key,
        )

    def _set_busy(self, value: bool) -> None:
        normalized = bool(value)
        if self._busy != normalized:
            self._busy = normalized
            self.busyChanged.emit(normalized)

    def _set_error_message(self, value: str) -> None:
        normalized = str(value or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _filters_for_qml(self, filters: object) -> list[dict[str, Any]]:
        qml_filters: list[dict[str, Any]] = []
        for filter_definition in filters if isinstance(filters, list) else []:
            mapped = dict(filter_definition)
            source = str(mapped.get("option_source") or "").strip()
            if source and not mapped.get("options"):
                try:
                    mapped["options"] = self._catalog_service.options_for(source)
                except Exception as exc:
                    mapped["options"] = []
                    self._set_error_message(str(exc))
            qml_filters.append(mapped)
        return qml_filters

    @staticmethod
    def _currencies_for_qml(currencies: object) -> list[dict[str, Any]]:
        mapped = [dict(currency) for currency in currencies if isinstance(currency, dict)]
        if not mapped:
            return []
        return [{"key": "", "label": "Todas"}, *mapped]

    @staticmethod
    def _coerce_params(params: object) -> dict[str, Any]:
        if params is None:
            return {}
        if isinstance(params, dict):
            return dict(params)
        if hasattr(params, "toVariant"):
            variant = params.toVariant()
            if variant is None:
                return {}
            if isinstance(variant, dict):
                return dict(variant)
            try:
                return dict(variant)
            except (TypeError, ValueError):
                return {}
        try:
            return dict(params)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return {}
