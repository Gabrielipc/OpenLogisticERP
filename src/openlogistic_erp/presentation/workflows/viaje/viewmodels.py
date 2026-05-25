"""Specialized workflow coordinator for Viaje built on top of a catalog list screen."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from ....application.modelo.services import ModeloWorkflowService
from ....domain.modelo.catalog_queries import CatalogFilter, CatalogFilterOperator
from ...catalog.screen_view_model import CatalogScreenViewModel
from ...qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ..common import WorkflowDescriptor, WorkflowModuleViewModel
from .detail import DetalleOperacionViewModel
from .forms import ViajeFormViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("ViajeWorkflowViewModel")
@QmlUncreatable("ViajeWorkflowViewModel instances are created in Python and injected into QML.")
class ViajeWorkflowViewModel(WorkflowModuleViewModel):
    listScreenChanged = Signal()
    errorMessageChanged = Signal(str)
    selectedRecordIdChanged = Signal(object)
    selectedViajeChanged = Signal()
    activePageChanged = Signal(str)
    activeFormChanged = Signal()
    detailSummaryChanged = Signal()
    detailViewModelChanged = Signal()
    activeSubpageTitleChanged = Signal(str)
    canDeleteSelectedViajeChanged = Signal(bool)
    activeDetailRecordIdChanged = Signal(object)
    dateFilterModeChanged = Signal(str)
    selectedMonthChanged = Signal(str)
    globalFiltersChanged = Signal()
    permissionsChanged = Signal()
    unbilledTripsChanged = Signal()

    def __init__(
        self,
        descriptor: WorkflowDescriptor,
        *,
        list_screen: CatalogScreenViewModel,
        workflow_service: ModeloWorkflowService,
    ) -> None:
        super().__init__(descriptor)
        self._list_screen = list_screen
        self._workflow_service = workflow_service
        self._detail_summary: dict[str, Any] = {}
        self._detail_error_message = ""
        self._error_message = ""
        self._active_page = "list"
        self._active_subpage_title = ""
        self._detail_busy = False
        self._initialized = False
        self._unbilled_trips: list[dict[str, Any]] = []
        self._date_filter_mode = "last_month"
        self._selected_month = date.today().strftime("%Y-%m")
        self._detail_view_model: DetalleOperacionViewModel | None = self._create_detail_view_model()
        self._wire_list_screen()
        self._sync_busy_state()
        self._sync_error_state()

    @Property(CatalogScreenViewModel, notify=listScreenChanged)
    def list_screen(self) -> CatalogScreenViewModel:
        return self._list_screen

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(object, notify=selectedRecordIdChanged)
    def selected_record_id(self) -> object:
        return self._list_screen.selected_record_id

    @Property("QVariantMap", notify=selectedViajeChanged)
    def selected_viaje(self) -> object:
        selected = self._list_screen.selected_row_data
        return {} if not isinstance(selected, dict) else dict(selected)

    @Property(str, notify=activePageChanged)
    def active_page(self) -> str:
        return self._active_page

    @Property(str, notify=activeSubpageTitleChanged)
    def active_subpage_title(self) -> str:
        return self._active_subpage_title

    @Property(ViajeFormViewModel, notify=activeFormChanged)
    def active_form(self) -> ViajeFormViewModel | None:
        form = self._list_screen.form_host.active_form
        return form if isinstance(form, ViajeFormViewModel) else None

    @Property("QVariantMap", notify=detailSummaryChanged)
    def detail_summary(self) -> object:
        return dict(self._detail_summary)

    @Property(DetalleOperacionViewModel, notify=detailViewModelChanged)
    def detail_view_model(self) -> DetalleOperacionViewModel | None:
        return self._detail_view_model

    @Property(object, notify=activeDetailRecordIdChanged)
    def active_detail_record_id(self) -> object:
        viaje = self._detail_summary.get("viaje")
        if not isinstance(viaje, dict):
            return None
        record_id = viaje.get("id")
        return int(record_id) if isinstance(record_id, int) else None

    @Property(str, notify=dateFilterModeChanged)
    def date_filter_mode(self) -> str:
        return self._date_filter_mode

    @Property(str, notify=selectedMonthChanged)
    def selected_month(self) -> str:
        return self._selected_month

    @Property("QVariantList", notify=unbilledTripsChanged)
    def unbilled_trips(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._unbilled_trips]
    
    @Property("QVariantList", notify=globalFiltersChanged)
    def global_filters(self):
        filters = []

        filters.append({
            "key": "period",
            "label": "Periodo",
            "displayValue": self._get_period_display_value(),
            "resettable": False,
            "editorType": "period",
            "value": self._date_filter_mode,
            "month": self._selected_month
        })

        return filters

    def _get_period_display_value(self):
        mode = self._date_filter_mode
        
        if mode == "all":
            return "Histórico"
        elif mode == "last_week":
            return "Ultima Semana"
        elif mode == "last_month":
            return "Último Mes"
        elif mode == "selected_month":
            return f"Mes {self._selected_month}"
    
    @Property(bool, notify=canDeleteSelectedViajeChanged)
    def can_delete_selected_viaje(self) -> bool:
        return self._list_screen.can_delete and self.selected_record_id is not None

    @Property(bool, notify=permissionsChanged)
    def can_create_viaje(self) -> bool:
        return self._list_screen.can_create

    @Property(bool, notify=permissionsChanged)
    def can_edit_viaje(self) -> bool:
        return self._list_screen.can_edit

    @Property(bool, notify=permissionsChanged)
    def can_open_detail(self) -> bool:
        return True

    def _wire_list_screen(self) -> None:
        self._list_screen.busyChanged.connect(self._handle_list_busy_changed)
        self._list_screen.errorMessageChanged.connect(self._handle_list_error_changed)
        self._list_screen.selectedRecordIdChanged.connect(self._handle_selected_record_changed)
        self._list_screen.selectedRowDataChanged.connect(self._handle_selected_row_data_changed)
        self._list_screen.form_host.activeFormChanged.connect(self._handle_active_form_changed)
        self._list_screen.form_host.activeFormChanged.connect(self._rewire_active_form_title)
        self._list_screen.canCreateChanged.connect(self._handle_permissions_changed)
        self._list_screen.canEditChanged.connect(self._handle_permissions_changed)
        self._list_screen.canDeleteChanged.connect(self._handle_permissions_changed)

    def _unwire_list_screen(self) -> None:
        for signal, slot in (
            (self._list_screen.busyChanged, self._handle_list_busy_changed),
            (self._list_screen.errorMessageChanged, self._handle_list_error_changed),
            (self._list_screen.selectedRecordIdChanged, self._handle_selected_record_changed),
            (self._list_screen.selectedRowDataChanged, self._handle_selected_row_data_changed),
            (self._list_screen.form_host.activeFormChanged, self._handle_active_form_changed),
            (self._list_screen.form_host.activeFormChanged, self._rewire_active_form_title),
            (self._list_screen.canCreateChanged, self._handle_permissions_changed),
            (self._list_screen.canEditChanged, self._handle_permissions_changed),
            (self._list_screen.canDeleteChanged, self._handle_permissions_changed),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass

    def _create_detail_view_model(self) -> DetalleOperacionViewModel:
        detail_view_model = DetalleOperacionViewModel(
            workflow_service=self._workflow_service,
            can_modify=self._list_screen.can_edit,
        )
        detail_view_model.summaryChanged.connect(self._handle_detail_summary_changed)
        detail_view_model.errorMessageChanged.connect(self._handle_detail_error_changed)
        return detail_view_model

    def _replace_detail_view_model(self) -> None:
        previous = self._detail_view_model
        if previous is None:
            return
        try:
            previous.summaryChanged.disconnect(self._handle_detail_summary_changed)
        except TypeError:
            pass
        try:
            previous.errorMessageChanged.disconnect(self._handle_detail_error_changed)
        except TypeError:
            pass
        self._detail_view_model = None
        self.detailViewModelChanged.emit()
        previous.deleteLater()

    def _rewire_active_form_title(self) -> None:
        form = self.active_form
        previous = getattr(self, "_observed_form", None)
        if previous is form:
            return
        if previous is not None:
            try:
                previous.titleChanged.disconnect(self._handle_active_form_title_changed)
            except TypeError:
                pass
        self._observed_form = form
        if form is not None:
            form.titleChanged.connect(self._handle_active_form_title_changed)

    def _handle_active_form_title_changed(self, title: str) -> None:
        if self._active_page == "form":
            self._set_active_subpage_title(title)

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _set_detail_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._detail_error_message != normalized:
            self._detail_error_message = normalized
            self._sync_error_state()

    def _sync_error_state(self) -> None:
        self._set_error_message(self._detail_error_message or self._list_screen.error_message)

    def _sync_busy_state(self) -> None:
        self.is_busy = bool(self._detail_busy or self._list_screen.is_busy)

    def _set_detail_busy(self, value: bool) -> None:
        normalized = bool(value)
        if self._detail_busy != normalized:
            self._detail_busy = normalized
            self._sync_busy_state()

    def _set_active_page(self, value: str) -> None:
        normalized = str(value or "list")
        if self._active_page != normalized:
            self._active_page = normalized
            self.activePageChanged.emit(normalized)

    def _set_active_subpage_title(self, value: str) -> None:
        normalized = str(value or "")
        if self._active_subpage_title != normalized:
            self._active_subpage_title = normalized
            self.activeSubpageTitleChanged.emit(normalized)

    def _handle_list_busy_changed(self, _busy: bool) -> None:
        self._sync_busy_state()

    def _handle_list_error_changed(self, _message: str) -> None:
        self._sync_error_state()

    def _handle_detail_summary_changed(self) -> None:
        if self._detail_view_model is None:
            return
        self._detail_summary = self._detail_view_model.summary
        self.detailSummaryChanged.emit()
        self.activeDetailRecordIdChanged.emit(self.active_detail_record_id)

    def _handle_detail_error_changed(self, message: str) -> None:
        self._set_detail_error_message(message)

    def _handle_selected_record_changed(self, record_id: object) -> None:
        self.selectedRecordIdChanged.emit(record_id)
        self.canDeleteSelectedViajeChanged.emit(self.can_delete_selected_viaje)

    def _handle_selected_row_data_changed(self) -> None:
        self.selectedViajeChanged.emit()

    def _handle_permissions_changed(self) -> None:
        if self._detail_view_model is not None:
            self._detail_view_model.set_can_modify(self._list_screen.can_edit)
        self.permissionsChanged.emit()
        self.canDeleteSelectedViajeChanged.emit(self.can_delete_selected_viaje)

    def _handle_active_form_changed(self) -> None:
        form = self.active_form
        if form is not None:
            self._set_active_page("form")
            self._set_active_subpage_title(form.title)
        elif self._active_page == "form":
            self._set_active_page("list")
            self._set_active_subpage_title("")
        self.activeFormChanged.emit()

    def _set_date_filter_mode(self, value: str) -> None:
        normalized = str(value or "all").strip().lower()
        if normalized not in {"all", "last_week", "last_month", "selected_month"}:
            normalized = "all"
        if self._date_filter_mode != normalized:
            self._date_filter_mode = normalized
            self.dateFilterModeChanged.emit(normalized)

    def _set_selected_month(self, value: str) -> None:
        normalized = self._normalize_month(value)
        if self._selected_month != normalized:
            self._selected_month = normalized
            self.selectedMonthChanged.emit(normalized)

    @staticmethod
    def _normalize_month(value: str) -> str:
        raw_value = str(value or "").strip()
        try:
            parsed = datetime.strptime(raw_value, "%Y-%m")
        except ValueError:
            parsed = datetime.combine(date.today().replace(day=1), time.min)
        return parsed.strftime("%Y-%m")

    @staticmethod
    def _month_range(month_value: str) -> tuple[datetime, datetime]:
        start = datetime.strptime(month_value, "%Y-%m")
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end - timedelta(microseconds=1)

    def _date_filters_for_mode(self, mode: str, month_value: str) -> tuple[CatalogFilter, ...]:
        today = date.today()
        end = datetime.combine(today + timedelta(days=1), time.min) - timedelta(microseconds=1)
        if mode == "last_week":
            start = datetime.combine(today - timedelta(days=6), time.min)
        elif mode == "last_month":
            start = datetime.combine(today - timedelta(days=29), time.min)
        elif mode == "selected_month":
            start, end = self._month_range(month_value)
        else:
            return ()
        return (
            CatalogFilter(
                field="fecha_posicionamiento",
                operator=CatalogFilterOperator.BETWEEN,
                value=start.isoformat(timespec="seconds"),
                value_to=end.isoformat(timespec="seconds"),
                is_hidden=True,
            ),
        )

    def _filters_without_date_range(self) -> tuple[CatalogFilter, ...]:
        return tuple(
            filter_spec
            for filter_spec in self._list_screen.filters
            if filter_spec.field != "fecha_posicionamiento"
        )

    @staticmethod
    def _normalize_record_id(record_id: object) -> int:
        if isinstance(record_id, bool):
            raise ValueError("Se requiere identificador valido de viaje")
        if isinstance(record_id, int):
            normalized = record_id
        elif isinstance(record_id, str):
            raw_value = record_id.strip()
            if not raw_value:
                raise ValueError("Se requiere identificador valido de viaje")
            normalized = int(raw_value)
        else:
            normalized = int(record_id)
        if normalized <= 0:
            raise ValueError("Se requiere identificador valido de viaje")
        return normalized

    @Slot()
    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._list_screen.load_screen()

    @Slot(result=object)
    def refresh(self) -> int | None:
        return self._list_screen.refresh()

    @Slot()
    def refresh_data(self) -> None:
        self._list_screen.refresh_data()

    @Slot(str, result=object)
    def apply_search(self, term: str) -> int | None:
        return self._list_screen.apply_search(term)

    @Slot()
    def clear_search(self) -> int:
        return self._list_screen.clear_search()

    @Slot(str, str, result=bool)
    def apply_date_filter(self, mode: str, month_value: str = "") -> bool:
        normalized_mode = str(mode or "all").strip().lower()
        normalized_month = self._normalize_month(month_value or self._selected_month)
        try:
            filters = self._filters_without_date_range() + self._date_filters_for_mode(normalized_mode, normalized_month)
            self._list_screen.set_filters(filters)
            self._set_date_filter_mode(normalized_mode)
            self._set_selected_month(normalized_month)
            return True
        except Exception as exc:
            self._set_detail_error_message(str(exc))
            return False

    @Slot()
    def next_page(self) -> int | None:
        return self._list_screen.next_page()

    @Slot()
    def prev_page(self) -> int | None:
        return self._list_screen.prev_page()

    @Slot(int)
    def select_row_index(self, row_index: int) -> None:
        self._list_screen.select_row_index(row_index)

    @Slot("QVariant")
    def select_record_by_id(self, record_id: object) -> None:
        self._list_screen.select_record_by_id(self._normalize_record_id(record_id))

    @Slot(int, result=int)
    def record_id_at_row(self, row_index: int) -> int:
        return self._list_screen.record_id_at_row(row_index)

    @Slot(int, result=object)
    def row_data_at(self, row_index: int) -> dict[str, Any]:
        return self._list_screen.row_data_at(row_index)

    @Slot(int, result=object)
    def column_at(self, column_index: int) -> dict[str, Any]:
        return self._list_screen.column_at(column_index)

    @Slot(int, result=int)
    def column_width_at(self, column_index: int) -> int:
        return self._list_screen.column_width_at(column_index)

    @Slot(str)
    def toggle_sort(self, field_name: str) -> None:
        self._list_screen.toggle_sort(field_name)

    @Slot(str, int)
    def set_column_width(self, field_name: str, width: int) -> None:
        self._list_screen.set_column_width(field_name, width)

    @Slot(result=bool)
    def open_create(self) -> bool:
        if not self.can_create_viaje:
            self._set_detail_error_message("No tienes permiso para crear viaje")
            return False
        self.close_detalle()
        self._set_detail_error_message("")
        return self._list_screen.open_create_form()

    @Slot(str, "QVariantMap", result=bool)
    def open_subpage(self, subpage: str, context: object = None) -> bool:
        normalized = str(subpage or "").strip().lower()
        if normalized != "unbilled_trips":
            self._set_detail_error_message(f"Subpagina no soportada: {normalized}")
            return False
        del context
        self.close_detalle()
        self._list_screen.close_active_form()
        self._unbilled_trips = self._workflow_service.viaje.list_unbilled_trips()
        self.unbilledTripsChanged.emit()
        self._set_active_page("unbilled_trips")
        self._set_active_subpage_title("Viajes sin facturar")
        return True

    @Slot()
    def close_subpage(self) -> None:
        if self._active_page == "unbilled_trips":
            self._set_active_page("list")
            self._set_active_subpage_title("")

    @Slot("QVariant", result=bool)
    def open_record_form(self, record_id: object) -> bool:
        if not self.can_edit_viaje:
            self._set_detail_error_message("No tienes permiso para modificar viaje")
            return False
        normalized = self._normalize_record_id(record_id)
        self.close_detalle()
        self._set_detail_error_message("")
        self._list_screen.select_record_by_id(normalized)
        return self._list_screen.open_record_form(normalized)

    @Slot(result=bool)
    def open_selected_form(self) -> bool:
        record_id = self._list_screen.selected_record_id
        if record_id is None:
            self._set_detail_error_message("record_id es requerido para editar")
            return False
        return self.open_record_form(int(record_id))

    @Slot()
    def close_form(self) -> None:
        self._list_screen.close_active_form()

    @Slot()
    def close_active_form(self) -> None:
        self.close_form()

    @Slot(result=bool)
    def save_form(self) -> bool:
        form = self.active_form
        if form is None:
            return False
        if form.mode == "create" and not self.can_create_viaje:
            self._set_detail_error_message("No tienes permiso para crear viaje")
            return False
        if form.mode == "edit" and not self.can_edit_viaje:
            self._set_detail_error_message("No tienes permiso para modificar viaje")
            return False
        return form.submit_form()

    @Slot(result=bool)
    def delete_selected_viaje(self) -> bool:
        record_id = self._list_screen.selected_record_id
        if record_id is None:
            self._set_detail_error_message("record_id es requerido para eliminar")
            return False
        return self.delete_viaje(record_id)

    @Slot(result=bool)
    def delete_active_viaje(self) -> bool:
        if self._detail_view_model is not None and self._detail_view_model.is_closed:
            self._set_detail_error_message("El detalle operativo esta cerrado y no permite eliminar el viaje.")
            return False
        record_id = self.active_detail_record_id
        if record_id is None:
            self._set_detail_error_message("record_id es requerido para eliminar")
            return False
        return self.delete_viaje(record_id)

    @Slot("QVariant", result=bool)
    def delete_viaje(self, record_id: object) -> bool:
        if not self._list_screen.can_delete:
            self._set_detail_error_message("No tienes permiso para eliminar viaje")
            return False
        normalized = self._normalize_record_id(record_id)
        if (
            self.active_detail_record_id == normalized
            and self._detail_view_model is not None
            and self._detail_view_model.is_closed
        ):
            self._set_detail_error_message("El detalle operativo esta cerrado y no permite eliminar el viaje.")
            return False
        try:
            self._set_detail_error_message("")
            self._list_screen.close_active_form()
            self._list_screen.select_record_by_id(normalized)
            deleted = self._list_screen.delete_record_by_id(normalized)
            if deleted:
                self.close_detalle()
            else:
                self._sync_error_state()
            return bool(deleted)
        except Exception as exc:
            self._set_detail_error_message(str(exc))
            return False

    @Slot("QVariant")
    def open_detalle(self, record_id: object) -> None:
        if not self.can_open_detail:
            self._set_detail_error_message("No tienes permiso para leer viaje")
            return
        self._set_detail_error_message("")
        try:
            normalized = self._normalize_record_id(record_id)
            self._list_screen.close_active_form()
            self._list_screen.select_record_by_id(normalized)
            self._set_detail_busy(True)
            if self._detail_view_model is None:
                self._detail_view_model = self._create_detail_view_model()
                self.detailViewModelChanged.emit()
            self._detail_view_model.set_can_modify(self._list_screen.can_edit)
            self._detail_view_model.load(normalized)
            self._detail_summary = self._detail_view_model.summary
            self._set_active_page("detail")
            self._set_active_subpage_title(f"Detalle viaje #{normalized}")
            self.detailSummaryChanged.emit()
            self.activeDetailRecordIdChanged.emit(self.active_detail_record_id)
        except Exception as exc:
            self._set_detail_error_message(str(exc))
        finally:
            self._set_detail_busy(False)

    def set_permissions(self, permissions: dict[str, bool]) -> None:
        self._list_screen.set_permissions(permissions)

    @Slot()
    def close_detalle(self) -> None:
        self._set_active_page("list")
        self._set_active_subpage_title("")
        self._replace_detail_view_model()
        if self._detail_summary:
            self._detail_summary = {}
            self.detailSummaryChanged.emit()
            self.activeDetailRecordIdChanged.emit(None)
        self._set_detail_error_message("")

    @Slot()
    def dispose(self) -> None:
        if getattr(self, "_disposed", False):
            return
        self._unwire_list_screen()
        previous_form = getattr(self, "_observed_form", None)
        if previous_form is not None:
            try:
                previous_form.titleChanged.disconnect(self._handle_active_form_title_changed)
            except TypeError:
                pass
            self._observed_form = None
        self.close_detalle()
        self._list_screen.dispose()
        self._list_screen.deleteLater()
        super().dispose()
