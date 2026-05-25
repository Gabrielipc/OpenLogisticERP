"""Catalog screen view model with table-backed listing and pluggable form host."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ...application.modelo.query_service import ModeloCatalogQueryService
from ...application.modelo.services import ModeloCatalogService
from ...domain.modelo.catalog_queries import (
    CatalogFilter,
    CatalogFilterOperator,
    CatalogQueryRequest,
    CatalogSort,
    CatalogSortDirection,
)
from ...domain.modelo.dtos import FieldKind, FieldSchemaDTO
from ..qt import QCoreApplication, QThreadPool, Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ..viewmodels.base_view_model import BaseViewModel
from .async_load import (
    CatalogLoadFailure,
    CatalogLoadRequest,
    CatalogLoadResult,
    CatalogLoadRunner,
    QtThreadPoolCatalogLoadRunner,
)
from .definitions import CatalogViewDefinition
from .form_host_view_model import FormHostViewModel
from .table_model import CatalogTableModel
from .serialization import display_catalog_value, display_money_value
from .table_preferences import CatalogTablePreferencesStore, InMemoryCatalogTablePreferencesStore
from .types import FormMode

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

_ACTION_COLUMN_KEY = "__actions__"
_ACTION_COLUMN_WIDTH = 100
_ACTION_COLUMN_MIN_WIDTH = 100


def _operator_label(operator_name: str) -> str:
    normalized = str(operator_name or "").strip().lower()
    labels = {
        CatalogFilterOperator.EQ.value: "Es igual a",
        CatalogFilterOperator.CONTAINS.value: "Contiene",
        CatalogFilterOperator.IN.value: "Es uno de",
        CatalogFilterOperator.GTE.value: "Mayor o igual",
        CatalogFilterOperator.LTE.value: "Menor o igual",
        CatalogFilterOperator.BETWEEN.value: "Entre",
    }
    return labels.get(normalized, normalized.title())


@QmlNamedElement("CatalogScreenViewModel")
@QmlUncreatable("CatalogScreenViewModel instances are created in Python and injected into QML.")
class CatalogScreenViewModel(BaseViewModel):
    tableModelChanged = Signal()
    formHostChanged = Signal()
    titleChanged = Signal()
    catalogNameChanged = Signal()
    searchFieldChanged = Signal()
    searchFieldsChanged = Signal()
    searchPlaceholderChanged = Signal()
    filterFieldsChanged = Signal()
    activeFiltersChanged = Signal()
    columnsChanged = Signal()
    canCreateChanged = Signal()
    canEditChanged = Signal()
    canDeleteChanged = Signal()
    canExportChanged = Signal()
    exportSelectionModeChanged = Signal(bool)
    selectedExportRecordIdsChanged = Signal()
    selectedExportCountChanged = Signal(int)
    totalCountChanged = Signal(int)
    currentPageChanged = Signal(int)
    pageSizeChanged = Signal(int)
    searchTermChanged = Signal(str)
    selectedRecordIdChanged = Signal(object)
    selectedRowIndexChanged = Signal(int)
    selectedRowDataChanged = Signal()
    errorMessageChanged = Signal(str)
    sortChanged = Signal(str, str)
    sortFieldChanged = Signal(str)
    sortDirectionChanged = Signal(str)
    sortLabelChanged = Signal(str)
    sortOptionsChanged = Signal()
    pageStateChanged = Signal()
    loadStarted = Signal(int)
    loadFinished = Signal(int, bool)

    def __init__(
        self,
        view_definition: CatalogViewDefinition,
        query_service: ModeloCatalogQueryService,
        catalog_service: ModeloCatalogService,
        form_host: FormHostViewModel,
        *,
        table_preferences_store: CatalogTablePreferencesStore | None = None,
        load_runner: CatalogLoadRunner | None = None,
        delete_handler=None,
        export_handler: Callable[[Sequence[int], str], str] | None = None,
    ) -> None:
        super().__init__()
        self._definition = view_definition
        self._query_service = query_service
        self._catalog_service = catalog_service
        self._form_host = form_host
        self._table_model = CatalogTableModel()
        self._table_preferences_store = table_preferences_store or InMemoryCatalogTablePreferencesStore()
        self._filters: tuple[CatalogFilter, ...] = ()
        self._filter_state_by_field: dict[str, dict[str, Any]] = {}
        self._total_count = 0
        self._current_page = 0
        self._page_size = view_definition.page_size
        self._search_term = ""
        self._selected_record_id: int | None = None
        self._selected_row_index = -1
        self._selected_row_data: dict[str, Any] | None = None
        self._error_message = ""
        self._sort = view_definition.default_sort
        self._rows_cache: list[dict[str, Any]] = []
        self._display_rows_cache: list[tuple[str, ...]] = []
        self._display_column_keys: tuple[str, ...] = ()
        self._dynamic_column_keys: tuple[str, ...] = ()
        self._latest_requested_id = 0
        self._latest_applied_id = 0
        self._pending_request_ids: set[int] = set()
        self._has_loaded_once = False
        self._load_runner = load_runner or QtThreadPoolCatalogLoadRunner(query_service)
        self._column_width_overrides = self._table_preferences_store.load_column_widths(
            self._definition.catalog_name
        )
        self._delete_handler = delete_handler
        self._export_handler = export_handler
        self._export_selection_mode = False
        self._selected_export_record_ids: list[int] = []

        self._form_host.formSaved.connect(self._handle_form_saved)

    @Slot()
    def dispose(self) -> None:
        if getattr(self, "_disposed", False):
            return
        if self._pending_request_ids:
            QThreadPool.globalInstance().waitForDone(5000)
            QCoreApplication.processEvents()
        try:
            self._form_host.formSaved.disconnect(self._handle_form_saved)
        except TypeError:
            pass
        self._pending_request_ids.clear()
        self._refresh_busy_state()
        self._form_host.close_form()
        self._form_host.deleteLater()
        self._table_model.deleteLater()
        super().dispose()

    @Property(CatalogTableModel, notify=tableModelChanged)
    def table_model(self) -> CatalogTableModel:
        return self._table_model

    @Property(FormHostViewModel, notify=formHostChanged)
    def form_host(self) -> FormHostViewModel:
        return self._form_host

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        return self._definition.title or self._definition.catalog_name.replace("_", " ").title()

    @Property(str, notify=catalogNameChanged)
    def catalog_name(self) -> str:
        return self._definition.catalog_name

    @Property(str, notify=searchFieldChanged)
    def search_field(self) -> str:
        return self._definition.search_field or ""

    @Property("QVariantList", notify=searchFieldsChanged)
    def search_fields(self) -> list[str]:
        return list(self._definition.search_fields)

    @Property(str, notify=searchPlaceholderChanged)
    def search_placeholder(self) -> str:
        return self._definition.search_placeholder or "Buscar"

    @Property(str, notify=searchTermChanged)
    def search_term(self) -> str:
        return self._search_term

    @Property("QVariantList", notify=filterFieldsChanged)
    def available_filter_fields(self) -> list[dict[str, Any]]:
        return [self._serialize_filter_field(field_schema) for field_schema in self._definition.schema_fields if field_schema.filterable]

    @Property("QVariantList", notify=activeFiltersChanged)
    def active_filters(self) -> list[dict[str, Any]]:
        return [dict(filter_map) for filter_map in self._filter_state_by_field.values() if not filter_map.get("is_hidden", False)]

    @Property("QVariantList", notify=columnsChanged)
    def columns(self) -> list[dict[str, Any]]:
        return self._resolved_columns()

    @Property(int, notify=totalCountChanged)
    def total_count(self) -> int:
        return self._total_count

    @Property(int, notify=currentPageChanged)
    def current_page(self) -> int:
        return self._current_page

    @Property(int, notify=pageSizeChanged)
    def page_size(self) -> int:
        return self._page_size

    @Property(object, notify=selectedRecordIdChanged)
    def selected_record_id(self) -> object:
        return self._selected_record_id

    @Property(int, notify=selectedRowIndexChanged)
    def selected_row_index(self) -> int:
        return self._selected_row_index

    @Property("QVariantMap", notify=selectedRowDataChanged)
    def selected_row_data(self) -> object:
        if self._selected_row_data is None:
            return {}
        return dict(self._selected_row_data)

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(bool, notify=canCreateChanged)
    def can_create(self) -> bool:
        return bool(self._definition.permissions.get("create", True))

    @Property(bool, notify=canEditChanged)
    def can_edit(self) -> bool:
        return bool(self._definition.permissions.get("edit", True))

    @Property(bool, notify=canDeleteChanged)
    def can_delete(self) -> bool:
        return bool(self._definition.permissions.get("delete", True))

    @Property(bool, notify=canExportChanged)
    def can_export(self) -> bool:
        return self._export_handler is not None

    @Property(bool, notify=exportSelectionModeChanged)
    def export_selection_mode(self) -> bool:
        return self._export_selection_mode

    @Property("QVariantList", notify=selectedExportRecordIdsChanged)
    def selected_export_record_ids(self) -> list[int]:
        return list(self._selected_export_record_ids)

    @Property(int, notify=selectedExportCountChanged)
    def selected_export_count(self) -> int:
        return len(self._selected_export_record_ids)

    @Property(str, notify=sortFieldChanged)
    def sort_field(self) -> str:
        return self._sort.field or ""

    @Property(str, notify=sortDirectionChanged)
    def sort_direction(self) -> str:
        return self._sort.direction.value

    @Property(str, notify=sortLabelChanged)
    def sort_label(self) -> str:
        return self._sort_label(self._sort)

    @Property("QVariantList", notify=sortOptionsChanged)
    def sort_options(self) -> list[dict[str, str]]:
        return [
            {"label": "Más recientes", "field": "id", "direction": CatalogSortDirection.DESC.value},
            {"label": "Más antiguos", "field": "id", "direction": CatalogSortDirection.ASC.value},
        ]

    @Property(bool, notify=pageStateChanged)
    def has_next_page(self) -> bool:
        return (self._current_page + 1) * self._page_size < self._total_count

    @Property(bool, notify=pageStateChanged)
    def has_prev_page(self) -> bool:
        return self._current_page > 0

    @property
    def filters(self) -> tuple[CatalogFilter, ...]:
        return self._filters

    @property
    def sort(self) -> CatalogSort:
        return self._sort

    @property
    def view_definition(self) -> CatalogViewDefinition:
        return self._definition

    def set_permissions(self, permissions: Mapping[str, bool]) -> None:
        normalized = {
            "create": bool(permissions.get("create", False)),
            "edit": bool(permissions.get("edit", False)),
            "delete": bool(permissions.get("delete", False)),
        }
        if dict(self._definition.permissions) == normalized:
            return
        self._definition = CatalogViewDefinition(
            catalog_name=self._definition.catalog_name,
            title=self._definition.title,
            columns=self._definition.columns,
            qml_component=self._definition.qml_component,
            form_id=self._definition.form_id,
            page_size=self._definition.page_size,
            default_sort=self._definition.default_sort,
            search_field=self._definition.search_field,
            search_fields=self._definition.search_fields,
            search_placeholder=self._definition.search_placeholder,
            permissions=normalized,
            schema_fields=self._definition.schema_fields,
            generic_form_fields=self._definition.generic_form_fields,
            form_layout=self._definition.form_layout,
            form_context=self._definition.form_context,
        )
        self.canCreateChanged.emit()
        self.canEditChanged.emit()
        self.canDeleteChanged.emit()
        self.columnsChanged.emit()

    def load(self) -> int:
        request_id = self._next_request_id()
        request = CatalogLoadRequest(
            request_id=request_id,
            query=CatalogQueryRequest(
                catalog_name=self._definition.catalog_name,
                page=self._current_page,
                page_size=self._page_size,
                sort=self._sort,
                search_text=self._search_term or None,
                search_fields=self._definition.search_fields,
                filters=self._filters,
            ),
            column_keys=self._requested_column_keys(),
        )
        self._prepare_load_dispatch(request_id)
        try:
            self._load_runner.submit(
                request,
                self._handle_load_success,
                self._handle_load_failure,
            )
        except Exception:
            self._pending_request_ids.discard(request_id)
            self._refresh_busy_state()
            self.loadFinished.emit(request_id, False)
            raise
        return request_id

    def refresh(self) -> int:
        return self.load()

    def set_page(self, page: int) -> int:
        if page < 0:
            page = 0
        self._set_current_page(page)
        return self.load()

    def next_page(self) -> int | None:
        if (self._current_page + 1) * self._page_size >= self._total_count:
            return None
        return self.set_page(self._current_page + 1)

    def prev_page(self) -> int | None:
        if self._current_page <= 0:
            return None
        return self.set_page(self._current_page - 1)

    def set_filters(self, filters: tuple[CatalogFilter, ...] | list[CatalogFilter]) -> int:
        self._filters = tuple(filters)
        self._sync_filter_states_from_specs(self._filters)
        self._set_current_page(0)
        return self.load()

    def clear_filters(self) -> int:
        self._filters = ()
        self._filter_state_by_field = {}
        self.activeFiltersChanged.emit()
        self._set_current_page(0)
        return self.load()

    def set_sort(self, sort: CatalogSort) -> int:
        self._sort = sort
        self._set_current_page(0)
        self._emit_sort_changed()
        return self.load()

    def select_record(self, record_id: int | None) -> None:
        if self._selected_record_id != record_id:
            self._selected_record_id = record_id
            self.selectedRecordIdChanged.emit(record_id)
        row_index = -1
        if record_id is not None:
            for index, row in enumerate(self._rows_cache):
                if row.get("id") == record_id:
                    row_index = index
                    break
        self._set_selected_row_index(row_index)

    def open_create(self):
        if not self.can_create:
            self._set_permission_denied("crear")
            return None
        return self._form_host.open_form(
            self._definition.catalog_name,
            mode=FormMode.CREATE,
            preferred_form_id=self._definition.form_id,
            context=self._build_form_context(),
        )

    def open_edit(self, record_id: int | None = None):
        if not self.can_edit:
            self._set_permission_denied("modificar")
            return None
        target_id = record_id if record_id is not None else self._selected_record_id
        if target_id is None:
            raise ValueError("record_id es requerido para editar")
        return self._form_host.open_form(
            self._definition.catalog_name,
            mode=FormMode.EDIT,
            record_id=int(target_id),
            preferred_form_id=self._definition.form_id,
            context=self._build_form_context(record_id=int(target_id)),
        )

    def open_detail(self, record_id: int | None = None):
        target_id = record_id if record_id is not None else self._selected_record_id
        if target_id is None:
            raise ValueError("record_id es requerido para ver detalle")
        return self._form_host.open_form(
            self._definition.catalog_name,
            mode=FormMode.VIEW,
            record_id=int(target_id),
            preferred_form_id=self._definition.form_id,
            context=self._build_form_context(record_id=int(target_id)),
        )

    def close_form(self) -> None:
        self._form_host.close_form()

    def reset_transient_state(self) -> None:
        """Clear navigation/form state while preserving user filters."""
        self.close_form()
        self.select_record(None)
        self.cancel_export_selection()
        self._set_search_term("")
        self._set_current_page(0)
        if self._sort != self._definition.default_sort:
            self._sort = self._definition.default_sort
            self._emit_sort_changed()
        self._set_error_message("")

    def delete_record(self, record_id: int | None = None) -> bool:
        if not self.can_delete:
            self._set_permission_denied("eliminar")
            return False
        target_id = record_id if record_id is not None else self._selected_record_id
        if target_id is None:
            raise ValueError("record_id es requerido para eliminar")
        if self._delete_handler is not None:
            deleted = bool(self._delete_handler(int(target_id)))
        else:
            deleted = self._catalog_service.delete(self._definition.catalog_name, int(target_id))
        self.refresh()
        return deleted

    def begin_export_selection(self) -> None:
        if not self.can_export:
            self._set_error_message("Exportacion de Excel no disponible para este catalogo")
            return
        self._set_error_message("")
        self._set_export_selection_mode(True)

    def cancel_export_selection(self) -> None:
        self._set_export_selection_mode(False)
        self._set_selected_export_record_ids([])

    def toggle_export_record(self, record_id: int, selected: bool) -> None:
        normalized_id = int(record_id)
        if normalized_id < 0:
            return
        selected_ids = list(self._selected_export_record_ids)
        if selected:
            if normalized_id not in selected_ids:
                selected_ids.append(normalized_id)
        else:
            selected_ids = [item for item in selected_ids if item != normalized_id]
        self._set_selected_export_record_ids(selected_ids)

    def export_selected(self, target_path: str) -> bool:
        if not self._selected_export_record_ids:
            self._set_error_message("Selecciona al menos una factura para exportar")
            return False
        exported = self._export_records(self._selected_export_record_ids, target_path)
        if exported:
            self.cancel_export_selection()
        return exported

    def export_record(self, record_id: int, target_path: str) -> bool:
        return self._export_records([int(record_id)], target_path)

    def _export_records(self, record_ids: Sequence[int], target_path: str) -> bool:
        if self._export_handler is None:
            self._set_error_message("Exportacion de Excel no disponible para este catalogo")
            return False
        normalized_path = str(target_path or "").strip()
        if not normalized_path:
            self._set_error_message("Selecciona una ruta para exportar")
            return False
        try:
            self._set_error_message("")
            self._export_handler([int(record_id) for record_id in record_ids], normalized_path)
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

    def _set_export_selection_mode(self, value: bool) -> None:
        normalized = bool(value)
        if self._export_selection_mode != normalized:
            self._export_selection_mode = normalized
            self.exportSelectionModeChanged.emit(normalized)

    def _set_selected_export_record_ids(self, record_ids: Sequence[int]) -> None:
        normalized: list[int] = []
        seen: set[int] = set()
        for record_id in record_ids:
            item = int(record_id)
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        if self._selected_export_record_ids != normalized:
            self._selected_export_record_ids = normalized
            self.selectedExportRecordIdsChanged.emit()
            self.selectedExportCountChanged.emit(len(normalized))

    def _set_permission_denied(self, action: str) -> None:
        self._set_error_message(f"No tienes permiso para {action} {self._definition.catalog_name}")

    def _build_form_context(self, **extra: Any) -> dict[str, Any]:
        context = {"view_definition": self._definition}
        context.update(dict(self._definition.form_context))
        context.update(extra)
        return context

    def _handle_form_saved(self, payload: dict[str, Any]) -> None:
        saved_id = payload.get("id")
        saved_from_mode = str(payload.get("__form_mode") or "").strip().lower()
        if saved_id is not None:
            self.select_record(int(saved_id))
        if saved_id is not None and saved_from_mode == FormMode.CREATE.value:
            target_page = self._try_locate_record_page(int(saved_id))
            if target_page is not None:
                self._set_current_page(target_page)
                self.load()
                return
        self.refresh()

    def _next_request_id(self) -> int:
        return self._latest_requested_id + 1

    def _requested_column_keys(self) -> tuple[str, ...]:
        if self._definition.columns:
            return tuple(column.key for column in self._definition.columns)
        return tuple(self._dynamic_column_keys)

    def _prepare_load_dispatch(self, request_id: int) -> None:
        self._latest_requested_id = request_id
        self._pending_request_ids.add(request_id)
        self._set_error_message("")
        if not self._has_loaded_once:
            self._clear_rows_for_initial_load()
        self.loadStarted.emit(request_id)
        self._refresh_busy_state()

    def _handle_load_success(self, result: CatalogLoadResult) -> None:
        self._pending_request_ids.discard(result.request_id)
        applied = result.request_id == self._latest_requested_id
        if applied:
            self._apply_load_result(result)
        self._refresh_busy_state()
        self.loadFinished.emit(result.request_id, applied)

    def _handle_load_failure(self, failure: CatalogLoadFailure) -> None:
        self._pending_request_ids.discard(failure.request_id)
        applied = failure.request_id == self._latest_requested_id
        if applied:
            self._set_error_message(failure.message)
        self._refresh_busy_state()
        self.loadFinished.emit(failure.request_id, applied)

    def _apply_load_result(self, result: CatalogLoadResult) -> None:
        if not self._definition.columns and result.column_keys:
            self._dynamic_column_keys = tuple(result.column_keys)
        self._latest_applied_id = result.request_id
        self._has_loaded_once = True
        self._set_error_message("")
        self._sync_rows_cache(
            list(result.rows),
            display_rows=list(result.display_rows),
            display_column_keys=tuple(result.column_keys),
        )
        self._set_total_count(result.total_count)
        self.pageStateChanged.emit()

    def _refresh_busy_state(self) -> None:
        self.is_busy = self._latest_requested_id in self._pending_request_ids

    def _clear_rows_for_initial_load(self) -> None:
        if not self._definition.columns:
            self._dynamic_column_keys = ()
        self._sync_rows_cache([], display_rows=[], display_column_keys=self._requested_column_keys())
        self._set_total_count(0)
        self.pageStateChanged.emit()

    def _set_total_count(self, total_count: int) -> None:
        total_count = int(total_count)
        if self._total_count != total_count:
            self._total_count = total_count
            self.totalCountChanged.emit(total_count)
            self.pageStateChanged.emit()

    def _set_current_page(self, page: int) -> None:
        page = int(page)
        if self._current_page != page:
            self._current_page = page
            self.currentPageChanged.emit(page)
            self.pageStateChanged.emit()

    def _set_search_term(self, value: str) -> None:
        value = str(value or "")
        if self._search_term != value:
            self._search_term = value
            self.searchTermChanged.emit(value)

    def _set_error_message(self, message: str) -> None:
        message = str(message or "")
        if self._error_message != message:
            self._error_message = message
            self.errorMessageChanged.emit(message)

    def _emit_sort_changed(self) -> None:
        self.sortChanged.emit(self._sort.field or "", self._sort.direction.value)
        self.sortFieldChanged.emit(self._sort.field or "")
        self.sortDirectionChanged.emit(self._sort.direction.value)
        self.sortLabelChanged.emit(self.sort_label)

    def _sort_label(self, sort: CatalogSort) -> str:
        field_name = str(sort.field or "").strip()
        direction = sort.direction
        if field_name == "id":
            if direction == CatalogSortDirection.DESC:
                return "Más recientes"
            if direction == CatalogSortDirection.ASC:
                return "Más antiguos"
        label = self._field_schema(field_name).label if field_name else ""
        arrow = "↑" if direction == CatalogSortDirection.ASC else "↓"
        return f"{label} {arrow}".strip()

    def _set_selected_row_index(self, row_index: int) -> None:
        row_index = int(row_index)
        if self._selected_row_index != row_index:
            self._selected_row_index = row_index
            self.selectedRowIndexChanged.emit(row_index)
        self._set_selected_row_data(self._row_data_for_index(row_index))

    def _set_selected_row_data(self, value: dict[str, Any] | None) -> None:
        normalized = None if value is None else dict(value)
        if self._selected_row_data != normalized:
            self._selected_row_data = normalized
            self.selectedRowDataChanged.emit()

    def _sync_rows_cache(
        self,
        rows: list[dict[str, Any]],
        *,
        display_rows: list[tuple[str, ...]],
        display_column_keys: tuple[str, ...],
    ) -> None:
        display_column_keys, display_rows = self._resolve_presentation_rows(
            rows,
            display_rows=display_rows,
            display_column_keys=display_column_keys,
        )
        self._rows_cache = [dict(row) for row in rows]
        self._display_rows_cache = [tuple(display_row) for display_row in display_rows]
        self._display_column_keys = tuple(display_column_keys)
        if self._selected_record_id is not None:
            for index, row in enumerate(self._rows_cache):
                if row.get("id") == self._selected_record_id:
                    self._set_selected_row_index(index)
                    break
            else:
                self.select_record(None)
        else:
            self._set_selected_row_index(-1)
        self._refresh_table_model()
        self.columnsChanged.emit()

    def _refresh_table_model(self) -> None:
        self._table_model.set_table(
            self._rows_cache,
            self._resolved_columns(),
            self._display_rows_cache,
            self._display_column_keys,
        )

    def _resolved_columns(self) -> list[dict[str, Any]]:
        columns = self._resolved_data_columns()
        columns.append(
            {
                "key": _ACTION_COLUMN_KEY,
                "header": "Acciones",
                "width": _ACTION_COLUMN_WIDTH,
                "minWidth": _ACTION_COLUMN_MIN_WIDTH,
                "sortable": False,
                "resizable": False,
                "kind": "actions",
            }
        )
        return columns

    def _resolved_data_columns(self) -> list[dict[str, Any]]:
        if self._definition.columns:
            return [
                self._serialize_column(column)
                for column in self._definition.columns
                if not self._is_currency_column(column.key)
            ]
        if self._dynamic_column_keys:
            columns: list[dict[str, Any]] = []
            for key in self._dynamic_column_keys:
                if self._is_currency_column(key):
                    continue
                columns.append(
                    {
                        "key": key,
                        "header": key.replace("_", " ").title(),
                        "width": self._column_width_overrides.get(key, 160),
                        "minWidth": 96,
                        "sortable": True,
                        "resizable": True,
                        "kind": "data",
                    }
                )
            return columns
        return []

    def _resolve_presentation_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        display_rows: list[tuple[str, ...]],
        display_column_keys: tuple[str, ...],
    ) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
        visible_keys = tuple(key for key in display_column_keys if not self._is_currency_column(key))
        if visible_keys == display_column_keys:
            display_index = {key: index for index, key in enumerate(display_column_keys)}
            resolved_rows: list[tuple[str, ...]] = []
            for row_index, row in enumerate(rows):
                source_display_row = display_rows[row_index] if row_index < len(display_rows) else ()
                values: list[str] = []
                for key in visible_keys:
                    if self._is_money_column(key):
                        values.append(display_money_value(row.get(key), self._currency_for_money(row, key)))
                        continue
                    source_index = display_index.get(key)
                    if source_index is not None and source_index < len(source_display_row):
                        values.append(source_display_row[source_index])
                    else:
                        values.append(display_catalog_value(row.get(key)))
                resolved_rows.append(tuple(values))
            return visible_keys, resolved_rows

        resolved_rows = [
            tuple(
                display_money_value(row.get(key), self._currency_for_money(row, key))
                if self._is_money_column(key)
                else display_catalog_value(row.get(key))
                for key in visible_keys
            )
            for row in rows
        ]
        return visible_keys, resolved_rows

    def _is_currency_column(self, field_name: str) -> bool:
        normalized = str(field_name or "").strip().lower()
        return normalized == "moneda" or normalized.endswith("_moneda")

    def _is_money_column(self, field_name: str) -> bool:
        normalized = str(field_name or "").strip().lower()
        normalized_without_prefix = normalized.lstrip("_")
        try:
            if self._field_schema(field_name).kind == FieldKind.MONEY:
                return True
        except Exception:
            pass
        return normalized_without_prefix in {
            "monto",
            "subtotal",
            "total",
            "saldo_restante",
            "saldo_disponible",
            "costo",
        }

    def _currency_for_money(self, row: Mapping[str, Any], field_name: str) -> Any:
        normalized = str(field_name or "").strip()
        if normalized.endswith("_monto"):
            paired_key = f"{normalized[:-6]}_moneda"
            if paired_key in row:
                return row.get(paired_key)
        return row.get("moneda")

    def _serialize_column(self, column) -> dict[str, Any]:
        width = self._column_width_overrides.get(column.key)
        resolved_width = int(width if width is not None else (column.width or 160))
        min_width = int(column.min_width or 96)
        if resolved_width < min_width:
            resolved_width = min_width
        return {
            "key": column.key,
            "header": column.header or column.key.replace("_", " ").title(),
            "width": resolved_width,
            "minWidth": min_width,
            "sortable": bool(column.sortable),
            "resizable": bool(column.resizable),
            "kind": "data",
        }

    def _row_data_for_index(self, row_index: int) -> dict[str, Any] | None:
        if row_index < 0 or row_index >= len(self._rows_cache):
            return None
        return dict(self._rows_cache[row_index])

    def _record_id_for_row_index(self, row_index: int) -> int | None:
        row = self._row_data_for_index(row_index)
        if row is None:
            return None
        record_id = row.get("id")
        return int(record_id) if isinstance(record_id, int) else None

    def _field_schema(self, field_name: str):
        normalized = str(field_name or "").strip()
        for field_schema in self._definition.schema_fields:
            if field_schema.name == normalized:
                return field_schema
        return FieldSchemaDTO(
            name=normalized,
            label=normalized.replace("_", " ").title(),
            kind=FieldKind.TEXT,
            filterable=True,
            searchable=normalized in self._definition.search_fields or normalized == self._definition.search_field,
            supported_operators=("contains", "eq"),
        )

    def _serialize_filter_field(self, field_schema) -> dict[str, Any]:
        reference = field_schema.reference
        return {
            "name": field_schema.name,
            "label": field_schema.label,
            "kind": "reference" if reference is not None else field_schema.kind.value,
            "searchable": bool(field_schema.searchable),
            "filterable": bool(field_schema.filterable),
            "multiValue": bool(field_schema.multi_value),
            "operators": [
                {"value": operator, "label": _operator_label(operator)}
                for operator in field_schema.supported_operators
            ],
            "options": [{"value": option.value, "label": option.label} for option in field_schema.options],
            "reference": None
            if reference is None
            else {
                "lookupKey": reference.lookup_key,
                "minSearchChars": int(reference.min_search_chars),
                "pageSize": int(reference.page_size),
                "valueField": reference.value_field,
                "labelField": reference.label_field,
            },
        }

    def _sync_filter_states_from_specs(self, filters: Sequence[CatalogFilter]) -> None:
        serialized: dict[str, dict[str, Any]] = {}
        for filter_spec in filters:
            field_schema = self._field_schema(filter_spec.field)
            serialized[field_schema.name] = self._serialize_filter_state(field_schema, filter_spec)
        self._filter_state_by_field = serialized
        self.activeFiltersChanged.emit()

    def _serialize_filter_state(
        self,
        field_schema,
        filter_spec: CatalogFilter,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_value = payload.get("value") if payload is not None and "value" in payload else filter_spec.value
        raw_value_to = payload.get("valueTo") if payload is not None and "valueTo" in payload else filter_spec.value_to
        return {
            "field": field_schema.name,
            "label": field_schema.label,
            "kind": "reference" if field_schema.reference is not None else field_schema.kind.value,
            "operator": filter_spec.operator.value,
            "operatorLabel": _operator_label(filter_spec.operator.value),
            "value": raw_value,
            "valueTo": raw_value_to,
            "displayValue": self._display_filter_value(field_schema, filter_spec.operator, raw_value, raw_value_to),
            "is_hidden": filter_spec.is_hidden
        }

    def _display_filter_value(
        self,
        field_schema,
        operator: CatalogFilterOperator,
        value: Any,
        value_to: Any,
    ) -> str:
        if operator == CatalogFilterOperator.BETWEEN:
            left = self._display_single_filter_value(field_schema, value)
            right = self._display_single_filter_value(field_schema, value_to)
            return f"{left} -> {right}".strip()
        return self._display_single_filter_value(field_schema, value)

    def _display_single_filter_value(self, field_schema, value: Any) -> str:
        if isinstance(value, Mapping):
            label = value.get("label")
            if label is not None:
                return str(label)
            if "id" in value:
                return str(value["id"])
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return ", ".join(
                self._display_single_filter_value(field_schema, item)
                for item in value
                if item not in (None, "")
            )
        if field_schema.reference is not None:
            return "" if value in (None, "") else str(value)
        if field_schema.kind.value == "bool":
            if value is True:
                return "Si"
            if value is False:
                return "No"
            return "Todos"
        option_labels = {option.value: option.label for option in field_schema.options}
        if value in option_labels:
            return str(option_labels[value])
        return "" if value in (None, "") else str(value)

    def _replace_filter(self, filter_spec: CatalogFilter, *, payload: Mapping[str, Any] | None = None) -> int:
        updated_filters = [existing for existing in self._filters if existing.field != filter_spec.field]
        updated_filters.append(filter_spec)
        self._filters = tuple(updated_filters)
        field_schema = self._field_schema(filter_spec.field)
        self._filter_state_by_field[field_schema.name] = self._serialize_filter_state(field_schema, filter_spec, payload)
        self.activeFiltersChanged.emit()
        self._set_current_page(0)
        return self.load()

    def _remove_filter(self, field_name: str) -> int:
        normalized = str(field_name or "").strip()
        self._filters = tuple(filter_spec for filter_spec in self._filters if filter_spec.field != normalized)
        self._filter_state_by_field.pop(normalized, None)
        self.activeFiltersChanged.emit()
        self._set_current_page(0)
        return self.load()

    def _build_filter_from_payload(self, payload: Mapping[str, Any]) -> tuple[CatalogFilter | None, str]:
        field_name = str(payload.get("field") or "").strip()
        if not field_name:
            raise ValueError("field es requerido")
        field_schema = self._field_schema(field_name)
        supported_operators = tuple(field_schema.supported_operators or ("eq",))
        operator_name = str(payload.get("operator") or supported_operators[0]).strip().lower()
        if operator_name not in supported_operators:
            raise ValueError(f"Operador no soportado para {field_schema.label}: {operator_name}")
        operator = CatalogFilterOperator(operator_name)
        value = payload.get("value")
        value_to = payload.get("valueTo")
        if field_schema.multi_value and isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            normalized_values = [item for item in value if item not in (None, "")]
            if operator == CatalogFilterOperator.EQ:
                if len(normalized_values) > 1:
                    operator = CatalogFilterOperator.IN
                    value = normalized_values
                elif len(normalized_values) == 1:
                    value = normalized_values[0]
                else:
                    value = None
        if self._is_empty_filter_value(operator, value, value_to):
            return None, field_name
        return CatalogFilter(field=field_name, operator=operator, value=value, value_to=value_to), field_name

    @staticmethod
    def _is_empty_filter_value(
        operator: CatalogFilterOperator,
        value: Any,
        value_to: Any,
    ) -> bool:
        if operator == CatalogFilterOperator.BETWEEN:
            return value in (None, "") or value_to in (None, "")
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            return len(value) == 0
        return value in (None, "")

    def _call_with_error_capture(self, action) -> bool:
        try:
            self._set_error_message("")
            action()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

    def _try_locate_record_page(self, record_id: int) -> int | None:
        try:
            return self._query_service.locate_record_page(
                self._definition.catalog_name,
                int(record_id),
                page_size=self._page_size,
                sort=self._sort,
                search_text=self._search_term or None,
                search_fields=self._definition.search_fields,
                filters=self._filters,
            )
        except Exception:
            return None

    @Slot()
    def load_screen(self) -> None:
        self._call_with_error_capture(self.load)

    @Slot()
    def refresh_data(self) -> None:
        self._call_with_error_capture(self.refresh)

    @Slot(int)
    def set_page_index(self, page: int) -> None:
        self._call_with_error_capture(lambda: self.set_page(int(page)))

    @Slot()
    def next_page_slot(self) -> None:
        self._call_with_error_capture(lambda: self.next_page())

    @Slot()
    def prev_page_slot(self) -> None:
        self._call_with_error_capture(lambda: self.prev_page())

    @Slot(int)
    def select_row_index(self, row_index: int) -> None:
        row_index = int(row_index)
        if row_index < 0 or row_index >= len(self._rows_cache):
            self.select_record(None)
            return
        record_id = self._record_id_for_row_index(row_index)
        if record_id is not None:
            self.select_record(record_id)
        else:
            self._set_selected_row_index(row_index)

    @Slot(int)
    def select_record_by_id(self, record_id: int) -> None:
        self.select_record(int(record_id))

    @Slot(str)
    def apply_search(self, term: str) -> int | None:
        term = str(term or "").strip()
        self._set_search_term(term)
        if not self._definition.search_fields:
            return None
        self._set_current_page(0)
        return self.load()

    @Slot()
    def clear_search(self) -> int:
        self._set_search_term("")
        self._set_current_page(0)
        return self.load()

    @Slot(dict, result=bool)
    def apply_filter_payload(self, payload: object) -> bool:
        if not isinstance(payload, Mapping):
            self._set_error_message("Se requiere un filtro valido.")
            return False
        return self._call_with_error_capture(lambda: self._apply_filter_payload_internal(payload))

    def _apply_filter_payload_internal(self, payload: Mapping[str, Any]) -> int:
        filter_spec, field_name = self._build_filter_from_payload(payload)
        if filter_spec is None:
            return self._remove_filter(field_name)
        return self._replace_filter(filter_spec, payload=payload)

    @Slot(str, result=bool)
    def remove_filter(self, field_name: str) -> bool:
        return self._call_with_error_capture(lambda: self._remove_filter(field_name))

    @Slot(str, str, result=list)
    def reference_options(self, field_name: str, term: str) -> list[dict[str, Any]]:
        try:
            return self._query_service.lookup_reference_options(
                self._definition.catalog_name,
                field_name,
                term,
            )
        except Exception as exc:
            self._set_error_message(str(exc))
            return []

    @Slot(str, str, result=list)
    def relation_options(self, field_name: str, term: str) -> list[dict[str, Any]]:
        return self.reference_options(field_name, term)

    @Slot(str)
    def toggle_sort(self, field_name: str) -> int | None:
        field_name = str(field_name or "").strip()
        if not field_name or field_name == _ACTION_COLUMN_KEY:
            return None
        direction = CatalogSortDirection.ASC
        if self._sort.field == field_name and self._sort.direction == CatalogSortDirection.ASC:
            direction = CatalogSortDirection.DESC
        return self.set_sort(CatalogSort(field=field_name, direction=direction))

    @Slot(dict, result=bool)
    def apply_sort_payload(self, payload: object) -> bool:
        if not isinstance(payload, Mapping):
            self._set_error_message("Se requiere un orden valido.")
            return False
        return self._call_with_error_capture(lambda: self._apply_sort_payload_internal(payload))

    def _apply_sort_payload_internal(self, payload: Mapping[str, Any]) -> int:
        field_name = str(payload.get("field") or "").strip()
        direction_name = str(payload.get("direction") or "").strip().lower()
        if not field_name:
            raise ValueError("field es requerido")
        if direction_name not in {CatalogSortDirection.ASC.value, CatalogSortDirection.DESC.value}:
            raise ValueError("direction debe ser asc o desc")
        return self.set_sort(CatalogSort(field=field_name, direction=CatalogSortDirection(direction_name)))

    @Slot(str, int)
    def set_column_width(self, field_name: str, width: int) -> None:
        normalized_key = str(field_name or "").strip()
        if not normalized_key or normalized_key == _ACTION_COLUMN_KEY:
            return
        column_map = {column["key"]: column for column in self._resolved_data_columns()}
        column = column_map.get(normalized_key)
        if column is None or not bool(column.get("resizable", True)):
            return
        min_width = int(column.get("minWidth", 96))
        normalized_width = max(int(width), min_width)
        current_width = int(column.get("width", min_width))
        if current_width == normalized_width:
            return
        self._column_width_overrides[normalized_key] = normalized_width
        self._table_preferences_store.save_column_width(self._definition.catalog_name, normalized_key, normalized_width)
        self.columnsChanged.emit()

    @Slot(int, result=object)
    def column_at(self, column_index: int) -> dict[str, Any]:
        columns = self._resolved_columns()
        if column_index < 0 or column_index >= len(columns):
            return {}
        return dict(columns[column_index])

    @Slot(int, result=int)
    def column_width_at(self, column_index: int) -> int:
        column = self.column_at(column_index)
        if not column:
            return 0
        return int(column.get("width", 0))

    @Slot(int, result=object)
    def row_data_at(self, row_index: int) -> dict[str, Any]:
        row = self._row_data_for_index(row_index)
        return {} if row is None else dict(row)

    @Slot(int, result=int)
    def record_id_at_row(self, row_index: int) -> int:
        record_id = self._record_id_for_row_index(row_index)
        return -1 if record_id is None else int(record_id)

    @Slot(result=bool)
    def open_create_form(self) -> bool:
        return self._call_with_error_capture(self.open_create)

    @Slot(result=bool)
    def open_selected_form(self) -> bool:
        return self._call_with_error_capture(self.open_edit)

    @Slot(int, result=bool)
    def open_record_form(self, record_id: int) -> bool:
        return self._call_with_error_capture(lambda: self.open_edit(int(record_id)))

    @Slot(int, result=bool)
    def open_record_detail(self, record_id: int) -> bool:
        return self._call_with_error_capture(lambda: self.open_detail(int(record_id)))

    @Slot(int, result=bool)
    def open_row_form_by_index(self, row_index: int) -> bool:
        return self._call_with_error_capture(
            lambda: self.open_edit(self._required_record_id_for_row_index(int(row_index)))
        )

    @Slot(int, result=bool)
    def open_row_detail_by_index(self, row_index: int) -> bool:
        return self._call_with_error_capture(
            lambda: self.open_detail(self._required_record_id_for_row_index(int(row_index)))
        )

    @Slot()
    def close_active_form(self) -> None:
        self.close_form()

    @Slot()
    def reset_transient_state_slot(self) -> None:
        self.reset_transient_state()

    @Slot(result=bool)
    def delete_selected_record(self) -> bool:
        return self._call_with_error_capture(self.delete_record)

    @Slot(int, result=bool)
    def delete_record_by_id(self, record_id: int) -> bool:
        return self._call_with_error_capture(lambda: self.delete_record(int(record_id)))

    @Slot(int, result=bool)
    def delete_row_by_index(self, row_index: int) -> bool:
        return self._call_with_error_capture(
            lambda: self.delete_record(self._required_record_id_for_row_index(int(row_index)))
        )

    @Slot()
    def begin_export_selection_slot(self) -> None:
        self.begin_export_selection()

    @Slot()
    def cancel_export_selection_slot(self) -> None:
        self.cancel_export_selection()

    @Slot(int, int)
    def toggle_export_record_id(self, record_id: int, selected: int) -> None:
        self.toggle_export_record(int(record_id), bool(selected))

    @Slot(int, result=bool)
    def is_record_selected_for_export(self, record_id: int) -> bool:
        return int(record_id) in self._selected_export_record_ids

    @Slot(str, result=bool)
    def export_selected_records(self, target_path: str) -> bool:
        return self.export_selected(str(target_path))

    @Slot(int, str, result=bool)
    def export_record_by_id(self, record_id: int, target_path: str) -> bool:
        return self.export_record(int(record_id), str(target_path))

    def _required_record_id_for_row_index(self, row_index: int) -> int:
        record_id = self._record_id_for_row_index(row_index)
        if record_id is None:
            raise ValueError("record_id es requerido para la fila seleccionada")
        return record_id
