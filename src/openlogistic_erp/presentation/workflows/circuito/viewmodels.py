"""Specialized workflow coordinator for Circuito."""

from __future__ import annotations

from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloWorkflowService
from ....infrastructure.persistence.modelo.workflow_orm import TipoViaje
from ...catalog.forms import BaseFormViewModel
from ...catalog.screen_view_model import CatalogScreenViewModel
from ...catalog.types import FormMode
from ...qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ..common import WorkflowDescriptor, WorkflowModuleViewModel
from ..viaje.forms import ViajeFormViewModel
from .detail import CircuitoDetailViewModel
from .forms import CircuitoBasicFormViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@QmlNamedElement("CircuitoWorkflowViewModel")
@QmlUncreatable("CircuitoWorkflowViewModel instances are created in Python and injected into QML.")
class CircuitoWorkflowViewModel(WorkflowModuleViewModel):
    listScreenChanged = Signal()
    errorMessageChanged = Signal(str)
    selectedRecordIdChanged = Signal(object)
    activePageChanged = Signal(str)
    activeFormChanged = Signal()
    detailSummaryChanged = Signal()
    detailViewModelChanged = Signal()
    activeSubpageTitleChanged = Signal(str)
    permissionsChanged = Signal()

    def __init__(
        self,
        descriptor: WorkflowDescriptor,
        *,
        list_screen: CatalogScreenViewModel,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        can_create_return_trip: bool = True,
    ) -> None:
        super().__init__(descriptor)
        self._list_screen = list_screen
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._can_create_return_trip = bool(can_create_return_trip)
        self._active_page = "list"
        self._active_subpage_title = ""
        self._detail_summary: dict[str, Any] = {}
        self._detail_view_model: CircuitoDetailViewModel | None = self._create_detail_view_model()
        self._error_message = ""
        self._detail_busy = False
        self._initialized = False
        self._pending_return_trip_circuito_id: int | None = None
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

    @Property(str, notify=activePageChanged)
    def active_page(self) -> str:
        return self._active_page

    @Property(str, notify=activeSubpageTitleChanged)
    def active_subpage_title(self) -> str:
        return self._active_subpage_title

    @Property(BaseFormViewModel, notify=activeFormChanged)
    def active_form(self) -> BaseFormViewModel | None:
        return self._list_screen.form_host.active_form

    @Property("QVariantMap", notify=detailSummaryChanged)
    def detail_summary(self) -> dict[str, Any]:
        return dict(self._detail_summary)

    @Property(CircuitoDetailViewModel, notify=detailViewModelChanged)
    def detail_view_model(self) -> CircuitoDetailViewModel | None:
        return self._detail_view_model

    @Property(bool, notify=permissionsChanged)
    def can_edit_circuito(self) -> bool:
        return self._list_screen.can_edit

    @Property(bool, notify=permissionsChanged)
    def can_create_return_trip(self) -> bool:
        return self._can_create_return_trip

    def _wire_list_screen(self) -> None:
        self._list_screen.busyChanged.connect(self._handle_list_busy_changed)
        self._list_screen.errorMessageChanged.connect(self._handle_list_error_changed)
        self._list_screen.selectedRecordIdChanged.connect(self._handle_selected_record_changed)
        self._list_screen.form_host.activeFormChanged.connect(self._handle_active_form_changed)
        self._list_screen.form_host.formSaved.connect(self._handle_form_saved)
        self._list_screen.canEditChanged.connect(self._handle_permissions_changed)

    def _create_detail_view_model(self) -> CircuitoDetailViewModel:
        detail = CircuitoDetailViewModel(
            workflow_service=self._workflow_service,
            reference_lookup_service=self._reference_lookup_service,
            can_modify=self._list_screen.can_edit,
            can_create_return_trip=self._can_create_return_trip,
        )
        detail.summaryChanged.connect(self._handle_detail_summary_changed)
        detail.errorMessageChanged.connect(self._handle_detail_error_changed)
        return detail

    def _handle_list_busy_changed(self, _busy: bool) -> None:
        self._sync_busy_state()

    def _handle_list_error_changed(self, _message: str) -> None:
        self._sync_error_state()

    def _handle_selected_record_changed(self, record_id: object) -> None:
        self.selectedRecordIdChanged.emit(record_id)

    def _handle_active_form_changed(self) -> None:
        form = self.active_form
        if form is not None:
            self._set_active_page("form")
            self._set_active_subpage_title(form.title)
        elif self._active_page == "form":
            self._set_active_page("list")
            self._set_active_subpage_title("")
        self.activeFormChanged.emit()

    def _handle_form_saved(self, _payload: dict[str, Any]) -> None:
        circuito_id = self._pending_return_trip_circuito_id
        self._pending_return_trip_circuito_id = None
        if circuito_id is None:
            return
        self.open_detalle(circuito_id)

    def _handle_permissions_changed(self) -> None:
        if self._detail_view_model is not None:
            self._detail_view_model.set_permissions(
                can_modify=self._list_screen.can_edit,
                can_create_return_trip=self._can_create_return_trip,
            )
        self.permissionsChanged.emit()

    def _handle_detail_summary_changed(self) -> None:
        if self._detail_view_model is None:
            return
        self._detail_summary = self._detail_view_model.summary
        self.detailSummaryChanged.emit()

    def _handle_detail_error_changed(self, message: str) -> None:
        self._set_error_message(message or self._list_screen.error_message)

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _sync_error_state(self) -> None:
        detail_error = self._detail_view_model.error_message if self._detail_view_model is not None else ""
        self._set_error_message(detail_error or self._list_screen.error_message)

    def _sync_busy_state(self) -> None:
        detail_busy = self._detail_view_model.is_busy if self._detail_view_model is not None else False
        self.is_busy = bool(self._detail_busy or detail_busy or self._list_screen.is_busy)

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

    @staticmethod
    def _normalize_record_id(record_id: object) -> int:
        if isinstance(record_id, int) and record_id > 0:
            return record_id
        if isinstance(record_id, str) and record_id.strip().isdigit():
            return int(record_id)
        raise ValueError("Se requiere identificador valido de circuito")

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

    @Slot("QVariant")
    def select_record_by_id(self, record_id: object) -> None:
        self._list_screen.select_record_by_id(self._normalize_record_id(record_id))

    @Slot("QVariant", result=bool)
    def open_record_form(self, record_id: object) -> bool:
        normalized = self._normalize_record_id(record_id)
        self.open_detalle(normalized)
        return self._active_page == "detail"

    @Slot(result=bool)
    def open_create(self) -> bool:
        self._set_error_message("Los circuitos se crean automaticamente desde viajes de exportacion.")
        return False

    @Slot(result=bool)
    def save_form(self) -> bool:
        form = self.active_form
        if form is None:
            return False
        return bool(form.submit_form())

    @Slot()
    def close_form(self) -> None:
        self._pending_return_trip_circuito_id = None
        self._list_screen.close_active_form()

    @Slot("QVariant")
    def open_detalle(self, record_id: object) -> None:
        normalized = self._normalize_record_id(record_id)
        self._list_screen.close_active_form()
        self._list_screen.select_record_by_id(normalized)
        self._detail_busy = True
        self._sync_busy_state()
        try:
            if self._detail_view_model is None:
                self._detail_view_model = self._create_detail_view_model()
                self.detailViewModelChanged.emit()
            self._detail_view_model.set_permissions(
                can_modify=self._list_screen.can_edit,
                can_create_return_trip=self._can_create_return_trip,
            )
            self._detail_view_model.load(normalized)
            self._detail_summary = self._detail_view_model.summary
            self._set_active_page("detail")
            self._set_active_subpage_title(f"Detalle circuito #{normalized}")
            self.detailSummaryChanged.emit()
        except Exception as exc:
            self._set_error_message(str(exc))
        finally:
            self._detail_busy = False
            self._sync_busy_state()

    @Slot()
    def close_detalle(self) -> None:
        self._set_active_page("list")
        self._set_active_subpage_title("")
        if self._detail_summary:
            self._detail_summary = {}
            self.detailSummaryChanged.emit()

    @Slot(str, result=bool)
    def open_return_trip_form(self, trip_type: str) -> bool:
        detail = self._detail_view_model
        if detail is not None and detail.is_closed:
            self._set_error_message("No se puede modificar un circuito finalizado")
            return False
        if not self._list_screen.can_edit:
            self._set_error_message("No tienes permiso para modificar circuito")
            return False
        if not self._can_create_return_trip:
            self._set_error_message("No tienes permiso para crear viaje")
            return False
        if detail is None or not detail.can_add_return_trip:
            return False
        circuito_id = detail.circuito_summary.get("id")
        if circuito_id is None:
            return False
        normalized_type = str(trip_type or TipoViaje.IMPOR.value)
        if normalized_type not in {TipoViaje.IMPOR.value, TipoViaje.VACIO.value}:
            normalized_type = TipoViaje.IMPOR.value
        form = self._list_screen.form_host.open_form(
            "viaje",
            mode=FormMode.CREATE,
            preferred_form_id="viaje-workflow",
            context={},
        )
        if not isinstance(form, ViajeFormViewModel):
            return False
        form.prepare_return_trip(int(circuito_id), normalized_type)
        self._pending_return_trip_circuito_id = int(circuito_id)
        self._set_active_page("form")
        self._set_active_subpage_title(f"Nuevo viaje de vuelta circuito #{circuito_id}")
        self.activeFormChanged.emit()
        return True

    def set_permissions(self, *, can_edit_circuito: bool, can_create_return_trip: bool) -> None:
        self._list_screen.set_permissions(
            {
                "create": False,
                "edit": bool(can_edit_circuito),
                "delete": False,
            }
        )
        self._can_create_return_trip = bool(can_create_return_trip)
        if self._detail_view_model is not None:
            self._detail_view_model.set_permissions(
                can_modify=bool(can_edit_circuito),
                can_create_return_trip=self._can_create_return_trip,
            )
        self.permissionsChanged.emit()

    @Slot()
    def dispose(self) -> None:
        if getattr(self, "_disposed", False):
            return
        self._list_screen.dispose()
        self._list_screen.deleteLater()
        if self._detail_view_model is not None:
            self._detail_view_model.dispose()
            self._detail_view_model.deleteLater()
            self._detail_view_model = None
        super().dispose()
