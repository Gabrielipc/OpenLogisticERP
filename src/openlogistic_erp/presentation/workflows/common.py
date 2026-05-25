"""Shared workflow presentation primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ...application.modelo.reference_service import ReferenceLookupService
from ...application.modelo.services import ModeloCatalogService, ModeloWorkflowService
from ...domain.modelo.field_validation import normalize_field_value
from ...infrastructure.persistence.modelo.workflow_orm import Moneda, parse_money, q4
from ..catalog.forms import BaseFormViewModel
from ..catalog.serialization import display_money_value
from ..qt import Property, QAbstractTableModel, QmlNamedElement, QmlUncreatable, QModelIndex, Qt, Signal, Slot
from ..viewmodels.base_view_model import BaseViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@dataclass(frozen=True)
class WorkflowDescriptor:
    module_id: str
    title: str
    domain_title: str
    summary: str
    qml_component: str


@dataclass(frozen=True)
class WorkflowLookupField:
    name: str
    search: Any
    resolve: Any
    bound_field_name: str | None = None


@QmlNamedElement("WorkflowModuleViewModel")
@QmlUncreatable("WorkflowModuleViewModel instances are created in Python and injected into QML.")
class WorkflowModuleViewModel(BaseViewModel):
    titleChanged = Signal()
    moduleIdChanged = Signal(str)
    domainTitleChanged = Signal(str)
    summaryChanged = Signal(str)
    qmlComponentChanged = Signal(str)

    def __init__(self, descriptor: WorkflowDescriptor) -> None:
        super().__init__()
        self._descriptor = descriptor

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        return self._descriptor.title

    @Property(str, notify=moduleIdChanged)
    def module_id(self) -> str:
        return self._descriptor.module_id

    @Property(str, notify=domainTitleChanged)
    def domain_title(self) -> str:
        return self._descriptor.domain_title

    @Property(str, notify=summaryChanged)
    def summary(self) -> str:
        return self._descriptor.summary

    @Property(str, notify=qmlComponentChanged)
    def qml_component(self) -> str:
        return self._descriptor.qml_component


def _as_decimal(value: Any, *, places: int = 2) -> Decimal:
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, AttributeError):
            decimal_value = Decimal("0")
    quantum = Decimal("1").scaleb(-places)
    return decimal_value.quantize(quantum)


def _money_text(value: Any) -> str:
    return format(_as_decimal(value, places=2), ".2f")


def _money_display_text(value: Any, currency: Any) -> str:
    return display_money_value(_money_text(value), _invoice_currency_value(currency))


def _rate_text(value: Any) -> str:
    return format(_as_decimal(value, places=4), ".4f")


def _normalize_money_input(value: Any, *, required: bool = True) -> Decimal:
    normalized = normalize_field_value(
        kind="money",
        value=value,
        required=required,
        nullable=not required,
    )
    return parse_money(normalized)


def _normalize_rate_input(value: Any) -> Decimal:
    normalized = normalize_field_value(
        kind="percent",
        value=value,
        required=True,
        nullable=False,
    )
    decimal_value = q4(normalized)
    if decimal_value <= Decimal("0"):
        raise ValueError("La tasa de cambio debe ser mayor que cero.")
    return decimal_value


def _normalize_int_input(value: Any, *, label: str) -> int:
    try:
        result = normalize_field_value(kind="integer", value=value, required=True, nullable=False)
        assert result is not None
        return int(result)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _normalize_datetime_input(value: Any, *, label: str) -> str:
    try:
        return str(normalize_field_value(kind="datetime", value=value, required=True, nullable=False))
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _normalize_reference_id(value: Any, *, label: str) -> int:
    try:
        result = normalize_field_value(kind="reference", value=value, required=True, nullable=False)
        assert result is not None 
        return int(result)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _cliente_lookup_options(
    reference_lookup_service: ReferenceLookupService | None,
    *,
    lookup_key: str,
    term: str,
) -> list[dict[str, Any]]:
    if reference_lookup_service is None:
        return []
    normalized_term = str(term or "").strip()
    if normalized_term and len(normalized_term) < 2:
        return []
    return [
        {"value": option.value, "label": option.label}
        for option in reference_lookup_service.search(lookup_key, normalized_term, limit=20)
        if option.value is not None
    ]


def _resolved_reference_option(
    reference_lookup_service: ReferenceLookupService | None,
    *,
    lookup_key: str,
    value: Any,
) -> list[dict[str, Any]]:
    if reference_lookup_service is None or value in (None, ""):
        return []
    resolved = reference_lookup_service.resolve_ids(lookup_key, [value])
    option = resolved.get(value)
    if option is None:
        return []
    return [{"value": option.value, "label": option.label}]


def _invoice_currency_value(currency: Any) -> str:
    if isinstance(currency, Moneda):
        return currency.value
    return str(currency or Moneda.NIO.value)


@QmlNamedElement("WorkflowFormViewModelBase")
@QmlUncreatable("WorkflowFormViewModelBase instances are created in Python and specialized by concrete workflow forms.")
class WorkflowFormViewModelBase(BaseFormViewModel):
    valuesChanged = Signal()
    fieldErrorsChanged = Signal()
    clientOptionsChanged = Signal()
    lookupOptionsChanged = Signal(str)

    def __init__(
        self,
        *,
        title: str,
        catalog_service: ModeloCatalogService,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        client_lookup_key: str,
    ) -> None:
        super().__init__(title=title)
        self._catalog_service = catalog_service
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._client_lookup_key = client_lookup_key
        self._values: dict[str, Any] = {}
        self._initial_values: dict[str, Any] = {}
        self._field_errors: dict[str, str] = {}
        self._lookup_fields: dict[str, WorkflowLookupField] = {}
        self._lookup_options: dict[str, list[dict[str, Any]]] = {}
        self._lookup_labels: dict[str, str] = {}
        self._lookup_selected_values: dict[str, Any] = {}
        self._register_lookup_field(
            "cliente_id",
            search=self._search_client_lookup_options,
            resolve=self._resolve_client_lookup_options,
            bound_field_name="cliente_id",
        )

    @Property("QVariantMap", notify=valuesChanged)
    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @Property("QVariantMap", notify=fieldErrorsChanged)
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)

    @Property("QVariantList", notify=clientOptionsChanged)
    def client_options(self) -> list[dict[str, Any]]:
        return self.lookup_options("cliente_id")

    @Slot(str, "QVariant")
    def set_field_value(self, field_name: str, value: Any) -> None:
        if self.is_read_only:
            return
        if field_name not in self._values:
            return
        self._values[field_name] = value
        self._clear_field_error(field_name)
        self._set_error_message("")
        self._set_dirty(self._values != self._initial_values or self._is_dirty_externally())
        self._after_field_change(field_name)
        self.valuesChanged.emit()

    @Slot()
    def prime_client_field(self) -> None:
        self.prime_lookup_field("cliente_id")

    @Slot(str)
    def search_client_options(self, term: str) -> None:
        self.search_lookup_options("cliente_id", term)

    @Slot(str, result=list)
    def lookup_options(self, field_name: str) -> list[dict[str, Any]]:
        return [dict(option) for option in self._lookup_options.get(field_name, [])]

    @Slot(str)
    def prime_lookup_field(self, field_name: str) -> None:
        lookup = self._lookup_field(field_name)
        current_value = self._lookup_current_value(lookup)
        if current_value in (None, ""):
            options = lookup.search("")
        else:
            options = lookup.resolve(current_value)
        self._set_lookup_options(field_name, options)

    @Slot(str, str)
    def search_lookup_options(self, field_name: str, term: str) -> None:
        lookup = self._lookup_field(field_name)
        options = lookup.search(str(term or ""))
        current_value = self._lookup_current_value(lookup)
        if current_value not in (None, "") and all(option.get("value") != current_value for option in options):
            options = [*lookup.resolve(current_value), *options]
        self._set_lookup_options(field_name, options)

    @Slot(str, "QVariant", str)
    def set_lookup_field_value(self, field_name: str, value: Any, label: str) -> None:
        if self.is_read_only:
            return
        lookup = self._lookup_field(field_name)
        normalized_label = str(label or "").strip()
        current_options = self._lookup_options.get(field_name, [])
        selected_option = next((dict(option) for option in current_options if option.get("value") == value), None)
        if selected_option is None:
            selected_option = {"value": value, "label": normalized_label}
        elif normalized_label:
            selected_option["label"] = normalized_label
        if normalized_label:
            self._lookup_labels[field_name] = normalized_label
        self._set_lookup_options(field_name, [selected_option])
        if lookup.bound_field_name is None:
            self._lookup_selected_values[field_name] = value
            return
        self._set_bound_lookup_value(lookup.bound_field_name, value)

    def _replace_values(self, values: Mapping[str, Any], *, dirty: bool = False) -> None:
        self._values = dict(values)
        self._initial_values = dict(values)
        self._lookup_selected_values = {}
        self._set_dirty(dirty or self._is_dirty_externally())
        self.valuesChanged.emit()

    def _clear_field_error(self, field_name: str) -> None:
        if field_name in self._field_errors:
            self._field_errors.pop(field_name, None)
            self.fieldErrorsChanged.emit()

    def _set_field_errors(self, field_errors: Mapping[str, str]) -> None:
        normalized = {key: str(value) for key, value in dict(field_errors).items() if str(value or "")}
        if self._field_errors != normalized:
            self._field_errors = normalized
            self.fieldErrorsChanged.emit()

    def _after_field_change(self, field_name: str) -> None:
        lookup_field_name = self._lookup_name_for_bound_field(field_name)
        if lookup_field_name is not None:
            self.prime_lookup_field(lookup_field_name)
        if field_name == "cliente_id":
            self._handle_client_change()

    def _handle_client_change(self) -> None:
        return

    def _is_dirty_externally(self) -> bool:
        return False

    def _register_lookup_field(
        self,
        name: str,
        *,
        search: Any,
        resolve: Any,
        bound_field_name: str | None = None,
    ) -> None:
        self._lookup_fields[name] = WorkflowLookupField(
            name=name,
            search=search,
            resolve=resolve,
            bound_field_name=bound_field_name,
        )

    def _lookup_field(self, field_name: str) -> WorkflowLookupField:
        lookup = self._lookup_fields.get(field_name)
        if lookup is None:
            raise KeyError(f"Lookup desconocido: {field_name}")
        return lookup

    def _lookup_name_for_bound_field(self, field_name: str) -> str | None:
        for lookup_name, lookup in self._lookup_fields.items():
            if lookup.bound_field_name == field_name:
                return lookup_name
        return None

    def _lookup_current_value(self, lookup: WorkflowLookupField) -> Any:
        if lookup.bound_field_name is not None:
            return self._values.get(lookup.bound_field_name)
        return self._lookup_selected_values.get(lookup.name)

    def _set_lookup_options(self, field_name: str, options: list[dict[str, Any]]) -> None:
        normalized_options = [dict(option) for option in options if option.get("value") not in (None, "")]
        self._lookup_options[field_name] = normalized_options
        selected_label = next(
            (
                str(option.get("label") or "").strip()
                for option in normalized_options
                if option.get("value") == self._lookup_current_value(self._lookup_field(field_name))
            ),
            "",
        )
        if selected_label:
            self._lookup_labels[field_name] = selected_label
        if field_name == "cliente_id":
            self.clientOptionsChanged.emit()
        self.lookupOptionsChanged.emit(field_name)
        self._after_lookup_options_changed(field_name)

    def _set_bound_lookup_value(self, field_name: str, value: Any) -> None:
        if self.is_read_only:
            return
        if field_name not in self._values:
            return
        self._values[field_name] = value
        self._clear_field_error(field_name)
        self._set_error_message("")
        self._set_dirty(self._values != self._initial_values or self._is_dirty_externally())
        self._after_field_change(field_name)
        self.valuesChanged.emit()

    def _search_client_lookup_options(self, term: str) -> list[dict[str, Any]]:
        return _cliente_lookup_options(
            self._reference_lookup_service,
            lookup_key=self._client_lookup_key,
            term=term,
        )

    def _resolve_client_lookup_options(self, value: Any) -> list[dict[str, Any]]:
        options = _resolved_reference_option(
            self._reference_lookup_service,
            lookup_key=self._client_lookup_key,
            value=value,
        )
        cached_label = self._lookup_labels.get("cliente_id", "").strip()
        if not options and value not in (None, "") and cached_label:
            return [{"value": value, "label": cached_label}]
        return options

    def _after_lookup_options_changed(self, field_name: str) -> None:
        return


@QmlNamedElement("SelectableCandidateTableModel")
@QmlUncreatable("SelectableCandidateTableModel instances are created by workflow form view models.")
class SelectableCandidateTableModel(QAbstractTableModel):
    _CELL_VALUE_ROLE = Qt.ItemDataRole.UserRole + 1
    _ROW_DATA_ROLE = Qt.ItemDataRole.UserRole + 2
    _SELECTED_ROLE = Qt.ItemDataRole.UserRole + 3

    def __init__(
        self,
        form: WorkflowFormViewModelBase,
        *,
        field_name: str,
        selected_ids_getter: Any,
        columns: list[dict[str, Any]],
    ) -> None:
        super().__init__()
        self.setParent(form)
        self._form = form
        self._field_name = field_name
        self._selected_ids_getter = selected_ids_getter
        self._columns = [dict(column) for column in columns]
        self._rows: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not self._is_valid_index(index):
            return None
        row = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, self._CELL_VALUE_ROLE):
            return self._cell_value(row, index.column())
        if role == self._ROW_DATA_ROLE:
            return dict(row)
        if role == self._SELECTED_ROLE:
            return self._is_row_selected(row)
        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            self._CELL_VALUE_ROLE: b"cellValue",
            self._ROW_DATA_ROLE: b"rowData",
            self._SELECTED_ROLE: b"selected",
        }

    @Slot(result=list)
    def columns(self) -> list[dict[str, Any]]:
        return [dict(column) for column in self._columns]

    @Slot(int, result=object)
    def column_data(self, column: int) -> dict[str, Any]:
        if 0 <= column < len(self._columns):
            return dict(self._columns[column])
        return {}

    def set_column_width(self, column_key: str, width: int) -> bool:
        normalized_key = str(column_key or "").strip()
        if not normalized_key:
            return False
        for column in self._columns:
            if str(column.get("key") or "") != normalized_key:
                continue
            min_width = int(column.get("minWidth") or 40)
            normalized_width = max(int(width), min_width)
            if int(column.get("width") or min_width) == normalized_width:
                return False
            column["width"] = normalized_width
            return True
        return False

    @Slot(int, result=object)
    def row_data(self, row: int) -> dict[str, Any]:
        if 0 <= row < len(self._rows):
            return dict(self._rows[row])
        return {}

    @Slot(int, int, result=object)
    def cell_data(self, row: int, column: int) -> Any:
        if 0 <= row < len(self._rows):
            return self._cell_value(self._rows[row], column)
        return None

    def reset_model(self) -> None:
        self.beginResetModel()
        try:
            self._rows = self._current_rows()
        finally:
            self.endResetModel()

    def emit_selection_changed(self) -> None:
        if self.rowCount() == 0:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, max(0, self.columnCount() - 1))
        self.dataChanged.emit(top_left, bottom_right, [self._CELL_VALUE_ROLE, self._SELECTED_ROLE])

    def _current_rows(self) -> list[dict[str, Any]]:
        return self._form.lookup_options(self._field_name)

    def _selected_ids(self) -> set[int]:
        return {int(item) for item in self._selected_ids_getter()}

    def _is_row_selected(self, row: Mapping[str, Any]) -> bool:
        return int(row.get("value", 0)) in self._selected_ids()

    def _cell_value(self, row: Mapping[str, Any], column: int) -> Any:
        if not 0 <= column < len(self._columns):
            return None
        key = str(self._columns[column].get("key") or "")
        if key == "selected":
            return self._is_row_selected(row)
        if key == "referencia":
            return row.get("referencia") or row.get("label") or ""
        return row.get(key, "")

    def _is_valid_index(self, index: QModelIndex) -> bool:
        return index.isValid() and 0 <= index.row() < len(self._rows) and 0 <= index.column() < len(self._columns)
