"""Detail view models for Circuito workflow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloWorkflowService
from ....domain.modelo.dtos import FieldKind
from ....domain.modelo.field_validation import normalize_field_value, validate_field_value
from ...catalog.definitions import GenericFormFieldDefinition
from ...catalog.form_layout import FormLayoutDefinition, FormLayoutFieldItem
from ...qt import (
    Property,
    QAbstractListModel,
    QAbstractTableModel,
    QmlNamedElement,
    QmlUncreatable,
    QModelIndex,
    QObject,
    Qt,
    Signal,
    Slot,
)
from ...viewmodels.base_view_model import BaseViewModel
from ..viaje.detail import DetailSectionFormViewModel
from .forms import CircuitoBasicFormViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


_GASTO_CAMION_FIELDS = (
    GenericFormFieldDefinition(
        name="combustible_base_camion",
        label="Combustible base camion",
        kind=FieldKind.NUMBER.value,
        required=True,
        nullable=False,
    ),
    GenericFormFieldDefinition(
        name="retorno_camion",
        label="Retorno camion",
        kind=FieldKind.NUMBER.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="_consumo_camion",
        label="Consumo camion",
        kind=FieldKind.NUMBER.value,
        required=False,
        nullable=True,
        editable=False,
    ),
)

_GASTO_CAMION_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutFieldItem("combustible_base_camion"),
        FormLayoutFieldItem("retorno_camion"),
        FormLayoutFieldItem("_consumo_camion"),
    )
)


@QmlNamedElement("CircuitoMovimientosAdicionalesFormViewModel")
@QmlUncreatable("CircuitoMovimientosAdicionalesFormViewModel instances are created by CircuitoDetailViewModel.")
class CircuitoMovimientosAdicionalesFormViewModel(BaseViewModel):
    rowsChanged = Signal()
    lookupOptionsChanged = Signal()
    dirtyChanged = Signal(bool)
    validChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    readOnlyChanged = Signal(bool)

    def __init__(
        self,
        *,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        can_modify: bool = True,
        can_create_return_trip: bool = True,
    ) -> None:
        super().__init__()
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._rows: list[dict[str, Any]] = []
        self._initial_rows: list[dict[str, Any]] = []
        self._lookup_options: dict[str, list[dict[str, Any]]] = {}
        self._field_errors: dict[str, str] = {}
        self._is_dirty = False
        self._is_valid = True
        self._is_read_only = False
        self._error_message = ""
        self._table_model = CircuitoMovimientosTableModel(self)

    @Property("QVariantList", notify=rowsChanged)
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    @Property(QObject, constant=True)
    def table_model(self) -> CircuitoMovimientosTableModel:
        return self._table_model

    @Property("QVariantList", constant=True)
    def row_fields(self) -> list[dict[str, Any]]:
        return [
            {"name": "ruta_id", "label": "Ruta", "kind": "reference", "editable": True},
            {"name": "fecha_movimiento", "label": "Fecha movimiento", "kind": "datetime", "editable": True},
            {"name": "descripcion", "label": "Descripcion", "kind": "text", "editable": True},
            {"name": "es_triangulado", "label": "Triangulado", "kind": "boolean", "editable": True},
        ]

    @Property("QVariantMap", notify=lookupOptionsChanged)
    def lookup_options_map(self) -> dict[str, list[dict[str, Any]]]:
        return {field_name: [dict(option) for option in options] for field_name, options in self._lookup_options.items()}

    @Property(bool, notify=dirtyChanged)
    def is_dirty(self) -> bool:
        return self._is_dirty

    @Property(bool, notify=validChanged)
    def is_valid(self) -> bool:
        return self._is_valid

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(bool, notify=readOnlyChanged)
    def is_read_only(self) -> bool:
        return self._is_read_only

    def load_rows(self, rows: list[dict[str, Any]]) -> None:
        self._table_model.begin_model_reset()
        self._rows = [dict(row) for row in rows]
        self._initial_rows = [dict(row) for row in self._rows]
        self._table_model.end_model_reset()
        self._set_dirty(False)
        self._refresh_validation()
        self.rowsChanged.emit()

    @Slot(str, result=list)
    def lookup_options(self, field_name: str) -> list[dict[str, Any]]:
        return [dict(option) for option in self._lookup_options.get(str(field_name), [])]

    @Slot(str)
    def prime_lookup_field(self, field_name: str) -> None:
        if str(field_name) != "ruta_id":
            return
        current_value = next((row.get("ruta_id") for row in self._rows if row.get("ruta_id") not in (None, "")), None)
        options = self._resolve_route_options(current_value) if current_value not in (None, "") else self._search_route_options("")
        self._set_lookup_options("ruta_id", options)

    @Slot(str, str)
    def search_lookup_options(self, field_name: str, term: str) -> None:
        if str(field_name) != "ruta_id":
            return
        options = self._search_route_options(str(term or ""))
        current_options = list(options)
        for row in self._rows:
            current_value = row.get("ruta_id")
            if current_value in (None, "") or any(option.get("value") == current_value for option in current_options):
                continue
            current_options = [*self._resolve_route_options(current_value, fallback_label=row.get("ruta_label")), *current_options]
        self._set_lookup_options("ruta_id", current_options)

    @Slot(int, str, "QVariant", str)
    def set_lookup_field_value(self, row_index: int, field_name: str, value: Any, label: str) -> None:
        if self._is_read_only:
            return
        if str(field_name) != "ruta_id" or not (0 <= row_index < len(self._rows)):
            return
        normalized_label = str(label or "").strip()
        self._rows[row_index]["ruta_id"] = value
        self._rows[row_index]["ruta_label"] = normalized_label
        if value not in (None, ""):
            self._set_lookup_options("ruta_id", [{"value": value, "label": normalized_label or str(value)}])
        self._table_model.emit_row_changed(row_index)
        self._set_dirty(self._rows != self._initial_rows)
        self._refresh_validation()
        self.rowsChanged.emit()

    @Slot()
    def add_row(self) -> None:
        if self._is_read_only:
            return
        row = {
            "id": None,
            "ruta_id": None,
            "ruta_label": "",
            "fecha_movimiento": "",
            "descripcion": "",
            "es_triangulado": False,
        }
        index = len(self._rows)
        self._table_model.begin_insert_row(index)
        self._rows.append(row)
        self._table_model.end_insert_row()
        self._set_dirty(True)
        self._refresh_validation()
        self.rowsChanged.emit()

    @Slot(int)
    def remove_row(self, row_index: int) -> None:
        if self._is_read_only:
            return
        if 0 <= row_index < len(self._rows):
            self._table_model.begin_remove_row(row_index)
            self._rows.pop(row_index)
            self._table_model.end_remove_row()
            self._set_dirty(self._rows != self._initial_rows)
            self._refresh_validation()
            self.rowsChanged.emit()

    @Slot(int, str, "QVariant")
    def set_row_field(self, row_index: int, field_name: str, value: Any) -> None:
        if self._is_read_only:
            return
        if not (0 <= row_index < len(self._rows)):
            return
        if field_name not in self._rows[row_index]:
            return
        self._rows[row_index][field_name] = value
        if field_name == "ruta_id" and value in (None, ""):
            self._rows[row_index]["ruta_label"] = ""
        self._table_model.emit_row_changed(row_index)
        self._set_dirty(self._rows != self._initial_rows)
        self._refresh_validation()
        self.rowsChanged.emit()

    @Slot(result=bool)
    def save_section(self) -> bool:
        if self._is_read_only:
            return False
        handler = getattr(self, "_save_handler", None)
        return bool(handler("movimientos_adicionales")) if callable(handler) else False

    def set_save_handler(self, handler) -> None:
        self._save_handler = handler

    def build_payload(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for row in self._rows:
            if all(row.get(key) in (None, "") for key in ("ruta_id", "fecha_movimiento", "descripcion")) and not row.get("es_triangulado"):
                continue
            item = {
                "ruta_id": normalize_field_value(
                    kind=FieldKind.INTEGER,
                    value=row.get("ruta_id"),
                    required=False,
                    nullable=True,
                ),
                "fecha_movimiento": normalize_field_value(
                    kind=FieldKind.DATETIME,
                    value=row.get("fecha_movimiento"),
                    required=False,
                    nullable=True,
                ),
                "descripcion": normalize_field_value(
                    kind=FieldKind.TEXT,
                    value=row.get("descripcion"),
                    required=False,
                    nullable=True,
                ),
                "es_triangulado": bool(row.get("es_triangulado", False)),
            }
            if row.get("id") not in (None, ""):
                item["id"] = int(row["id"])
            payload.append(item)
        return payload

    def _refresh_validation(self) -> None:
        errors: dict[str, str] = {}
        for index, row in enumerate(self._rows):
            if all(row.get(key) in (None, "") for key in ("ruta_id", "fecha_movimiento", "descripcion")) and not row.get("es_triangulado"):
                continue
            error = validate_field_value(
                kind=FieldKind.DATETIME,
                value=row.get("fecha_movimiento"),
                required=False,
                nullable=True,
            )
            if error:
                errors[f"row_{index}_fecha_movimiento"] = error
        self._field_errors = errors
        self._set_valid(not errors)

    def _set_dirty(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_dirty != normalized:
            self._is_dirty = normalized
            self.dirtyChanged.emit(normalized)

    def _set_valid(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_valid != normalized:
            self._is_valid = normalized
            self.validChanged.emit(normalized)

    def _search_route_options(self, term: str) -> list[dict[str, Any]]:
        normalized_term = str(term or "").strip()
        if self._reference_lookup_service is None:
            return self._catalog_route_options(normalized_term)
        options = [
            {"value": option.value, "label": option.label}
            for option in self._reference_lookup_service.search("viaje._ruta_id", normalized_term, limit=50)
            if option.value not in (None, "")
        ]
        return options or self._catalog_route_options(normalized_term)

    def _resolve_route_options(self, value: Any, fallback_label: Any = "") -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        if self._reference_lookup_service is not None:
            resolved = self._reference_lookup_service.resolve_ids("viaje._ruta_id", [value])
            option = resolved.get(int(value) if str(value).isdigit() else value)
            if option is not None:
                return [{"value": option.value, "label": option.label}]
        record = self._route_record(value)
        if record is not None:
            return [{"value": record.get("id"), "label": self._route_label(record)}]
        label = str(fallback_label or value).strip()
        return [{"value": value, "label": label}]

    def _catalog_route_options(self, term: str) -> list[dict[str, Any]]:
        normalized_term = str(term or "").strip().casefold()
        options: list[dict[str, Any]] = []
        for record in self._workflow_service.catalog.list("ruta"):
            label = self._route_label(record)
            if normalized_term and normalized_term not in label.casefold():
                continue
            options.append({"value": record.get("id"), "label": label})
            if len(options) >= 50:
                break
        return options

    def _route_record(self, value: Any) -> dict[str, Any] | None:
        try:
            record = self._workflow_service.catalog.get("ruta", int(value))
        except (TypeError, ValueError):
            return None
        return dict(record) if record is not None else None

    def _route_label(self, route: Mapping[str, Any]) -> str:
        origen_label = self._ubicacion_label(route.get("origen_id"))
        destino_label = self._ubicacion_label(route.get("destino_id"))
        if origen_label and destino_label:
            return f"{origen_label} -> {destino_label}"
        return str(route.get("id") or "")

    def _ubicacion_label(self, value: Any) -> str:
        try:
            record = self._workflow_service.catalog.get("ubicacion", int(value))
        except (TypeError, ValueError):
            return ""
        if record is None:
            return ""
        return str(record.get("descripcion") or record.get("id") or "")

    def _set_lookup_options(self, field_name: str, options: list[dict[str, Any]]) -> None:
        seen: set[str] = set()
        normalized: list[dict[str, Any]] = []
        for option in options:
            value = option.get("value")
            if value in (None, ""):
                continue
            key = str(value)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"value": value, "label": str(option.get("label") or value)})
        self._lookup_options[field_name] = normalized
        self.lookupOptionsChanged.emit()

    def set_read_only(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_read_only != normalized:
            self._is_read_only = normalized
            self.readOnlyChanged.emit(normalized)

@QmlNamedElement("CircuitoMovimientosTableModel")
@QmlUncreatable("CircuitoMovimientosTableModel instances are created by CircuitoMovimientosAdicionalesFormViewModel.")
class CircuitoMovimientosTableModel(QAbstractTableModel):
    _ROW_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
    _ROW_INDEX_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, form: CircuitoMovimientosAdicionalesFormViewModel) -> None:
        super().__init__(form)
        self._form = form

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._form._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._form.row_fields) + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not self._is_valid_index(index):
            return None

        row = index.row()
        column = index.column()

        if role == self._ROW_DATA_ROLE:
            return dict(self._form._rows[row])

        if role == self._ROW_INDEX_ROLE:
            return row

        if role == Qt.ItemDataRole.DisplayRole:
            if self._is_actions_column(column):
                return ""

            field_name = str(self._form.row_fields[column].get("name", ""))
            if not field_name:
                return ""

            return self._form._rows[row].get(field_name, "")

        return None

    def roleNames(self) -> dict[int, bytes]:
        return {
            int(Qt.ItemDataRole.DisplayRole): b"display",
            int(self._ROW_DATA_ROLE): b"rowData",
            int(self._ROW_INDEX_ROLE): b"rowIndex",
        }

    @Slot(int, result=object)
    def column_field(self, column: int) -> dict[str, Any]:
        try:
            column = int(column)
        except (TypeError, ValueError):
            return {}

        if 0 <= column < len(self._form.row_fields):
            return dict(self._form.row_fields[column])

        if self._is_actions_column(column):
            return {
                "name": "__actions__",
                "label": "Acciones",
            }

        return {}

    def begin_model_reset(self) -> None:
        self.beginResetModel()

    def end_model_reset(self) -> None:
        self.endResetModel()

    def begin_insert_row(self, row: int) -> None:
        if not (0 <= row <= len(self._form._rows)):
            return
        self.beginInsertRows(QModelIndex(), row, row)

    def end_insert_row(self) -> None:
        self.endInsertRows()

    def begin_remove_row(self, row: int) -> None:
        if not (0 <= row < len(self._form._rows)):
            return
        self.beginRemoveRows(QModelIndex(), row, row)

    def end_remove_row(self) -> None:
        self.endRemoveRows()

    def emit_row_changed(self, row: int) -> None:
        if 0 <= row < self.rowCount() and self.columnCount() > 0:
            left_index = self.index(row, 0)
            right_index = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left_index, right_index, [])

    def _is_valid_index(self, index: QModelIndex) -> bool:
        return (
            index.isValid()
            and 0 <= index.row() < len(self._form._rows)
            and 0 <= index.column() < self.columnCount()
        )

    def _is_actions_column(self, column: int) -> bool:
        return column == len(self._form.row_fields)


@QmlNamedElement("CircuitoDetailViewModel")
@QmlUncreatable("CircuitoDetailViewModel instances are created by CircuitoWorkflowViewModel.")
class CircuitoDetailViewModel(BaseViewModel):
    summaryChanged = Signal()
    circuitoSummaryChanged = Signal()
    viajesChanged = Signal()
    visibleSectionsChanged = Signal()
    activeTabChanged = Signal(str)
    canAddReturnTripChanged = Signal(bool)
    canEditCircuitoChanged = Signal(bool)
    closedChanged = Signal(bool)
    errorMessageChanged = Signal(str)

    def __init__(
        self,
        *,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        can_modify: bool = True,
        can_create_return_trip: bool = True,
    ) -> None:
        super().__init__()
        self._workflow_service = workflow_service
        self._summary: dict[str, Any] = {}
        self._circuito_summary: dict[str, Any] = {}
        self._viaje_ida: dict[str, Any] = {}
        self._viaje_vuelta: dict[str, Any] = {}
        self._visible_sections: list[str] = []
        self._active_tab = "gasto_real_camion"
        self._record_id: int | None = None
        self._error_message = ""
        self._can_modify = bool(can_modify)
        self._can_create_return_trip = bool(can_create_return_trip)
        self._summary_can_add_return_trip = False
        self._can_add_return_trip = False
        self._can_edit_circuito = False
        self._is_closed = False
        self._circuito_form = CircuitoBasicFormViewModel(workflow_service=workflow_service)
        self._gasto_real_camion_form = DetailSectionFormViewModel(
            section_key="gasto_real_camion",
            title="Consumo camion",
            fields=_GASTO_CAMION_FIELDS,
            form_layout=_GASTO_CAMION_LAYOUT,
            workflow_service=workflow_service,
        )
        self._movimientos_adicionales_form = CircuitoMovimientosAdicionalesFormViewModel(
            workflow_service=workflow_service,
            reference_lookup_service=reference_lookup_service,
        )
        self._gasto_real_camion_form.set_save_handler(self.save_section)
        self._movimientos_adicionales_form.set_save_handler(self.save_section)

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, Any]:
        return dict(self._summary)

    @Property("QVariantMap", notify=circuitoSummaryChanged)
    def circuito_summary(self) -> dict[str, Any]:
        return dict(self._circuito_summary)

    @Property("QVariantMap", notify=viajesChanged)
    def viaje_ida(self) -> dict[str, Any]:
        return dict(self._viaje_ida)

    @Property("QVariantMap", notify=viajesChanged)
    def viaje_vuelta(self) -> dict[str, Any]:
        return dict(self._viaje_vuelta)

    @Property("QVariantList", notify=visibleSectionsChanged)
    def visible_sections(self) -> list[str]:
        return list(self._visible_sections)

    @Property(str, notify=activeTabChanged)
    def active_tab(self) -> str:
        return self._active_tab

    @Property(bool, notify=canAddReturnTripChanged)
    def can_add_return_trip(self) -> bool:
        return self._can_add_return_trip

    @Property(bool, notify=canEditCircuitoChanged)
    def can_edit_circuito(self) -> bool:
        return self._can_edit_circuito

    @Property(bool, notify=closedChanged)
    def is_closed(self) -> bool:
        return self._is_closed

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(CircuitoBasicFormViewModel, constant=True)
    def circuito_form(self) -> CircuitoBasicFormViewModel:
        return self._circuito_form

    @Property(DetailSectionFormViewModel, constant=True)
    def gasto_real_camion_form(self) -> DetailSectionFormViewModel:
        return self._gasto_real_camion_form

    @Property(CircuitoMovimientosAdicionalesFormViewModel, constant=True)
    def movimientos_adicionales_form(self) -> CircuitoMovimientosAdicionalesFormViewModel:
        return self._movimientos_adicionales_form

    def load(self, record_id: int) -> None:
        self.is_busy = True
        try:
            self._set_error_message("")
            self._record_id = int(record_id)
            self._apply_summary(self._workflow_service.circuito.get_detail_summary(int(record_id)))
        except Exception as exc:
            self._set_error_message(str(exc))
            raise
        finally:
            self.is_busy = False

    @Slot()
    def reload(self) -> None:
        if self._record_id is not None:
            self.load(self._record_id)

    @Slot(str)
    def set_active_tab(self, section_key: str) -> None:
        normalized = str(section_key or "").strip()
        if normalized and self._active_tab != normalized:
            self._active_tab = normalized
            self.activeTabChanged.emit(normalized)

    @Slot(str, result=dict)
    def section_state(self, section_key: str) -> dict[str, Any]:
        form = {
            "gasto_real_camion": self._gasto_real_camion_form,
            "movimientos_adicionales": self._movimientos_adicionales_form,
        }.get(str(section_key))
        if form is None:
            return {"visible": False, "dirty": False, "valid": True, "title": str(section_key)}
        return {
            "visible": str(section_key) in self._visible_sections,
            "dirty": bool(getattr(form, "is_dirty", False)),
            "valid": bool(getattr(form, "is_valid", True)),
            "title": getattr(form, "title", "Movimientos adicionales"),
        }

    @Slot(str, result=bool)
    def save_section(self, section_key: str) -> bool:
        if self._is_closed:
            self._set_error_message("No se puede modificar un circuito finalizado")
            return False
        if not self._can_modify:
            self._set_error_message("No tienes permiso para modificar circuito")
            return False
        if self._record_id is None:
            return False
        try:
            payload = self._build_payload_for_section(str(section_key))
            self._workflow_service.circuito.actualizar_secciones(self._record_id, payload)
            self._apply_summary(self._workflow_service.circuito.get_detail_summary(self._record_id))
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

    def _build_payload_for_section(self, section_key: str) -> dict[str, Any]:
        if section_key == "gasto_real_camion":
            self._gasto_real_camion_form._refresh_validation()
            if not self._gasto_real_camion_form.is_valid:
                raise ValueError("La seccion Consumo camion es invalida.")
            return {"gasto_real_camion": self._gasto_real_camion_form.build_payload()}
        if section_key == "movimientos_adicionales":
            if not self._movimientos_adicionales_form.is_valid:
                raise ValueError("La seccion Movimientos adicionales es invalida.")
            return {"movimientos_adicionales": self._movimientos_adicionales_form.build_payload()}
        return {}

    def _apply_summary(self, summary: Mapping[str, Any]) -> None:
        normalized = dict(summary)
        self._summary = normalized
        self._circuito_summary = dict(normalized.get("circuito") or {})
        self._viaje_ida = dict(normalized.get("viaje_ida") or {})
        self._viaje_vuelta = dict(normalized.get("viaje_vuelta") or {})
        self._visible_sections = [str(item) for item in normalized.get("visible_sections", [])]
        self._summary_can_add_return_trip = bool(normalized.get("can_add_return_trip", False))
        next_is_closed = str(self._circuito_summary.get("estado") or "") == "Finalizado"
        next_can_edit_circuito = self._can_modify and not next_is_closed
        next_can_add_return_trip = (
            self._summary_can_add_return_trip
            and self._can_modify
            and self._can_create_return_trip
            and not next_is_closed
        )
        self._gasto_real_camion_form.load_from_record(normalized.get("gasto_real_camion") or {})
        self._movimientos_adicionales_form.load_rows(list(normalized.get("movimientos_adicionales") or []))
        self._apply_read_only_to_forms(next_is_closed or not self._can_modify)
        if self._record_id is not None:
            self._circuito_form.load(self._record_id)
        if self._is_closed != next_is_closed:
            self._is_closed = next_is_closed
            self.closedChanged.emit(next_is_closed)
        if self._can_edit_circuito != next_can_edit_circuito:
            self._can_edit_circuito = next_can_edit_circuito
            self.canEditCircuitoChanged.emit(next_can_edit_circuito)
        if self._active_tab not in self._visible_sections:
            self._active_tab = self._visible_sections[0] if self._visible_sections else "gasto_real_camion"
            self.activeTabChanged.emit(self._active_tab)
        self.summaryChanged.emit()
        self.circuitoSummaryChanged.emit()
        self.viajesChanged.emit()
        self.visibleSectionsChanged.emit()
        if self._can_add_return_trip != next_can_add_return_trip:
            self._can_add_return_trip = next_can_add_return_trip
            self.canAddReturnTripChanged.emit(next_can_add_return_trip)

    def set_permissions(self, *, can_modify: bool, can_create_return_trip: bool) -> None:
        next_can_modify = bool(can_modify)
        next_can_create_return_trip = bool(can_create_return_trip)
        changed = self._can_modify != next_can_modify or self._can_create_return_trip != next_can_create_return_trip
        self._can_modify = next_can_modify
        self._can_create_return_trip = next_can_create_return_trip
        next_can_edit_circuito = self._can_modify and not self._is_closed
        next_can_add_return_trip = (
            self._summary_can_add_return_trip
            and self._can_modify
            and self._can_create_return_trip
            and not self._is_closed
        )
        self._apply_read_only_to_forms(self._is_closed or not self._can_modify)
        if self._can_edit_circuito != next_can_edit_circuito:
            self._can_edit_circuito = next_can_edit_circuito
            self.canEditCircuitoChanged.emit(next_can_edit_circuito)
        if self._can_add_return_trip != next_can_add_return_trip:
            self._can_add_return_trip = next_can_add_return_trip
            self.canAddReturnTripChanged.emit(next_can_add_return_trip)
        if changed:
            self.visibleSectionsChanged.emit()

    def _apply_read_only_to_forms(self, value: bool) -> None:
        self._gasto_real_camion_form.set_read_only(value)
        self._movimientos_adicionales_form.set_read_only(value)

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)
