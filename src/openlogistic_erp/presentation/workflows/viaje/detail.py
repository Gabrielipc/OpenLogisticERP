"""Detail coordinators and section forms for viaje.detalle_operacion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloWorkflowService
from ....domain.modelo.dtos import FieldKind, ReferenceFieldDTO
from ....domain.modelo.field_validation import (
    format_field_value_for_ui,
    normalize_field_value,
    validate_field_value,
)
from ....infrastructure.persistence.modelo.workflow_orm import Gasolinera, TipoOrdenCombustible
from ...catalog.definitions import FormFieldOption, GenericFormFieldDefinition
from ...catalog.form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from ...qt import Property, QAbstractListModel, QAbstractTableModel, QmlNamedElement, QmlUncreatable, QModelIndex, QObject, Qt, Signal, Slot
from ...viewmodels.base_view_model import BaseViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


def _enum_options(enum_cls: type[Enum]) -> tuple[FormFieldOption, ...]:
    return tuple(FormFieldOption(value=str(member.value), label=str(member.value)) for member in enum_cls)


def _serialize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    if hasattr(value, "value"):
        enum_value = getattr(value, "value", None)
        if enum_value is not None:
            return enum_value
    return value


def _coerce_model_value(field: GenericFormFieldDefinition, value: Any) -> Any:
    normalized_kind = field.kind or field.field_type
    normalized = normalize_field_value(
        kind=normalized_kind,
        value=value,
        required=field.required,
        nullable=field.nullable,
        options=tuple(field.options),
    )
    if normalized is None:
        return None
    if normalized_kind == FieldKind.DATETIME.value:
        return datetime.fromisoformat(str(normalized))
    if normalized_kind == FieldKind.DATE.value:
        return date.fromisoformat(str(normalized))
    if normalized_kind == FieldKind.NUMBER.value:
        return float(str(normalized))
    if normalized_kind == FieldKind.INTEGER.value or normalized_kind == FieldKind.REFERENCE.value:
        return int(normalized)
    return normalized

def _extract_id_as_int(datos: Any) -> int | None:
    if isinstance(datos, Mapping):
        value_id = datos.get("id") 
        if value_id is not None:
            return int(value_id) 
    return None

@dataclass(frozen=True)
class DetailSectionDefinition:
    key: str
    title: str
    visible_for: frozenset[str]


_DESCARGA_FIELDS = (
    GenericFormFieldDefinition(
        name="fecha_posicionamiento",
        label="Fecha posicionamiento",
        kind=FieldKind.DATETIME.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="fecha_despacho",
        label="Fecha despacho",
        kind=FieldKind.DATETIME.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="fecha_descarga",
        label="Fecha descarga",
        kind=FieldKind.DATETIME.value,
        required=True,
        nullable=False,
    ),
    GenericFormFieldDefinition(
        name="peso",
        label="Peso",
        kind=FieldKind.TEXT.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="_dias_viajados",
        label="Dias viajados",
        kind=FieldKind.INTEGER.value,
        required=False,
        nullable=True,
        editable=False,
    )
)

_DESCARGA_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutFieldItem("fecha_posicionamiento"),
        FormLayoutFieldItem("fecha_despacho"),
        FormLayoutFieldItem("fecha_descarga"),
        FormLayoutFieldItem("peso"),
        FormLayoutFieldItem("_dias_viajados"),
        FormLayoutFieldItem("_lugar_carga_id"),
    )
)

_THERMO_FIELDS = (
    GenericFormFieldDefinition(
        name="fecha_hora_encendido",
        label="Encendido",
        kind=FieldKind.DATETIME.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="fecha_hora_apagado",
        label="Apagado",
        kind=FieldKind.DATETIME.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="_duracion_horas",
        label="Duración horas",
        kind=FieldKind.NUMBER.value,
        required=False,
        nullable=True,
        editable=False,
    ),
    GenericFormFieldDefinition(
        name="combustible_base_thermo",
        label="Combustible base thermo",
        kind=FieldKind.NUMBER.value,
        required=True,
        nullable=False,
    ),
    GenericFormFieldDefinition(
        name="restante_thermo",
        label="Restante thermo",
        kind=FieldKind.NUMBER.value,
        required=False,
        nullable=True,
    ),
    GenericFormFieldDefinition(
        name="_consumo_thermo",
        label="Consumo thermo",
        kind=FieldKind.NUMBER.value,
        required=False,
        nullable=True,
        editable=False,
        precision=2,
    ),
)

_THERMO_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutSectionItem("Actividad del Thermo"),
        FormLayoutFieldItem("fecha_hora_encendido"),
        FormLayoutFieldItem("fecha_hora_apagado"),
        FormLayoutFieldItem("_duracion_horas"),
        FormLayoutSectionItem("Combustible del Thermo"),
        FormLayoutFieldItem("combustible_base_thermo"),
        FormLayoutFieldItem("restante_thermo"),
        FormLayoutFieldItem("_consumo_thermo"),
    )
)

DETAIL_SECTIONS: tuple[DetailSectionDefinition, ...] = (
    DetailSectionDefinition("descarga", "Descarga", frozenset({"Exportacion", "Importacion"})),
    DetailSectionDefinition("combustible_thermo", "Combustible del Thermo", frozenset({"Exportacion"})),
    DetailSectionDefinition("ordenes_combustible", "Ordenes de Combustible", frozenset({"Exportacion", "Importacion"})),
)


@QmlNamedElement("DetailSectionFormViewModel")
@QmlUncreatable("DetailSectionFormViewModel instances are created by DetalleOperacionViewModel.")
class DetailSectionFormViewModel(BaseViewModel):
    valuesChanged = Signal()
    fieldErrorsChanged = Signal()
    dirtyChanged = Signal(bool)
    validChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    layoutItemsChanged = Signal()
    readOnlyChanged = Signal(bool)

    def __init__(
        self,
        *,
        section_key: str,
        title: str,
        fields: tuple[GenericFormFieldDefinition, ...],
        form_layout: FormLayoutDefinition,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
    ) -> None:
        super().__init__()
        self._section_key = section_key
        self._title = title
        self._fields = fields
        self._field_map = {field.name: field for field in fields}
        self._layout = form_layout
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._save_handler = None
        self._values: dict[str, Any] = {}
        self._initial_values: dict[str, Any] = {}
        self._field_errors: dict[str, str] = {}
        self._reference_options: dict[str, list[dict[str, Any]]] = {}
        self._reference_labels: dict[str, str] = {}
        self._is_dirty = False
        self._is_valid = True
        self._is_read_only = False
        self._error_message = ""
        self._reset_to_defaults()

    @Property(str, constant=True)
    def section_key(self) -> str:
        return self._section_key

    @Property(str, constant=True)
    def title(self) -> str:
        return self._title

    @Property("QVariantMap", notify=valuesChanged)
    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @Property("QVariantMap", notify=fieldErrorsChanged)
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)

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

    @Property("QVariantList", notify=layoutItemsChanged)
    def layout_items(self) -> list[dict[str, Any]]:
        serialized_fields = {field.name: self._serialize_field(field) for field in self._fields}
        layout_items: list[dict[str, Any]] = []
        pending_row: list[dict[str, Any]] = []

        def flush_row() -> None:
            if not pending_row:
                return
            layout_items.append({"type": "row", "fields": list(pending_row)})
            pending_row.clear()

        for item in self._layout.items:
            if isinstance(item, FormLayoutSectionItem):
                flush_row()
                layout_items.append({"type": "section", "title": item.title})
                continue
            field = serialized_fields.get(item.field_name)
            if field is None:
                continue
            entry = {
                **field,
                "span": 2 if item.full_width else max(1, int(item.span or 1)),
                "full_width": bool(item.full_width),
            }
            if entry["span"] >= 2:
                flush_row()
                layout_items.append({"type": "row", "fields": [entry]})
                continue
            if len(pending_row) >= 2:
                flush_row()
            pending_row.append(entry)
            if len(pending_row) >= 2:
                flush_row()
        flush_row()
        return layout_items

    def set_save_handler(self, handler) -> None:
        self._save_handler = handler

    def load_from_record(self, record: Mapping[str, Any] | None) -> None:
        normalized = dict(record or {})
        values: dict[str, Any] = {}
        labels: dict[str, str] = {}
        for field in self._fields:
            raw_value = normalized.get(field.name, field.resolve_default())
            serialized_value = _serialize_scalar(raw_value)
            try:
                values[field.name] = format_field_value_for_ui(
                    kind=field.kind or field.field_type,
                    value=serialized_value,
                    precision=field.precision,
                )
            except (TypeError, ValueError):
                values[field.name] = "" if serialized_value is None else str(serialized_value)
            if field.display_field_key:
                display_value = normalized.get(field.display_field_key)
                if display_value not in (None, ""):
                    labels[field.name] = str(display_value)
        self._values = values
        self._initial_values = dict(values)
        self._reference_labels = labels
        self._field_errors = {}
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self.valuesChanged.emit()
        self.fieldErrorsChanged.emit()
        self.layoutItemsChanged.emit()

    def _reset_to_defaults(self) -> None:
        defaults = {
            field.name: format_field_value_for_ui(
                kind=field.kind or field.field_type,
                value=_serialize_scalar(field.resolve_default()),
                precision=field.precision,
            )
            for field in self._fields
        }
        self._values = defaults
        self._initial_values = dict(defaults)
        self._field_errors = {}
        self._reference_options = {}
        self._reference_labels = {}
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self.valuesChanged.emit()
        self.fieldErrorsChanged.emit()
        self.layoutItemsChanged.emit()

    @Slot(str, "QVariant")
    def set_field_value(self, field_name: str, value: Any) -> None:
        if self._is_read_only:
            return
        if field_name not in self._values:
            return
        self._values[field_name] = "" if value is None else value
        self._set_dirty(self._values != self._initial_values)
        self._set_error_message("")
        self._refresh_validation()
        self.valuesChanged.emit()
        self.layoutItemsChanged.emit()

    @Slot(str, "QVariant", str)
    def set_reference_field_value(self, field_name: str, value: Any, label: str) -> None:
        if self._is_read_only:
            return
        self.set_field_value(field_name, value)
        if str(label or "").strip():
            self._reference_labels[field_name] = str(label)
        else:
            self._reference_labels.pop(field_name, None)
        self.layoutItemsChanged.emit()

    @Slot(str)
    def prime_reference_field(self, field_name: str) -> None:
        field = self._field_map.get(field_name)
        if field is None or field.reference is None:
            return
        current_value = self._values.get(field_name)
        options = self._reference_lookup(field.reference, current_value, "")
        if current_value not in (None, "") and current_value != "" and not options:
            label = self._reference_labels.get(field_name, str(current_value))
            options = [{"value": current_value, "label": label}]
        self._reference_options[field_name] = options
        self.layoutItemsChanged.emit()

    @Slot(str, str)
    def search_reference_options(self, field_name: str, term: str) -> None:
        field = self._field_map.get(field_name)
        if field is None or field.reference is None:
            return
        self._reference_options[field_name] = self._reference_lookup(field.reference, self._values.get(field_name), term)
        self.layoutItemsChanged.emit()

    def _reference_lookup(self, reference: ReferenceFieldDTO, current_value: Any, term: str) -> list[dict[str, Any]]:
        if reference.lookup_key == "ubicacion.catalog":
            rows = self._workflow_service.catalog.list("ubicacion")
            normalized = str(term or "").strip().lower()
            options: list[dict[str, Any]] = []
            for row in rows:
                label = str(row.get("descripcion") or row.get("id") or "")
                if normalized and normalized not in label.lower():
                    continue
                options.append({"value": row.get("id"), "label": label})
                if len(options) >= int(reference.page_size):
                    break
            if current_value not in (None, "") and not any(option["value"] == current_value for option in options):
                record = self._workflow_service.catalog.get("ubicacion", int(current_value))
                if record is not None:
                    options.insert(0, {"value": record.get("id"), "label": str(record.get("descripcion") or current_value)})
            return options
        if self._reference_lookup_service is None:
            return []
        normalized_term = str(term or "").strip()
        context = None
        if current_value not in (None, "") and not normalized_term:
            resolved = self._reference_lookup_service.resolve_ids(reference.lookup_key, [current_value])
            option = resolved.get(int(current_value) if str(current_value).isdigit() else current_value)
            if option is not None:
                return [{"value": option.value, "label": option.label}]
        return [
            {"value": option.value, "label": option.label}
            for option in self._reference_lookup_service.search(
                reference.lookup_key,
                normalized_term,
                reference.page_size,
                context=context,
            )
        ]

    @Slot(result=bool)
    def save_section(self) -> bool:
        if self._is_read_only:
            return False
        if self._save_handler is None:
            return False
        return bool(self._save_handler(self._section_key))

    @Slot()
    def reset_section(self) -> None:
        if self._is_read_only:
            return
        self._values = dict(self._initial_values)
        self._field_errors = {}
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self.valuesChanged.emit()
        self.fieldErrorsChanged.emit()
        self.layoutItemsChanged.emit()

    def build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in self._fields:
            if not field.editable:
                continue
            payload[field.name] = _coerce_model_value(field, self._values.get(field.name))
        return payload

    def _refresh_validation(self) -> None:
        errors: dict[str, str] = {}
        for field in self._fields:
            error = validate_field_value(
                kind=field.kind or field.field_type,
                value=self._values.get(field.name),
                required=field.required,
                nullable=field.nullable,
                options=tuple(field.options),
            )
            if error:
                errors[field.name] = error
        self._field_errors = errors
        self._set_valid(not errors)
        self.fieldErrorsChanged.emit()

    def _serialize_field(self, field: GenericFormFieldDefinition) -> dict[str, Any]:
        options = [
            {"value": option.value, "label": option.display_label()}
            for option in field.options
        ]
        if field.reference is not None:
            options = list(self._reference_options.get(field.name, []))
        return {
            "name": field.name,
            "label": field.label or field.name,
            "field_type": field.field_type,
            "kind": field.kind or field.field_type,
            "required": field.required,
            "editable": field.editable,
            "nullable": field.nullable,
            "precision": field.precision,
            "display_format": field.display_format or "",
            "display_field_key": field.display_field_key or "",
            "options": options,
            "reference": {
                "lookup_key": field.reference.lookup_key,
                "min_search_chars": field.reference.min_search_chars,
                "page_size": field.reference.page_size,
                "value_field": field.reference.value_field,
                "label_field": field.reference.label_field,
            }
            if field.reference is not None
            else None,
        }

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

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def set_read_only(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_read_only != normalized:
            self._is_read_only = normalized
            self.readOnlyChanged.emit(normalized)
            self.layoutItemsChanged.emit()


@QmlNamedElement("FuelOrdersSectionFormViewModel")
@QmlUncreatable("FuelOrdersSectionFormViewModel instances are created by DetalleOperacionViewModel.")
class FuelOrdersSectionFormViewModel(BaseViewModel):
    rowsChanged = Signal()
    fieldErrorsChanged = Signal()
    dirtyChanged = Signal(bool)
    validChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    readOnlyChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._save_handler = None
        self._rows: list[dict[str, Any]] = []
        self._initial_rows: list[dict[str, Any]] = []
        self._field_errors: dict[str, str] = {}
        self._is_dirty = False
        self._is_valid = True
        self._is_read_only = False
        self._error_message = ""
        self._row_fields = [
            {
                "name": "gasolinera",
                "label": "Gasolinera",
                "kind": "enum",
                "options": [{"value": option.value, "label": option.display_label()} for option in _enum_options(Gasolinera)],
            },
            {"name": "numero_orden", "label": "Número orden", "kind": "text", "options": []},
            {"name": "galones_autorizados", "label": "Galones", "kind": "number", "options": []},
            {
                "name": "tipo",
                "label": "Tipo",
                "kind": "enum",
                "options": [{"value": option.value, "label": option.display_label()} for option in _enum_options(TipoOrdenCombustible)],
            },
        ]
        self._table_model = FuelOrdersTableModel(self)
        self.reset_rows()

    @Property(str, constant=True)
    def section_key(self) -> str:
        return "ordenes_combustible"

    @Property(str, constant=True)
    def title(self) -> str:
        return "Ordenes de Combustible"

    @Property("QVariantList", notify=rowsChanged)
    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    @Property(QObject, constant=True)
    def table_model(self) -> FuelOrdersTableModel:
        return self._table_model

    @Property("QVariantList", constant=True)
    def row_fields(self) -> list[dict[str, Any]]:
        return list(self._row_fields)

    @Property("QVariantMap", notify=fieldErrorsChanged)
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)

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

    def set_save_handler(self, handler) -> None:
        self._save_handler = handler

    def load_rows(self, rows: list[dict[str, Any]] | None) -> None:
        source = [dict(row) for row in (rows or [])]
        self._table_model.begin_model_reset()
        self._rows = source or [self._empty_row()]
        self._initial_rows = [dict(row) for row in self._rows]
        self._field_errors = {}
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self._table_model.end_model_reset()
        self.rowsChanged.emit()
        self.fieldErrorsChanged.emit()

    @Slot()
    def add_row(self) -> None:
        if self._is_read_only:
            return
        insert_index = len(self._rows)
        self._table_model.begin_insert_row(insert_index)
        self._rows.append(self._empty_row())
        self._table_model.end_insert_row()
        self._set_dirty(self._rows != self._initial_rows)
        self.rowsChanged.emit()

    @Slot(int)
    def remove_row(self, index: int) -> None:
        if self._is_read_only:
            return
        if 0 <= index < len(self._rows):
            self._table_model.begin_remove_row(index)
            self._rows.pop(index)
            self._table_model.end_remove_row()
            if not self._rows:
                self._table_model.begin_insert_row(0)
                self._rows.append(self._empty_row())
                self._table_model.end_insert_row()
            self._refresh_validation()
            self._set_dirty(self._rows != self._initial_rows)
            self.rowsChanged.emit()

    @Slot(int, str, "QVariant")
    def set_row_field(self, index: int, field_name: str, value: Any) -> None:
        if self._is_read_only:
            return
        if 0 <= index < len(self._rows):
            self._rows[index][field_name] = "" if value is None else value
            self._set_error_message("")
            self._refresh_validation()
            self._set_dirty(self._rows != self._initial_rows)
            self._table_model.emit_row_changed(index)
            self.rowsChanged.emit()

    @Slot(int, str, result=str)
    def row_error(self, index: int, field_name: str) -> str:
        return self._field_errors.get(f"row_{index}_{field_name}", "")

    @Slot(result=bool)
    def save_section(self) -> bool:
        if self._is_read_only:
            return False
        if self._save_handler is None:
            return False
        return bool(self._save_handler("ordenes_combustible"))

    @Slot()
    def reset_section(self) -> None:
        if self._is_read_only:
            return
        self._table_model.begin_model_reset()
        self._rows = [dict(row) for row in self._initial_rows]
        self._field_errors = {}
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self._table_model.end_model_reset()
        self.rowsChanged.emit()
        self.fieldErrorsChanged.emit()

    def build_payload(self) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for row in self._rows:
            if self._is_empty_row(row):
                continue
            item = {
                "gasolinera": normalize_field_value(
                    kind=FieldKind.ENUM,
                    value=row.get("gasolinera"),
                    required=True,
                    nullable=False,
                    options=_enum_options(Gasolinera),
                ),
                "numero_orden": normalize_field_value(
                    kind=FieldKind.TEXT,
                    value=row.get("numero_orden"),
                    required=True,
                    nullable=False,
                ),
                "galones_autorizados": normalize_field_value(
                    kind=FieldKind.NUMBER,
                    value=row.get("galones_autorizados"),
                    required=True,
                    nullable=False,
                ),
                "tipo": normalize_field_value(
                    kind=FieldKind.ENUM,
                    value=row.get("tipo"),
                    required=True,
                    nullable=False,
                    options=_enum_options(TipoOrdenCombustible),
                ),
            }
            if row.get("id") not in (None, ""):
                result = row.get("id")
                assert result is not None
                item["id"] = int(result)
            item["galones_autorizados"] = float(str(item["galones_autorizados"]))
            payload.append(item)
        if not payload:
            raise ValueError("Debes registrar al menos una orden de combustible.")
        return payload

    def reset_rows(self) -> None:
        self.load_rows([self._empty_row()])

    def _refresh_validation(self) -> None:
        errors: dict[str, str] = {}
        has_rows = False
        for index, row in enumerate(self._rows):
            if self._is_empty_row(row):
                continue
            has_rows = True
            for field_name, kind, options in (
                ("gasolinera", FieldKind.ENUM, _enum_options(Gasolinera)),
                ("numero_orden", FieldKind.TEXT, ()),
                ("galones_autorizados", FieldKind.NUMBER, ()),
                ("tipo", FieldKind.ENUM, _enum_options(TipoOrdenCombustible)),
            ):
                error = validate_field_value(
                    kind=kind,
                    value=row.get(field_name),
                    required=True,
                    nullable=False,
                    options=options,
                )
                if error:
                    errors[f"row_{index}_{field_name}"] = error
        if not has_rows:
            errors["ordenes_combustible"] = "Debes registrar al menos una orden de combustible."
        self._field_errors = errors
        self._set_valid(not errors)
        self.fieldErrorsChanged.emit()

    @staticmethod
    def _empty_row() -> dict[str, Any]:
        return {
            "id": None,
            "gasolinera": "",
            "numero_orden": "",
            "galones_autorizados": "",
            "tipo": str(TipoOrdenCombustible.CAMION.value),
        }

    @staticmethod
    def _is_empty_row(row: Mapping[str, Any]) -> bool:
        return all(row.get(field_name) in (None, "") for field_name in ("gasolinera", "numero_orden", "galones_autorizados"))

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

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def set_read_only(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_read_only != normalized:
            self._is_read_only = normalized
            self.readOnlyChanged.emit(normalized)


@QmlNamedElement("FuelOrdersTableModel")
@QmlUncreatable("FuelOrdersTableModel instances are created by FuelOrdersSectionFormViewModel.")
@QmlNamedElement("FuelOrdersTableModel")
@QmlUncreatable("FuelOrdersTableModel instances are created by FuelOrdersSectionFormViewModel.")
class FuelOrdersTableModel(QAbstractTableModel):
    _ROW_DATA_ROLE = Qt.ItemDataRole.UserRole + 1
    _ROW_INDEX_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, form: FuelOrdersSectionFormViewModel) -> None:
        super().__init__(form)
        self._form = form

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._form._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._form._row_fields)

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
            field_name = str(self._form._row_fields[column].get("name", ""))
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

        if 0 <= column < len(self._form._row_fields):
            return dict(self._form._row_fields[column])

        return {}

    @Slot(int, int, "QVariant")
    def set_cell_value(self, row: int, column: int, value: Any) -> None:
        try:
            row = int(row)
            column = int(column)
        except (TypeError, ValueError):
            return

        if not (0 <= row < len(self._form._rows)):
            return

        if not (0 <= column < len(self._form._row_fields)):
            return

        field_name = str(self._form._row_fields[column].get("name", ""))
        if not field_name:
            return

        self._form.set_row_field(row, field_name, value)

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
            and 0 <= index.column() < len(self._form._row_fields)
        )


@QmlNamedElement("DetalleOperacionViewModel")
@QmlUncreatable("DetalleOperacionViewModel instances are created by ViajeWorkflowViewModel.")
class DetalleOperacionViewModel(BaseViewModel):
    summaryChanged = Signal()
    viajeSummaryChanged = Signal()
    visibleSectionsChanged = Signal()
    activeTabChanged = Signal(str)
    hasUnsavedChangesChanged = Signal(bool)
    canSaveAllChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    closedChanged = Signal(bool)

    def __init__(
        self,
        *,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        can_modify: bool = True,
    ) -> None:
        super().__init__()
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._summary: dict[str, Any] = {}
        self._viaje_summary: dict[str, Any] = {}
        self._visible_sections: list[str] = []
        self._active_tab = "descarga"
        self._error_message = ""
        self._record_id: int | None = None
        self._detalle_operacion_id: int | None = None
        self._is_closed = False
        self._can_modify = bool(can_modify)
        self._descarga_form = DetailSectionFormViewModel(
            section_key="descarga",
            title="Descarga",
            fields=_DESCARGA_FIELDS,
            form_layout=_DESCARGA_LAYOUT,
            workflow_service=workflow_service,
            reference_lookup_service=reference_lookup_service,
        )
        self._combustible_thermo_form = DetailSectionFormViewModel(
            section_key="combustible_thermo",
            title="Combustible del Thermo",
            fields=_THERMO_FIELDS,
            form_layout=_THERMO_LAYOUT,
            workflow_service=workflow_service,
            reference_lookup_service=reference_lookup_service,
        )
        self._ordenes_combustible_form = FuelOrdersSectionFormViewModel()
        self._descarga_form.set_save_handler(self.save_section)
        self._combustible_thermo_form.set_save_handler(self.save_section)
        self._ordenes_combustible_form.set_save_handler(self.save_section)
        for form in (self._descarga_form, self._combustible_thermo_form, self._ordenes_combustible_form):
            form.dirtyChanged.connect(self._emit_aggregate_state)
            form.validChanged.connect(self._emit_aggregate_state)
            form.busyChanged.connect(self._emit_aggregate_state)
        self.reset()

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, Any]:
        return dict(self._summary)

    @Property("QVariantMap", notify=viajeSummaryChanged)
    def viaje_summary(self) -> dict[str, Any]:
        return dict(self._viaje_summary)

    @Property("QVariantList", notify=visibleSectionsChanged)
    def visible_sections(self) -> list[str]:
        return list(self._visible_sections)

    @Property(str, notify=activeTabChanged)
    def active_tab(self) -> str:
        return self._active_tab

    @Property(bool, notify=hasUnsavedChangesChanged)
    def has_unsaved_changes(self) -> bool:
        return any(self.section_state(section_key)["dirty"] for section_key in self._visible_sections)

    @Property(bool, notify=canSaveAllChanged)
    def can_save_all(self) -> bool:
        return (
            bool(self._visible_sections)
            and self._can_modify
            and not self._is_closed
            and all(self.section_state(section_key)["valid"] for section_key in self._visible_sections)
        )

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(bool, notify=closedChanged)
    def is_closed(self) -> bool:
        return self._is_closed

    @Property(DetailSectionFormViewModel, constant=True)
    def descarga_form(self) -> DetailSectionFormViewModel:
        return self._descarga_form

    @Property(DetailSectionFormViewModel, constant=True)
    def combustible_thermo_form(self) -> DetailSectionFormViewModel:
        return self._combustible_thermo_form

    @Property(FuelOrdersSectionFormViewModel, constant=True)
    def ordenes_combustible_form(self) -> FuelOrdersSectionFormViewModel:
        return self._ordenes_combustible_form

    def load(self, record_id: int) -> None:
        self.is_busy = True
        try:
            self._set_error_message("")
            self._apply_summary(self._workflow_service.viaje.get_detail_summary(int(record_id)))
        except Exception as exc:
            self._set_error_message(str(exc))
            raise
        finally:
            self.is_busy = False

    @Slot()
    def reset(self) -> None:
        self._summary = {}
        self._viaje_summary = {}
        self._visible_sections = []
        self._record_id = None
        self._detalle_operacion_id = None
        self._set_closed(False)
        self._active_tab = "descarga"
        self._descarga_form.load_from_record({})
        self._combustible_thermo_form.load_from_record({})
        self._ordenes_combustible_form.load_rows([])
        self._set_error_message("")
        self.summaryChanged.emit()
        self.viajeSummaryChanged.emit()
        self.visibleSectionsChanged.emit()
        self.activeTabChanged.emit(self._active_tab)
        self._emit_aggregate_state()

    @Slot(str)
    def set_active_tab(self, section_key: str) -> None:
        normalized = str(section_key or "").strip()
        if not normalized:
            return
        if self._active_tab != normalized:
            self._active_tab = normalized
            self.activeTabChanged.emit(normalized)

    @Slot(str, result=dict)
    def section_state(self, section_key: str) -> dict[str, Any]:
        section_map = {
            "descarga": self._descarga_form,
            "combustible_thermo": self._combustible_thermo_form,
            "ordenes_combustible": self._ordenes_combustible_form,
        }
        form = section_map.get(str(section_key))
        if form is None:
            return {"visible": False, "dirty": False, "valid": True, "busy": False}
        return {
            "visible": str(section_key) in self._visible_sections,
            "dirty": bool(form.is_dirty),
            "valid": bool(form.is_valid),
            "busy": bool(form.is_busy),
            "read_only": self._is_closed or not self._can_modify,
            "title": getattr(form, "title", str(section_key)),
        }

    @Slot(str, result=bool)
    def save_section(self, section_key: str) -> bool:
        if not self._can_modify:
            self._set_error_message("No tienes permiso para modificar viaje")
            return False
        if self._is_closed:
            return False
        normalized = str(section_key or "").strip()
        if normalized not in self._visible_sections or self._detalle_operacion_id is None:
            return False
        try:
            self._set_error_message("")
            payload = self._build_payload_for_section(normalized)
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

        self.is_busy = True
        try:
            self._workflow_service.detalle_operacion.actualizar_secciones(self._detalle_operacion_id, payload)
            self._reload()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self.is_busy = False

    @Slot(result=bool)
    def save_all(self) -> bool:
        if not self._can_modify:
            self._set_error_message("No tienes permiso para modificar viaje")
            return False
        if self._is_closed:
            return False
        if self._detalle_operacion_id is None:
            return False
        try:
            self._set_error_message("")
            payload: dict[str, Any] = {}
            for section_key in self._visible_sections:
                payload.update(self._build_payload_for_section(section_key))
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

        self.is_busy = True
        try:
            self._workflow_service.detalle_operacion.actualizar_secciones(self._detalle_operacion_id, payload)
            self._reload()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self.is_busy = False

    @Slot(result=bool)
    def close_detail(self) -> bool:
        if not self._can_modify:
            self._set_error_message("No tienes permiso para modificar viaje")
            return False
        if self._is_closed:
            return False
        if self._record_id is None:
            return False
        if not self.save_all():
            return False

        self.is_busy = True
        try:
            self._set_error_message("")
            self._workflow_service.viaje.terminar_viaje(self._record_id)
            self._reload()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self.is_busy = False

    @Slot(result=bool)
    def reopen_detail(self) -> bool:
        if not self._can_modify:
            self._set_error_message("No tienes permiso para modificar viaje")
            return False
        if not self._is_closed:
            return False
        if self._record_id is None:
            return False

        self.is_busy = True
        try:
            self._set_error_message("")
            self._workflow_service.viaje.reabrir_viaje(self._record_id)
            self._reload()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False
        finally:
            self.is_busy = False

    def _reload(self) -> None:
        if self._record_id is None:
            return
        self._apply_summary(self._workflow_service.viaje.get_detail_summary(self._record_id))

    def _apply_summary(self, summary: Mapping[str, Any]) -> None:
        normalized = dict(summary)
        viaje = normalized.get("viaje")
        detalle = normalized.get("detalle_operacion")
        self._summary = normalized
        self._viaje_summary = dict(normalized.get("viaje_summary") or viaje or {})
        self._visible_sections = [str(item) for item in normalized.get("visible_sections", [])]
        self._record_id = _extract_id_as_int(viaje)
        self._detalle_operacion_id = _extract_id_as_int(detalle)
        self._set_closed(self._summary_indicates_closed(detalle))
        self._descarga_form.load_from_record(normalized.get("descarga") or {})
        self._combustible_thermo_form.load_from_record(
            {
                **dict(normalized.get("actividad_thermo") or {}),
                **dict(normalized.get("gasto_real_thermo") or {}),
            }
        )
        self._ordenes_combustible_form.load_rows(list(normalized.get("ordenes_combustible") or []))
        self._apply_read_only_to_forms()
        if self._active_tab not in self._visible_sections:
            self._active_tab = self._visible_sections[0] if self._visible_sections else "descarga"
            self.activeTabChanged.emit(self._active_tab)
        self.summaryChanged.emit()
        self.viajeSummaryChanged.emit()
        self.visibleSectionsChanged.emit()
        self._emit_aggregate_state()

    def _build_payload_for_section(self, section_key: str) -> dict[str, Any]:
        if section_key == "descarga":
            self._descarga_form._refresh_validation()
            if not self._descarga_form.is_valid:
                raise ValueError("La sección Descarga es inválida.")
            return {"descarga": self._descarga_form.build_payload()}
        if section_key == "combustible_thermo":
            self._combustible_thermo_form._refresh_validation()
            if not self._combustible_thermo_form.is_valid:
                raise ValueError("La sección Combustible del Thermo es inválida.")
            thermo_payload = self._combustible_thermo_form.build_payload()
            return {
                "actividad_thermo": {
                    "fecha_hora_encendido": thermo_payload.get("fecha_hora_encendido"),
                    "fecha_hora_apagado": thermo_payload.get("fecha_hora_apagado"),
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": thermo_payload.get("combustible_base_thermo"),
                    "restante_thermo": thermo_payload.get("restante_thermo"),
                },
            }
        if section_key == "ordenes_combustible":
            self._ordenes_combustible_form._refresh_validation()
            if not self._ordenes_combustible_form.is_valid:
                raise ValueError("La sección Ordenes de Combustible es inválida.")
            return {"ordenes_combustible": self._ordenes_combustible_form.build_payload()}
        return {}

    def _emit_aggregate_state(self, *_args: Any) -> None:
        self.hasUnsavedChangesChanged.emit(self.has_unsaved_changes)
        self.canSaveAllChanged.emit(self.can_save_all)

    def _set_closed(self, value: bool) -> None:
        normalized = bool(value)
        if self._is_closed != normalized:
            self._is_closed = normalized
            self.closedChanged.emit(normalized)
        self._apply_read_only_to_forms()

    def _apply_read_only_to_forms(self) -> None:
        for form in (self._descarga_form, self._combustible_thermo_form, self._ordenes_combustible_form):
            form.set_read_only(self._is_closed or not self._can_modify)

    def set_can_modify(self, value: bool) -> None:
        normalized = bool(value)
        if self._can_modify != normalized:
            self._can_modify = normalized
            self._apply_read_only_to_forms()
            self._emit_aggregate_state()

    @staticmethod
    def _summary_indicates_closed(detalle: Any) -> bool:
        if not isinstance(detalle, Mapping):
            return False
        return str(detalle.get("estado") or "").strip().casefold() == "cerrado"

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)
