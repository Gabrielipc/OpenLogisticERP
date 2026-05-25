"""Form view models and contracts for pluggable catalog forms."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ...application.modelo.reference_service import ReferenceLookupService
from ...application.modelo.services import ModeloCatalogService
from ...domain.modelo.dtos import ReferenceFieldDTO, ReferenceOptionDTO
from ...domain.modelo.field_validation import (
    format_field_value_for_ui,
    normalize_field_value,
    validate_field_value,
)
from ...shared.errors import PersistenceConstraintError
from ..qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ..viewmodels.base_view_model import BaseViewModel
from .definitions import FormFieldOption, GenericFormFieldDefinition
from .form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from .serialization import serialize_catalog_value
from .types import FormMode

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


class FormViewModelContract(Protocol):
    mode: str
    record_id: object
    title: str
    is_busy: bool
    is_dirty: bool
    is_valid: bool
    error_message: str

    def load(self, record_id: int | None) -> None:
        ...

    def reset(self) -> None:
        ...

    def submit(self) -> Mapping[str, Any] | None:
        ...

    def cancel(self) -> None:
        ...


@QmlNamedElement("BaseFormViewModel")
@QmlUncreatable("BaseFormViewModel instances are created in Python and injected into QML.")
class BaseFormViewModel(BaseViewModel):
    """Stable QObject-based contract for list-compatible forms."""

    modeChanged = Signal(str)
    recordIdChanged = Signal(object)
    titleChanged = Signal(str)
    dirtyChanged = Signal(bool)
    validChanged = Signal(bool)
    errorMessageChanged = Signal(str)
    readOnlyChanged = Signal(bool)
    loaded = Signal("QVariantMap")
    saved = Signal("QVariantMap")
    cancelled = Signal()

    def __init__(self, title: str = "") -> None:
        super().__init__()
        self._mode = FormMode.CREATE
        self._record_id: int | None = None
        self._title = title
        self._is_dirty = False
        self._is_valid = True
        self._error_message = ""

    @Property(str, notify=modeChanged)
    def mode(self) -> str:
        return self._mode.value

    @Property(object, notify=recordIdChanged)
    def record_id(self) -> object:
        return self._record_id

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        return self._title

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
        return self._mode == FormMode.VIEW

    def _set_mode(self, mode: FormMode) -> None:
        if self._mode != mode:
            was_read_only = self.is_read_only
            self._mode = mode
            self.modeChanged.emit(mode.value)
            if self.is_read_only != was_read_only:
                self.readOnlyChanged.emit(self.is_read_only)

    def _set_record_id(self, record_id: int | None) -> None:
        if self._record_id != record_id:
            self._record_id = record_id
            self.recordIdChanged.emit(record_id)

    def _set_title(self, title: str) -> None:
        if self._title != title:
            self._title = title
            self.titleChanged.emit(title)

    def _set_dirty(self, is_dirty: bool) -> None:
        is_dirty = bool(is_dirty)
        if self._is_dirty != is_dirty:
            self._is_dirty = is_dirty
            self.dirtyChanged.emit(is_dirty)

    def _set_valid(self, is_valid: bool) -> None:
        is_valid = bool(is_valid)
        if self._is_valid != is_valid:
            self._is_valid = is_valid
            self.validChanged.emit(is_valid)

    def _set_error_message(self, message: str) -> None:
        message = str(message or "")
        if self._error_message != message:
            self._error_message = message
            self.errorMessageChanged.emit(message)

    def load(self, record_id: int | None) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def submit(self) -> Mapping[str, Any] | None:
        raise NotImplementedError

    def cancel(self) -> None:
        self.cancelled.emit()

    @Slot(result=bool)
    def submit_form(self) -> bool:
        if self.is_read_only:
            self._set_error_message("El formulario esta en modo solo lectura.")
            return False
        return self.submit() is not None

    @Slot()
    def cancel_form(self) -> None:
        self.cancel()


@QmlNamedElement("GenericCatalogFormViewModel")
@QmlUncreatable("GenericCatalogFormViewModel instances are created in Python and injected into QML.")
class GenericCatalogFormViewModel(BaseFormViewModel):
    """Metadata-driven form view model for simple catalog entities."""

    valuesChanged = Signal()
    fieldsChanged = Signal()
    fieldErrorsChanged = Signal()
    layoutItemsChanged = Signal()

    def __init__(
        self,
        catalog_name: str,
        fields: tuple[GenericFormFieldDefinition, ...],
        catalog_service: ModeloCatalogService,
        reference_lookup_service: ReferenceLookupService | None = None,
        form_layout: FormLayoutDefinition | None = None,
        title: str | None = None,
    ) -> None:
        super().__init__(title=title or catalog_name.title())
        self._catalog_name = catalog_name
        self._fields = fields
        self._field_map = {field.name: field for field in fields}
        self._catalog_service = catalog_service
        self._reference_lookup_service = reference_lookup_service
        self._form_layout = form_layout
        self._values: dict[str, Any] = {}
        self._initial_values: dict[str, Any] = {}
        self._reference_options: dict[str, tuple[ReferenceOptionDTO, ...]] = {}
        self._reference_display_values: dict[str, str] = {}
        self._validation_field_errors: dict[str, str] = {}
        self._persistence_field_errors: dict[str, str] = {}
        self._field_errors: dict[str, str] = {}
        self._transient_error_message = ""
        self._persistence_error_message = ""
        self.reset()

    @Property("QVariantMap", notify=valuesChanged)
    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @Property("QVariantList", notify=fieldsChanged)
    def fields(self) -> list[dict[str, Any]]:
        return [self._serialize_field(field) for field in self._fields]

    @Property("QVariantMap", notify=fieldErrorsChanged)
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)

    @Property("QVariantList", notify=layoutItemsChanged)
    def layout_items(self) -> list[dict[str, Any]]:
        return self._serialize_layout_items()

    def load(self, record_id: int | None) -> None:
        self.is_busy = True
        self._reset_error_state()
        try:
            if record_id is None:
                self._set_mode(FormMode.CREATE)
                self._set_record_id(None)
                values = self._default_values()
                self._set_title(f"Nuevo {self._catalog_name}")
            else:
                record = self._catalog_service.get(self._catalog_name, int(record_id))
                if record is None:
                    raise ValueError(f"No se encontro {self._catalog_name} con id={record_id}")
                self._set_mode(FormMode.VIEW if self._mode == FormMode.VIEW else FormMode.EDIT)
                self._set_record_id(int(record_id))
                values = self._values_from_record(record)
                action_label = "Detalle" if self._mode == FormMode.VIEW else "Editar"
                self._set_title(f"{action_label} {self._catalog_name}")

            self._replace_values(values, dirty=False)
            self._prime_reference_fields()
            self.loaded.emit(dict(self._values))
        except Exception as exc:
            self._set_transient_error_message(str(exc))
            self._set_valid(False)
        finally:
            self.is_busy = False

    def reset(self) -> None:
        self._reference_options = {}
        self._reference_display_values = {}
        self._replace_values(self._default_values(), dirty=False)
        self._set_mode(FormMode.CREATE)
        self._set_record_id(None)
        self._set_title(f"Nuevo {self._catalog_name}")
        self._reset_error_state()
        self.fieldsChanged.emit()
        self.layoutItemsChanged.emit()

    @Slot(str, "QVariant")
    def set_field_value(self, field_name: str, value: Any) -> None:
        if self.is_read_only:
            return
        if field_name not in self._values:
            raise KeyError(f"Campo desconocido: {field_name}")
        field = self._field(field_name)
        self._values[field_name] = self._coerce_ui_value(field, value)
        if field.reference is not None:
            self._reference_display_values.pop(field_name, None)
        self._set_dirty(self._values != self._initial_values)
        self._set_transient_error_message("")
        self._clear_persistence_error_for_field(field_name)
        self._refresh_validation()
        self.valuesChanged.emit()
        self.layoutItemsChanged.emit()

    @Slot(str, "QVariant", str)
    def set_reference_field_value(self, field_name: str, value: Any, label: str) -> None:
        if self.is_read_only:
            return
        field = self._field_by_name(field_name)
        if field.reference is None:
            self.set_field_value(field_name, value)
            return
        self._values[field_name] = self._coerce_ui_value(field, value)
        normalized_label = str(label or "").strip()
        if normalized_label:
            self._reference_display_values[field_name] = normalized_label
        else:
            self._reference_display_values.pop(field_name, None)
        self._set_dirty(self._values != self._initial_values)
        self._set_transient_error_message("")
        self._clear_persistence_error_for_field(field_name)
        self._refresh_validation()
        self.valuesChanged.emit()
        self.fieldsChanged.emit()
        self.layoutItemsChanged.emit()

    def submit(self) -> Mapping[str, Any] | None:
        if self.is_read_only:
            self._set_transient_error_message("El formulario esta en modo solo lectura.")
            return None
        self._set_transient_error_message("")
        self._clear_persistence_errors()
        self._refresh_validation()
        if not self.is_valid:
            self._set_transient_error_message("Formulario invalido")
            return None

        try:
            payload = self._build_payload()
        except ValueError as exc:
            self._set_transient_error_message(str(exc))
            self._refresh_validation()
            return None

        self.is_busy = True
        try:
            if self._mode == FormMode.CREATE:
                result = self._catalog_service.create(self._catalog_name, payload)
                new_record_id = result.get("id")
                self._set_record_id(int(new_record_id) if new_record_id is not None else None)
                self._set_mode(FormMode.EDIT)
                self._set_title(f"Editar {self._catalog_name}")
            else:
                if self._record_id is None:
                    raise ValueError("record_id es requerido para editar")
                result = self._catalog_service.update(self._catalog_name, int(self._record_id), payload)

            self._replace_values(self._values_from_record(result), dirty=False)
            self._reset_error_state()
            self._prime_reference_fields()
            self.saved.emit(dict(result))
            return result
        except PersistenceConstraintError as exc:
            self._apply_persistence_error(exc)
            return None
        except Exception as exc:
            self._set_transient_error_message(str(exc))
            return None
        finally:
            self.is_busy = False

    def _replace_values(self, values: Mapping[str, Any], *, dirty: bool) -> None:
        self._values = dict(values)
        self._initial_values = dict(values)
        self._set_dirty(dirty)
        self._refresh_validation()
        self.valuesChanged.emit()
        self.layoutItemsChanged.emit()

    def _default_values(self) -> dict[str, Any]:
        return {field.name: self._format_for_ui(field, field.resolve_default()) for field in self._fields}

    def _values_from_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        reference_display_values: dict[str, str] = {}
        for field in self._fields:
            raw_value = record.get(field.name, field.resolve_default())
            raw_value = self._format_for_ui(field, raw_value)
            if field.load_transform is not None:
                raw_value = field.load_transform(raw_value)
            values[field.name] = raw_value
            if field.reference is not None and field.display_field_key:
                display_value = record.get(field.display_field_key)
                if display_value not in (None, ""):
                    reference_display_values[field.name] = str(display_value)
        self._reference_display_values = reference_display_values
        return values

    def _build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in self._fields:
            if not field.editable:
                continue
            value = self._normalize_field_value(field, self._values.get(field.name))
            if field.submit_transform is not None:
                value = field.submit_transform(value)
            payload[field.name] = value
        return payload

    def _refresh_validation(self) -> None:
        field_errors = {
            field.name: error
            for field in self._fields
            if (error := self._validate_field(field, self._values.get(field.name))) is not None
        }
        self._validation_field_errors = field_errors
        self._sync_field_errors()

    def _serialize_field(self, field: GenericFormFieldDefinition) -> dict[str, Any]:
        options = field.options
        if field.reference is not None:
            reference_options = tuple(
                FormFieldOption(value=option.value, label=option.label)
                for option in self._reference_options.get(field.name, ())
            )
            if not reference_options:
                current_value = self._values.get(field.name)
                cached_label = self._reference_display_values.get(field.name, "").strip()
                if current_value not in (None, "") and cached_label:
                    reference_options = (FormFieldOption(value=current_value, label=cached_label),)
            options = reference_options
        return {
            "name": field.name,
            "label": field.label or field.name.replace("_", " ").title(),
            "field_type": field.field_type,
            "kind": field.kind or field.field_type,
            "required": field.required,
            "editable": field.editable,
            "nullable": field.nullable,
            "precision": field.precision,
            "display_format": field.display_format or "",
            "display_field_key": field.display_field_key or "",
            "options": [self._serialize_option(option) for option in options],
            "reference": self._serialize_reference(field.reference),
        }

    def _serialize_layout_items(self) -> list[dict[str, Any]]:
        serialized_fields = {field.name: self._serialize_field(field) for field in self._fields}
        layout_items: list[dict[str, Any]] = []
        pending_row: list[dict[str, Any]] = []
        consumed_fields: set[str] = set()

        def flush_row() -> None:
            if not pending_row:
                return
            layout_items.append({"type": "row", "fields": list(pending_row)})
            pending_row.clear()

        for item in self._layout_definition_items():
            if isinstance(item, FormLayoutSectionItem):
                flush_row()
                layout_items.append({"type": "section", "title": item.title})
                continue

            field = serialized_fields.get(item.field_name)
            if field is None or item.field_name in consumed_fields:
                continue

            consumed_fields.add(item.field_name)
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

        for field in self._fields:
            if field.name in consumed_fields:
                continue
            entry = {
                **serialized_fields[field.name],
                "span": 1,
                "full_width": False,
            }
            if len(pending_row) >= 2:
                flush_row()
            pending_row.append(entry)
            if len(pending_row) >= 2:
                flush_row()

        flush_row()
        return layout_items

    def _layout_definition_items(self) -> tuple[FormLayoutFieldItem | FormLayoutSectionItem, ...]:
        if self._form_layout is not None and self._form_layout.items:
            return self._form_layout.items
        return tuple(FormLayoutFieldItem(field_name=field.name) for field in self._fields)

    def _field(self, field_name: str) -> GenericFormFieldDefinition:
        return self._field_map[field_name]

    def _coerce_ui_value(self, field: GenericFormFieldDefinition, value: Any) -> Any:
        serialized = self._serialize_value(value)
        if field.kind == "bool":
            return bool(serialized)
        if serialized is None:
            return ""
        if field.kind in {"enum", "reference"}:
            return serialized
        return str(serialized)

    def _validate_field(self, field: GenericFormFieldDefinition, value: Any) -> str | None:
        return validate_field_value(
            kind=field.kind or field.field_type,
            value=value,
            required=field.required,
            nullable=field.nullable,
            options=field.options,
        )

    def _normalize_field_value(self, field: GenericFormFieldDefinition, value: Any) -> Any:
        return normalize_field_value(
            kind=field.kind or field.field_type,
            value=value,
            required=field.required,
            nullable=field.nullable,
            options=field.options,
        )

    def _format_for_ui(self, field: GenericFormFieldDefinition, value: Any) -> Any:
        return format_field_value_for_ui(
            kind=field.kind or field.field_type,
            value=self._serialize_value(value),
            precision=field.precision,
        )

    @staticmethod
    def _serialize_option(option: FormFieldOption) -> dict[str, Any]:
        return {
            "value": GenericCatalogFormViewModel._serialize_value(option.value),
            "label": option.display_label(),
        }

    @staticmethod
    def _serialize_reference(reference: ReferenceFieldDTO | None) -> dict[str, Any] | None:
        if reference is None:
            return None
        return {
            "lookup_key": reference.lookup_key,
            "min_search_chars": reference.min_search_chars,
            "page_size": reference.page_size,
            "value_field": reference.value_field,
            "label_field": reference.label_field,
        }

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        return serialize_catalog_value(value)

    def _field_by_name(self, field_name: str) -> GenericFormFieldDefinition:
        field = self._field_map.get(field_name)
        if field is None:
            raise KeyError(f"Campo desconocido: {field_name}")
        return field

    def _prime_reference_fields(self) -> None:
        changed = False
        for field in self._fields:
            if field.reference is None:
                continue
            options = self._load_current_reference_options(field)
            if self._reference_options.get(field.name) != options:
                self._reference_options[field.name] = options
                changed = True
        if changed:
            self.fieldsChanged.emit()
            self.layoutItemsChanged.emit()

    def _load_current_reference_options(
        self,
        field: GenericFormFieldDefinition,
    ) -> tuple[ReferenceOptionDTO, ...]:
        if field.reference is None or self._reference_lookup_service is None:
            return ()
        current_value = self._values.get(field.name)
        if current_value in (None, ""):
            return ()
        cached_label = self._reference_display_values.get(field.name, "").strip()
        if cached_label:
            return (ReferenceOptionDTO(value=current_value, label=cached_label),)
        resolved = self._reference_lookup_service.resolve_ids(field.reference.lookup_key, [current_value])
        if current_value not in resolved:
            if len(resolved) == 1:
                return (next(iter(resolved.values())),)
            return ()
        option = resolved[current_value]
        self._reference_display_values[field.name] = option.label
        return (option,)

    def _load_initial_reference_options(
        self,
        field: GenericFormFieldDefinition,
    ) -> tuple[ReferenceOptionDTO, ...]:
        if field.reference is None:
            return ()
        if self._reference_lookup_service is None:
            raise RuntimeError("ReferenceLookupService no configurado para este formulario")
        return tuple(
            self._reference_lookup_service.search(
                field.reference.lookup_key,
                "",
                field.reference.page_size,
            )
        )

    def _search_reference_options(
        self,
        field: GenericFormFieldDefinition,
        term: str,
    ) -> tuple[ReferenceOptionDTO, ...]:
        if field.reference is None:
            return ()
        if self._reference_lookup_service is None:
            raise RuntimeError("ReferenceLookupService no configurado para este formulario")
        normalized_term = str(term or "")
        if len(normalized_term.strip()) < field.reference.min_search_chars:
            return self._load_current_reference_options(field)

        options = list(
            self._reference_lookup_service.search(
                field.reference.lookup_key,
                normalized_term,
                field.reference.page_size,
            )
        )
        current_value = self._values.get(field.name)
        if current_value not in (None, "") and all(option.value != current_value for option in options):
            current_options = self._load_current_reference_options(field)
            options = [*current_options, *options]
        return tuple(options)

    @Slot(str)
    def prime_reference_field(self, field_name: str) -> None:
        field = self._field_by_name(field_name)
        if field.reference is None:
            return
        options = self._load_current_reference_options(field)
        if not options:
            options = self._load_initial_reference_options(field)
        if self._reference_options.get(field_name) != options:
            self._reference_options[field_name] = options
            self.fieldsChanged.emit()
            self.layoutItemsChanged.emit()

    @Slot(str, str)
    def search_reference_options(self, field_name: str, term: str) -> None:
        field = self._field_by_name(field_name)
        if field.reference is None:
            return
        options = self._search_reference_options(field, term)
        if self._reference_options.get(field_name) != options:
            self._reference_options[field_name] = options
            self.fieldsChanged.emit()
            self.layoutItemsChanged.emit()

    def _apply_persistence_error(self, error: PersistenceConstraintError) -> None:
        self._persistence_field_errors = dict(error.field_errors)
        self._persistence_error_message = error.summary_message
        self._sync_field_errors()
        self._sync_error_message()

    def _clear_persistence_errors(self) -> None:
        self._persistence_field_errors = {}
        self._persistence_error_message = ""
        self._sync_field_errors()
        self._sync_error_message()

    def _clear_persistence_error_for_field(self, field_name: str) -> None:
        if field_name not in self._persistence_field_errors:
            self._sync_error_message()
            return
        updated_errors = dict(self._persistence_field_errors)
        updated_errors.pop(field_name, None)
        self._persistence_field_errors = updated_errors
        if not updated_errors:
            self._persistence_error_message = ""
        self._sync_field_errors()
        self._sync_error_message()

    def _reset_error_state(self) -> None:
        self._transient_error_message = ""
        self._persistence_error_message = ""
        self._persistence_field_errors = {}
        self._sync_field_errors()
        self._sync_error_message()

    def _set_transient_error_message(self, message: str) -> None:
        message = str(message or "")
        if self._transient_error_message != message:
            self._transient_error_message = message
        self._sync_error_message()

    def _sync_error_message(self) -> None:
        self._set_error_message(self._persistence_error_message or self._transient_error_message)

    def _sync_field_errors(self) -> None:
        merged_errors = dict(self._validation_field_errors)
        merged_errors.update(self._persistence_field_errors)
        if self._field_errors != merged_errors:
            self._field_errors = merged_errors
            self.fieldErrorsChanged.emit()
        self._set_valid(not merged_errors)
