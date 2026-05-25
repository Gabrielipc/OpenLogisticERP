"""Specialized workflow form view model for Viaje."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloWorkflowService
from ....domain.modelo.dtos import FieldKind, FieldOptionDTO, ReferenceFieldDTO, ReferenceOptionDTO
from ....domain.modelo.field_validation import format_field_value_for_ui, normalize_field_value, validate_field_value
from ....infrastructure.persistence.modelo.workflow_orm import Gasolinera, Moneda, TipoOrdenCombustible, TipoViaje
from ...catalog.definitions import GenericFormFieldDefinition
from ...catalog.form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from ...catalog.forms import BaseFormViewModel
from ...catalog.types import FormMode
from ...qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


def _enum_options(enum_cls: type[Enum]) -> tuple[FieldOptionDTO, ...]:
    return tuple(FieldOptionDTO(value=str(member.value), label=str(member.value)) for member in enum_cls)


VIAJE_HEADER_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutSectionItem(title="Cabecera"),
        FormLayoutFieldItem(field_name="cliente_id"),
        FormLayoutFieldItem(field_name="referencia"),
        FormLayoutFieldItem(field_name="descripcion", full_width=True),
        FormLayoutSectionItem(title="Ruta"),
        FormLayoutFieldItem(field_name="origen_id"),
        FormLayoutFieldItem(field_name="destino_id"),
        FormLayoutFieldItem(field_name="fecha_posicionamiento", full_width=True),
        FormLayoutSectionItem(title="Equipo"),
        FormLayoutFieldItem(field_name="conductor_id"),
        FormLayoutFieldItem(field_name="furgon_id"),
        FormLayoutFieldItem(field_name="camion_id"),
        FormLayoutFieldItem(field_name="thermo_id"),
        FormLayoutSectionItem(title="Operación"),
        FormLayoutFieldItem(field_name="viaticos_monto"),
        FormLayoutFieldItem(field_name="viaticos_moneda"),
        FormLayoutFieldItem(field_name="temperatura", full_width=True),
        FormLayoutFieldItem(field_name="viaje_ida_id", full_width=True),
    )
)


@QmlNamedElement("ViajeFormViewModel")
@QmlUncreatable("ViajeFormViewModel instances are created in Python and injected into QML.")
class ViajeFormViewModel(BaseFormViewModel):
    valuesChanged = Signal()
    fieldErrorsChanged = Signal()
    referenceOptionsChanged = Signal()
    fuelOrdersChanged = Signal()
    fixedTripTypeChanged = Signal(str)
    tripTypeLockedChanged = Signal(bool)
    showTripTypeSelectorChanged = Signal(bool)
    showFuelOrdersChanged = Signal(bool)
    canEditNestedSectionsChanged = Signal(bool)
    includeAgregadosChanged = Signal(bool)
    headerLayoutItemsChanged = Signal()
    fuelOrderFieldsChanged = Signal()
    fieldLocksChanged = Signal()

    _REFERENCE_FIELDS = (
        "cliente_id",
        "origen_id",
        "destino_id",
        "conductor_id",
        "furgon_id",
        "camion_id",
        "thermo_id",
        "_ruta_id",
        "_circuito_id",
        "viaje_ida_id",
    )
    _FILTERED_REFERENCE_FIELDS = frozenset({"conductor_id", "furgon_id", "camion_id", "thermo_id"})
    _ROUTE_SELECTION_FIELDS = frozenset({"cliente_id", "origen_id", "destino_id"})
    _REFERENCE_FIELD_OVERRIDES = {
        "cliente_id": ReferenceFieldDTO(lookup_key="viaje.cliente_id", min_search_chars=0, page_size=20),
        "origen_id": ReferenceFieldDTO(lookup_key="viaje.origen_id", min_search_chars=0, page_size=50),
        "destino_id": ReferenceFieldDTO(lookup_key="viaje.destino_id", min_search_chars=0, page_size=50),
        "viaje_ida_id": ReferenceFieldDTO(lookup_key="viaje.viaje_ida_id", min_search_chars=0, page_size=20),
    }

    def __init__(
        self,
        *,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
    ) -> None:
        super().__init__(title="Nuevo viaje")
        self._workflow_service = workflow_service
        self._reference_lookup_service = reference_lookup_service
        self._viaje_schema = workflow_service.viaje.get_form_schema()
        self._field_index = {field.name: field for field in self._viaje_schema.form_fields}
        self._values: dict[str, Any] = {}
        self._initial_values: dict[str, Any] = {}
        self._field_errors: dict[str, str] = {}
        self._reference_options: dict[str, tuple[ReferenceOptionDTO, ...]] = {}
        self._fuel_orders: list[dict[str, Any]] = []
        self._initial_fuel_orders: list[dict[str, Any]] = []
        self._fixed_trip_type = str(TipoViaje.EXPOR.value)
        self._trip_type_locked = False
        self._show_trip_type_selector = True
        self._show_fuel_orders = True
        self._can_edit_nested_sections = True
        self._include_agregados = False
        self._locked_fields: frozenset[str] = frozenset()
        self._detalle_operacion_id: int | None = None
        self._circuito_id: int | None = None
        self._resolved_route_id: int | None = None
        self._route_resolution_error = ""
        self._reset_defaults()

    @Property("QVariantMap", notify=valuesChanged)
    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @Property("QVariantMap", notify=fieldErrorsChanged)
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)

    @Property("QVariantMap", notify=referenceOptionsChanged)
    def reference_options(self) -> dict[str, list[dict[str, Any]]]:
        return {
            field_name: [{"value": option.value, "label": option.label} for option in options]
            for field_name, options in self._reference_options.items()
        }

    @Property("QVariantList", notify=fuelOrdersChanged)
    def fuel_orders(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._fuel_orders]

    @Property("QVariantList", notify=fuelOrderFieldsChanged)
    def fuel_order_fields(self) -> list[dict[str, Any]]:
        return [
            {"name": "gasolinera", "label": "Gasolinera", "kind": "enum", "span": 1, "full_width": False},
            {"name": "numero_orden", "label": "Numero orden", "kind": "text", "span": 2, "full_width": True},
            {"name": "galones_autorizados", "label": "Galones", "kind": "number", "span": 1, "full_width": False},
            {"name": "tipo", "label": "Tipo", "kind": "enum", "span": 1, "full_width": False},
        ]

    @Property(str, notify=fixedTripTypeChanged)
    def fixed_trip_type(self) -> str:
        return self._fixed_trip_type

    @Property(bool, notify=tripTypeLockedChanged)
    def trip_type_locked(self) -> bool:
        return self._trip_type_locked

    @Property(bool, notify=showTripTypeSelectorChanged)
    def show_trip_type_selector(self) -> bool:
        return self._show_trip_type_selector

    @Property(bool, notify=showFuelOrdersChanged)
    def show_fuel_orders(self) -> bool:
        return self._show_fuel_orders

    @Property(bool, notify=canEditNestedSectionsChanged)
    def can_edit_nested_sections(self) -> bool:
        return self._can_edit_nested_sections

    @Property(bool, notify=includeAgregadosChanged)
    def include_agregados(self) -> bool:
        return self._include_agregados

    @Property("QVariantList", notify=headerLayoutItemsChanged)
    def header_layout_items(self) -> list[dict[str, Any]]:
        return self._serialize_header_layout_items()

    @Property("QVariantList", notify=fieldLocksChanged)
    def locked_fields(self) -> list[str]:
        return sorted(self._locked_fields)

    def load(self, record_id: int | None) -> None:
        self.is_busy = True
        self._set_error_message("")
        try:
            if record_id is None:
                self._set_mode(FormMode.CREATE)
                self._set_mode_from_tipo(TipoViaje.EXPOR.value, locked=False)
                self._set_record_id(None)
                self._set_title("Nuevo viaje")
                self._reset_defaults()
                self._load_initial_options_for_create()
                self.loaded.emit(dict(self._values))
                return

            record = self._workflow_service.viaje.get(int(record_id))
            if record is None:
                raise ValueError(f"No se encontro viaje con id={record_id}")

            payload = self._workflow_service.viaje.get_form_state(int(record_id))
            self._set_mode(FormMode.EDIT)
            self._set_record_id(int(record_id))
            record_trip_type = str(record.get("tipo_viaje") or TipoViaje.EXPOR.value)
            self._set_mode_from_tipo(record_trip_type, locked=True)
            self._set_title(f"Editar viaje #{record_id}")
            self._replace_values(payload["values"])
            self._set_locked_fields(("referencia", "descripcion") if record_trip_type == str(TipoViaje.VACIO.value) else ())
            self._fuel_orders = [dict(item) for item in payload["fuel_orders"]]
            self._initial_fuel_orders = [dict(item) for item in self._fuel_orders]
            self._detalle_operacion_id = self._coerce_positive_int(payload.get("detalle_operacion_id"))
            self._circuito_id = self._coerce_positive_int(payload.get("circuito_id"))
            self._resolved_route_id = self._coerce_positive_int(self._values.get("_ruta_id"))
            self.fuelOrdersChanged.emit()
            self._prime_reference_fields()
            self._refresh_validation()
            self.loaded.emit(dict(self._values))
        except Exception as exc:
            self._set_error_message(str(exc))
            self._set_valid(False)
        finally:
            self.is_busy = False

    def reset(self) -> None:
        self._set_mode(FormMode.CREATE)
        self._set_mode_from_tipo(TipoViaje.EXPOR.value, locked=False)
        self._set_record_id(None)
        self._set_title("Nuevo viaje")
        self._reset_defaults()
        self._load_initial_options_for_create()

    @Slot(str)
    def set_trip_type(self, trip_type: str) -> None:
        if self._trip_type_locked:
            return
        normalized = str(trip_type or "").strip() or str(TipoViaje.EXPOR.value)
        self._set_mode_from_tipo(normalized, locked=False)
        self._set_locked_fields(("referencia", "descripcion", "cliente_id") if normalized == str(TipoViaje.VACIO.value) else ())
        if normalized != str(TipoViaje.EXPOR.value):
            self._values["temperatura"] = ""
            self._values["combustible_base_thermo"] = ""
            self._values["combustible_base_camion"] = ""
        if normalized == str(TipoViaje.EXPOR.value):
            self._values["_circuito_id"] = ""
        self._reset_route_selection()
        self._load_initial_options_for_create()
        self._set_dirty(self._is_form_dirty())
        self._refresh_validation()
        self.valuesChanged.emit()

    def prepare_return_trip(self, circuito_id: int, trip_type: str) -> None:
        normalized_type = str(trip_type or TipoViaje.IMPOR.value)
        if normalized_type not in {TipoViaje.IMPOR.value, TipoViaje.VACIO.value}:
            normalized_type = TipoViaje.IMPOR.value
        self._set_mode(FormMode.CREATE)
        self._set_record_id(None)
        self._set_mode_from_tipo(normalized_type, locked=True)
        self._set_title("Nuevo viaje vacío" if normalized_type == str(TipoViaje.VACIO.value) else "Nuevo viaje de vuelta")
        self._reset_defaults()
        self._values["_circuito_id"] = int(circuito_id)
        self._values["viaje_ida_id"] = self._resolve_viaje_ida_for_circuito(circuito_id) or ""
        self._apply_return_trip_defaults_from_viaje_ida()
        if normalized_type == str(TipoViaje.VACIO.value):
            self._replace_empty_return_route_from_viaje_ida()
            self._set_locked_fields(
                (
                    "cliente_id",
                    "referencia",
                    "descripcion",
                    "origen_id",
                    "destino_id",
                    "conductor_id",
                    "_circuito_id",
                    "viaje_ida_id",
                )
            )
        else:
            self._set_locked_fields(("conductor_id", "_circuito_id", "viaje_ida_id"))
        if normalized_type != str(TipoViaje.EXPOR.value):
            self._values["temperatura"] = ""
            self._values["combustible_base_thermo"] = ""
            self._values["combustible_base_camion"] = ""
        self._load_initial_options_for_create()
        self._prime_reference_field("_circuito_id")
        self._prime_reference_field("viaje_ida_id")
        self._refresh_validation()
        self.valuesChanged.emit()

    @Slot(str, "QVariant")
    def set_field_value(self, field_name: str, value: Any) -> None:
        if field_name not in self._values:
            return
        if self.is_field_locked(field_name):
            return
        self._values[field_name] = value
        self._handle_dependent_field_change(field_name)
        self._clear_field_error(field_name)
        self._set_error_message("")
        self._set_dirty(self._is_form_dirty())
        self._refresh_validation()
        self.valuesChanged.emit()

    @Slot(str, result=bool)
    def is_field_locked(self, field_name: str) -> bool:
        return str(field_name or "") in self._locked_fields

    @Slot(str)
    def prime_reference_field(self, field_name: str) -> None:
        self._prime_reference_field(field_name)

    @Slot(str, str)
    def search_reference_options(self, field_name: str, term: str) -> None:
        reference = self._reference_for_field(field_name)
        if reference is None or self._reference_lookup_service is None:
            return
        normalized_term = str(term or "").strip()
        if len(normalized_term) < int(reference.min_search_chars):
            return
        self._load_reference_options(field_name, normalized_term)

    @Slot(bool)
    def set_include_agregados(self, include_agregados: bool) -> None:
        normalized = bool(include_agregados)
        if self._include_agregados == normalized:
            return
        self._include_agregados = normalized
        self._refresh_filtered_reference_options()
        self.includeAgregadosChanged.emit(normalized)

    @Slot()
    def add_fuel_order(self) -> None:
        self._fuel_orders.append(self._empty_fuel_order())
        self._set_dirty(self._is_form_dirty())
        self.fuelOrdersChanged.emit()

    @Slot(int)
    def remove_fuel_order(self, index: int) -> None:
        if 0 <= index < len(self._fuel_orders):
            self._fuel_orders.pop(index)
            self._set_dirty(self._is_form_dirty())
            self._refresh_validation()
            self.fuelOrdersChanged.emit()

    @Slot(int, str, "QVariant")
    def set_fuel_order_field(self, index: int, field_name: str, value: Any) -> None:
        if 0 <= index < len(self._fuel_orders):
            if self._fuel_orders[index].get(field_name) == value:
                return
            self._fuel_orders[index][field_name] = value
            self._set_dirty(self._is_form_dirty())
            self._refresh_validation()

    @Slot(int, str, result=str)
    def fuel_order_error(self, index: int, field_name: str) -> str:
        return self._field_errors.get(f"fuel_order_{index}_{field_name}", "")

    @Slot(str, result=str)
    def field_error(self, field_name: str) -> str:
        return self._field_errors.get(field_name, "")

    def _serialize_header_layout_items(self) -> list[dict[str, Any]]:
        layout_items: list[dict[str, Any]] = []
        pending_row: list[dict[str, Any]] = []

        def flush_row() -> None:
            if not pending_row:
                return
            layout_items.append({"type": "row", "fields": list(pending_row)})
            pending_row.clear()

        for item in VIAJE_HEADER_LAYOUT.items:
            if isinstance(item, FormLayoutSectionItem):
                flush_row()
                layout_items.append({"type": "section", "title": item.title})
                continue

            serialized_field = self._serialize_header_field(item.field_name)
            if serialized_field is None:
                continue

            entry = {
                **serialized_field,
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

    def _serialize_header_field(self, field_name: str) -> dict[str, Any] | None:
        field_schema = self._field_index.get(field_name)
        if field_schema is None:
            field = self._manual_header_field(field_name)
            if field is None:
                return None
        else:
            field = GenericFormFieldDefinition.from_schema(field_schema)
        return {
            "name": field.name,
            "label": self._header_field_label(field.name, field.label or field.name.replace("_", " ").title()),
            "field_type": field.field_type,
            "kind": field.kind or field.field_type,
            "required": field.required,
            "editable": field.editable,
            "nullable": field.nullable,
            "precision": field.precision,
            "display_format": field.display_format or "",
            "display_field_key": field.display_field_key or "",
            "options": [
                {"value": option.value, "label": option.display_label()}
                for option in field.options
            ],
        }

    @staticmethod
    def _header_field_label(field_name: str, default_label: str) -> str:
        overrides = {
            "_circuito_id": "Circuito de retorno",
            "viaje_ida_id": "Viaje de ida",
            "viaticos_monto": "Viáticos",
            "viaticos_moneda": "Moneda viáticos",
            "fecha_posicionamiento": "Fecha de posicionamiento",
        }
        return overrides.get(field_name, default_label)

    def _manual_header_field(self, field_name: str) -> GenericFormFieldDefinition | None:
        manual_fields: dict[str, GenericFormFieldDefinition] = {
            "origen_id": GenericFormFieldDefinition(
                name="origen_id",
                label="Origen",
                kind=FieldKind.REFERENCE.value,
                required=True,
                nullable=False,
                reference=self._reference_for_field("origen_id"),
            ),
            "destino_id": GenericFormFieldDefinition(
                name="destino_id",
                label="Destino",
                kind=FieldKind.REFERENCE.value,
                required=True,
                nullable=False,
                reference=self._reference_for_field("destino_id"),
            ),
            "viaje_ida_id": GenericFormFieldDefinition(
                name="viaje_ida_id",
                label="Viaje de ida",
                kind=FieldKind.REFERENCE.value,
                required=True,
                nullable=False,
                reference=self._reference_for_field("viaje_ida_id"),
            ),
        }
        return manual_fields.get(field_name)

    def submit(self) -> Mapping[str, Any] | None:
        self._set_error_message("")
        self._refresh_validation()
        if not self.is_valid:
            self._set_error_message("Formulario invalido")
            return None

        self.is_busy = True
        try:
            payload = self._build_payload()
            if self._mode.value == "create":
                result = self._workflow_service.viaje.create(payload)
                result_dict = dict(result or {})
                new_record_id = result_dict.get("id")
                self._set_record_id(int(new_record_id) if new_record_id is not None else None)
                self._set_mode(FormMode.EDIT)
                self._set_mode_from_tipo(str(result_dict.get("tipo_viaje") or self._fixed_trip_type), locked=True)
                self.load(self._record_id)
                self.saved.emit(result_dict)
                return result_dict

            if self._record_id is None:
                raise ValueError("record_id es requerido para editar viaje")

            result = self._workflow_service.viaje.update(self._record_id, {"viaje": payload["viaje"]})
            result_dict = dict(result or {})
            if payload.get("detalle_operacion") and self._detalle_operacion_id is not None:
                self._workflow_service.detalle_operacion.actualizar_secciones(
                    self._detalle_operacion_id,
                    payload["detalle_operacion"],
                )
            if payload.get("circuito") and self._circuito_id is not None:
                self._workflow_service.circuito.actualizar_secciones(
                    self._circuito_id,
                    payload["circuito"],
                )
            self.load(self._record_id)
            self.saved.emit(result_dict)
            return result_dict
        except Exception as exc:
            self._set_error_message(str(exc))
            return None
        finally:
            self.is_busy = False

    def _reset_defaults(self) -> None:
        self._values = {
            "referencia": "",
            "cliente_id": "",
            "origen_id": "",
            "destino_id": "",
            "conductor_id": "",
            "furgon_id": "",
            "camion_id": "",
            "thermo_id": "",
            "_ruta_id": "",
            "_circuito_id": "",
            "viaje_ida_id": "",
            "fecha_posicionamiento": "",
            "descripcion": "",
            "viaticos_monto": "",
            "viaticos_moneda": str(Moneda.USD.value),
            "temperatura": "",
            "combustible_base_thermo": "40.0",
            "combustible_base_camion": "60.0",
        }
        self._fuel_orders = [self._empty_fuel_order()]
        self._initial_values = dict(self._values)
        self._initial_fuel_orders = [dict(item) for item in self._fuel_orders]
        self._field_errors = {}
        self._reference_options = {}
        self._detalle_operacion_id = None
        self._circuito_id = None
        self._resolved_route_id = None
        self._route_resolution_error = ""
        self._include_agregados = False
        self._set_locked_fields(())
        self._set_dirty(False)
        self._set_valid(True)
        self._set_error_message("")
        self.valuesChanged.emit()
        self.referenceOptionsChanged.emit()
        self.fuelOrdersChanged.emit()
        self.fieldErrorsChanged.emit()
        self.includeAgregadosChanged.emit(False)

    def _values_from_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        values = dict(self._values)
        values.update(
            {
                "referencia": self._format_for_ui("referencia", record.get("referencia")),
                "cliente_id": self._format_for_ui("cliente_id", record.get("cliente_id")),
                "origen_id": record.get("origen_id") or "",
                "destino_id": record.get("destino_id") or "",
                "conductor_id": self._format_for_ui("conductor_id", record.get("conductor_id")),
                "furgon_id": self._format_for_ui("furgon_id", record.get("furgon_id")),
                "camion_id": self._format_for_ui("camion_id", record.get("camion_id")),
                "thermo_id": self._format_for_ui("thermo_id", record.get("thermo_id")),
                "_ruta_id": self._format_for_ui("_ruta_id", record.get("_ruta_id")),
                "_circuito_id": self._format_for_ui("_circuito_id", record.get("_circuito_id")),
                "viaje_ida_id": record.get("viaje_ida_id") or "",
                "fecha_posicionamiento": self._format_for_ui("fecha_posicionamiento", record.get("fecha_posicionamiento")),
                "descripcion": self._format_for_ui("descripcion", record.get("descripcion")),
                "viaticos_monto": self._format_for_ui("viaticos_monto", record.get("viaticos_monto")),
                "viaticos_moneda": self._format_for_ui("viaticos_moneda", record.get("viaticos_moneda")),
                "temperatura": self._format_for_ui("temperatura", record.get("temperatura")),
            }
        )
        return values

    def _replace_values(self, values: Mapping[str, Any]) -> None:
        self._values = dict(values)
        self._initial_values = dict(values)
        self.valuesChanged.emit()

    def _prime_reference_fields(self) -> None:
        for field_name in self._REFERENCE_FIELDS:
            self._prime_reference_field(field_name)

    def _prime_reference_field(self, field_name: str) -> None:
        reference = self._reference_for_field(field_name)
        if reference is None or self._reference_lookup_service is None:
            return
        value = self._values.get(field_name)
        if value in (None, ""):
            options = self._load_initial_reference_options(field_name)
            if self._reference_options.get(field_name) != options:
                self._reference_options[field_name] = options
                self.referenceOptionsChanged.emit()
            return
        key = int(value) if not isinstance(value, int) and str(value).isdigit() else value
        resolved = self._reference_lookup_service.resolve_ids(reference.lookup_key, [value])
        option = resolved.get(key)
        if option is None:
            self._reference_options[field_name] = (ReferenceOptionDTO(value=key, label=str(key)),)
            self.referenceOptionsChanged.emit()
            return
        self._reference_options[field_name] = (option,)
        self.referenceOptionsChanged.emit()

    def _load_initial_reference_options(self, field_name: str) -> tuple[ReferenceOptionDTO, ...]:
        reference = self._reference_for_field(field_name)
        if reference is None or self._reference_lookup_service is None:
            return ()
        return tuple(
            self._reference_lookup_service.search(
                reference.lookup_key,
                "",
                reference.page_size,
                context=self._lookup_context_for_field(field_name),
            )
        )

    def _lookup_context_for_field(self, field_name: str) -> dict[str, Any] | None:
        if field_name == "cliente_id":
            return {"trip_type": self._fixed_trip_type}
        if field_name == "origen_id":
            return {
                "cliente_id": self._coerce_positive_int(self._values.get("cliente_id")),
                "destino_id": self._coerce_positive_int(self._values.get("destino_id")),
            }
        if field_name == "destino_id":
            return {
                "cliente_id": self._coerce_positive_int(self._values.get("cliente_id")),
                "origen_id": self._coerce_positive_int(self._values.get("origen_id")),
            }
        if field_name == "conductor_id":
            return {
                "trip_type": self._fixed_trip_type,
                "include_agregados": self._include_agregados,
            }
        if field_name == "viaje_ida_id":
            return {
                "conductor_id": self._coerce_positive_int(self._values.get("conductor_id")),
                "camion_id": self._coerce_positive_int(self._values.get("camion_id")),
            }
        if field_name not in self._FILTERED_REFERENCE_FIELDS:
            return None
        return {"include_agregados": self._include_agregados}

    def _refresh_filtered_reference_options(self) -> None:
        emitted = False
        cleared_any = False
        for field_name in self._FILTERED_REFERENCE_FIELDS:
            if field_name in self._reference_options:
                self._reference_options[field_name] = ()
                cleared_any = True
            value = self._values.get(field_name)
            if value not in (None, ""):
                self._prime_reference_field(field_name)
                emitted = True
        if cleared_any and not emitted:
            self.referenceOptionsChanged.emit()

    def _set_mode_from_tipo(self, trip_type: str, *, locked: bool) -> None:
        normalized = str(trip_type or TipoViaje.EXPOR.value)
        if self._fixed_trip_type != normalized:
            self._fixed_trip_type = normalized
            self.fixedTripTypeChanged.emit(normalized)
        if self._trip_type_locked != bool(locked):
            self._trip_type_locked = bool(locked)
            self.tripTypeLockedChanged.emit(bool(locked))
        next_show_trip_type_selector = normalized != str(TipoViaje.VACIO.value)
        if self._show_trip_type_selector != next_show_trip_type_selector:
            self._show_trip_type_selector = next_show_trip_type_selector
            self.showTripTypeSelectorChanged.emit(next_show_trip_type_selector)
        next_show_fuel_orders = normalized != str(TipoViaje.VACIO.value)
        if self._show_fuel_orders != next_show_fuel_orders:
            self._show_fuel_orders = next_show_fuel_orders
            self.showFuelOrdersChanged.emit(next_show_fuel_orders)
        can_edit_nested = True
        if self._can_edit_nested_sections != can_edit_nested:
            self._can_edit_nested_sections = can_edit_nested
            self.canEditNestedSectionsChanged.emit(can_edit_nested)

    def _set_locked_fields(self, field_names: tuple[str, ...]) -> None:
        normalized = frozenset(str(field_name) for field_name in field_names if str(field_name or "").strip())
        if self._locked_fields != normalized:
            self._locked_fields = normalized
            self.fieldLocksChanged.emit()

    def _build_payload(self) -> dict[str, Any]:
        trip_type = self._coerce_trip_type(self._fixed_trip_type)
        payload: dict[str, Any] = {"viaje": self._build_viaje_payload(trip_type)}
        detail_sections = self._build_detalle_sections(trip_type)
        if detail_sections:
            payload["detalle_operacion"] = detail_sections
        if trip_type == TipoViaje.EXPOR:
            payload["circuito"] = self._build_circuito_sections()
        return payload

    def _build_viaje_payload(self, trip_type: TipoViaje) -> dict[str, Any]:
        fecha_posicionamiento = datetime.fromisoformat(
            str(
                normalize_field_value(
                    kind=FieldKind.DATETIME,
                    value=self._values.get("fecha_posicionamiento"),
                    required=True,
                    nullable=False,
                )
            )
        )
        viaje_payload = {
            "referencia": normalize_field_value(
                kind=FieldKind.TEXT,
                value=self._values.get("referencia"),
                required=False,
                nullable=True,
            ),
            "cliente_id": None if trip_type == TipoViaje.VACIO else self._normalize_required_reference("cliente_id"),
            "conductor_id": self._normalize_required_reference("conductor_id"),
            "furgon_id": self._normalize_required_reference("furgon_id"),
            "camion_id": self._normalize_required_reference("camion_id"),
            "thermo_id": self._normalize_required_reference("thermo_id"),
            "_ruta_id": self._resolve_route_id(required=True),
            "fecha_posicionamiento": fecha_posicionamiento,
            "descripcion": normalize_field_value(
                kind=FieldKind.TEXT,
                value=self._values.get("descripcion"),
                required=False,
                nullable=True,
            ),
            "viaticos_monto": normalize_field_value(
                kind=FieldKind.MONEY,
                value=self._values.get("viaticos_monto"),
                required=True,
                nullable=False,
            ),
            "viaticos_moneda": normalize_field_value(
                kind=FieldKind.ENUM,
                value=self._values.get("viaticos_moneda"),
                required=True,
                nullable=False,
                options=_enum_options(Moneda),
            ),
            "tipo_viaje": trip_type.value,
        }
        if trip_type == TipoViaje.EXPOR:
            viaje_payload["temperatura"] = normalize_field_value(
                kind=FieldKind.NUMBER,
                value=self._values.get("temperatura"),
                required=True,
                nullable=False,
            )
        if trip_type in {TipoViaje.IMPOR, TipoViaje.VACIO}:
            viaje_payload["_circuito_id"] = self._normalize_required_reference("_circuito_id")
            viaje_ida_id = self._coerce_positive_int(self._values.get("viaje_ida_id"))
            if viaje_ida_id is not None:
                viaje_payload["viaje_ida_id"] = int(viaje_ida_id)
        elif self._circuito_id is not None and self._mode.value == "edit":
            viaje_payload["_circuito_id"] = int(self._circuito_id)
        return viaje_payload

    def _build_detalle_sections(self, trip_type: TipoViaje) -> dict[str, Any]:
        sections: dict[str, Any] = {}
        if trip_type != TipoViaje.VACIO:
            sections["ordenes_combustible"] = self._normalize_fuel_orders()
        if trip_type == TipoViaje.EXPOR:
            sections["gasto_real_thermo"] = {
                "combustible_base_thermo": normalize_field_value(
                    kind=FieldKind.NUMBER,
                    value=self._values.get("combustible_base_thermo"),
                    required=True,
                    nullable=False,
                )
            }
        return sections

    def _build_circuito_sections(self) -> dict[str, Any]:
        fecha_inicio = datetime.fromisoformat(
            str(
                normalize_field_value(
                    kind=FieldKind.DATETIME,
                    value=self._values.get("fecha_posicionamiento"),
                    required=True,
                    nullable=False,
                )
            )
        )
        return {
            "fecha_inicio": fecha_inicio,
            "gasto_real_camion": {
                "combustible_base_camion": normalize_field_value(
                    kind=FieldKind.NUMBER,
                    value=self._values.get("combustible_base_camion"),
                    required=True,
                    nullable=False,
                )
            },
        }

    def _normalize_required_reference(self, field_name: str) -> int:
        
        result= normalize_field_value(
                kind=FieldKind.REFERENCE,
                value=self._values.get(field_name),
                required=True, nullable=False,)
        assert result is not None
        return int(result)

    def _normalize_fuel_orders(self) -> list[dict[str, Any]]:
        normalized_orders: list[dict[str, Any]] = []
        for fuel_order in self._fuel_orders:
            if self._is_empty_fuel_order(fuel_order):
                continue
            item = {
                "gasolinera": normalize_field_value(
                    kind=FieldKind.ENUM,
                    value=fuel_order.get("gasolinera"),
                    required=True,
                    nullable=False,
                    options=_enum_options(Gasolinera),
                ),
                "numero_orden": normalize_field_value(
                    kind=FieldKind.TEXT,
                    value=fuel_order.get("numero_orden"),
                    required=True,
                    nullable=False,
                ),
                "galones_autorizados": normalize_field_value(
                    kind=FieldKind.NUMBER,
                    value=fuel_order.get("galones_autorizados"),
                    required=True,
                    nullable=False,
                ),
                "tipo": normalize_field_value(
                    kind=FieldKind.ENUM,
                    value=fuel_order.get("tipo"),
                    required=True,
                    nullable=False,
                    options=_enum_options(TipoOrdenCombustible),
                ),
            }
            if fuel_order.get("id") not in (None, ""):
                item["id"] = fuel_order.get("id")
            normalized_orders.append(item)
        if not normalized_orders:
            raise ValueError("Debes registrar al menos una orden de combustible.")
        return normalized_orders

    def _refresh_validation(self) -> None:
        errors: dict[str, str] = {}
        trip_type = self._coerce_trip_type(self._fixed_trip_type)
        required_reference_fields = ["origen_id", "destino_id", "conductor_id", "furgon_id", "camion_id", "thermo_id"]
        if trip_type != TipoViaje.VACIO:
            required_reference_fields.insert(0, "cliente_id")
        for field_name in required_reference_fields:
            error = validate_field_value(
                kind=FieldKind.REFERENCE,
                value=self._values.get(field_name),
                required=True,
                nullable=False,
            )
            if error:
                errors[field_name] = error
        if trip_type == TipoViaje.VACIO and self._route_resolution_error:
            self._resolved_route_id = None
            self._values["_ruta_id"] = ""
            errors["destino_id"] = self._route_resolution_error
        elif not any(errors.get(field_name) for field_name in self._ROUTE_SELECTION_FIELDS):
            try:
                self._resolved_route_id = self._resolve_route_id(required=True)
                self._values["_ruta_id"] = self._resolved_route_id
            except ValueError as exc:
                self._resolved_route_id = None
                self._values["_ruta_id"] = ""
                errors["destino_id"] = str(exc)
        else:
            self._resolved_route_id = None
            self._values["_ruta_id"] = ""
        for field_name, kind, required, options in (
            ("referencia", FieldKind.TEXT, False, ()),
            ("fecha_posicionamiento", FieldKind.DATETIME, True, ()),
            ("descripcion", FieldKind.TEXT, False, ()),
            ("viaticos_monto", FieldKind.MONEY, True, ()),
            ("viaticos_moneda", FieldKind.ENUM, True, _enum_options(Moneda)),
        ):
            error = validate_field_value(
                kind=kind,
                value=self._values.get(field_name),
                required=required,
                nullable=not required,
                options=options,
            )
            if error:
                errors[field_name] = error
        if trip_type == TipoViaje.EXPOR:
            for field_name in ("temperatura", "combustible_base_thermo", "combustible_base_camion"):
                error = validate_field_value(
                    kind=FieldKind.NUMBER,
                    value=self._values.get(field_name),
                    required=True,
                    nullable=False,
                )
                if error:
                    errors[field_name] = error
        if trip_type in {TipoViaje.IMPOR, TipoViaje.VACIO}:
            viaje_ida_error = validate_field_value(
                kind=FieldKind.REFERENCE,
                value=self._values.get("viaje_ida_id"),
                required=self._values.get("_circuito_id") in (None, ""),
                nullable=self._values.get("_circuito_id") not in (None, ""),
            )
            circuito_error = validate_field_value(
                kind=FieldKind.REFERENCE,
                value=self._values.get("_circuito_id"),
                required=True,
                nullable=False,
            )
            if viaje_ida_error:
                errors["viaje_ida_id"] = viaje_ida_error
            if circuito_error:
                errors["_circuito_id"] = circuito_error
            else:
                circuito_id = self._coerce_positive_int(self._values.get("_circuito_id"))
                if circuito_id is not None:
                    if trip_type == TipoViaje.IMPOR:
                        errors.update(
                            self._workflow_service.viaje.validate_import_constraints(
                                circuito_id,
                                self._values,
                                exclude_viaje_id=self._record_id,
                            )
                        )
        if trip_type != TipoViaje.VACIO:
            errors.update(self._validate_fuel_orders())
        self._field_errors = errors
        self._set_valid(len(errors) == 0)
        self.fieldErrorsChanged.emit()

    def _validate_fuel_orders(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        has_valid = False
        for index, fuel_order in enumerate(self._fuel_orders):
            if self._is_empty_fuel_order(fuel_order):
                continue
            has_valid = True
            for field_name, kind, options in (
                ("gasolinera", FieldKind.ENUM, _enum_options(Gasolinera)),
                ("numero_orden", FieldKind.TEXT, ()),
                ("galones_autorizados", FieldKind.NUMBER, ()),
                ("tipo", FieldKind.ENUM, _enum_options(TipoOrdenCombustible)),
            ):
                error = validate_field_value(
                    kind=kind,
                    value=fuel_order.get(field_name),
                    required=True,
                    nullable=False,
                    options=options,
                )
                if error:
                    errors[f"fuel_order_{index}_{field_name}"] = error
        if not has_valid:
            errors["ordenes_combustible"] = "Debes registrar al menos una orden de combustible."
        return errors

    def _clear_field_error(self, field_name: str) -> None:
        if field_name in self._field_errors:
            self._field_errors.pop(field_name, None)
            self.fieldErrorsChanged.emit()

    def _is_form_dirty(self) -> bool:
        return self._values != self._initial_values or self._fuel_orders != self._initial_fuel_orders

    def _empty_fuel_order(self) -> dict[str, Any]:
        return {
            "id": None,
            "gasolinera": "",
            "numero_orden": "",
            "galones_autorizados": "",
            "tipo": str(TipoOrdenCombustible.CAMION.value),
        }

    def _format_fuel_order(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": record.get("id"),
            "gasolinera": self._format_enum_ui(record.get("gasolinera")),
            "numero_orden": record.get("numero_orden") or "",
            "galones_autorizados": self._format_decimal_ui(record.get("galones_autorizados")),
            "tipo": self._format_enum_ui(record.get("tipo")),
        }

    def _is_empty_fuel_order(self, fuel_order: Mapping[str, Any]) -> bool:
        return all(fuel_order.get(field_name) in (None, "") for field_name in ("gasolinera", "numero_orden", "galones_autorizados"))

    def _format_for_ui(self, field_name: str, value: Any) -> Any:
        field = self._field_index.get(field_name)
        if field is None:
            return self._format_decimal_ui(value)
        if field.kind == FieldKind.ENUM:
            return self._format_enum_ui(value)
        return format_field_value_for_ui(kind=field.kind, value=value)

    def _reference_for_field(self, field_name: str) -> ReferenceFieldDTO | None:
        if field_name in self._REFERENCE_FIELD_OVERRIDES:
            return self._REFERENCE_FIELD_OVERRIDES[field_name]
        field = self._field_index.get(field_name)
        return field.reference if field is not None else None

    def _load_reference_options(self, field_name: str, term: str) -> None:
        reference = self._reference_for_field(field_name)
        if reference is None or self._reference_lookup_service is None:
            return
        options = list(
            self._reference_lookup_service.search(
                reference.lookup_key,
                str(term or ""),
                reference.page_size,
                context=self._lookup_context_for_field(field_name),
            )
        )
        current_value = self._values.get(field_name)
        if current_value not in (None, ""):
            normalized_current = int(current_value) if str(current_value).isdigit() else current_value
            if all(option.value != normalized_current for option in options):
                resolved = self._reference_lookup_service.resolve_ids(reference.lookup_key, [current_value])
                current_option = resolved.get(normalized_current)
                if current_option is None:
                    current_option = ReferenceOptionDTO(value=normalized_current, label=str(normalized_current))
                options = [current_option, *options]
        self._reference_options[field_name] = tuple(options)
        self.referenceOptionsChanged.emit()

    def _load_initial_options_for_create(self) -> None:
        self._load_reference_options("cliente_id", "")
        for field_name in ("conductor_id", "furgon_id", "camion_id", "thermo_id"):
            self._load_reference_options(field_name, "")
        if self._fixed_trip_type in {str(TipoViaje.IMPOR.value), str(TipoViaje.VACIO.value)}:
            self._load_reference_options("viaje_ida_id", "")

    def _handle_dependent_field_change(self, field_name: str) -> None:
        if field_name == "cliente_id":
            self._values["origen_id"] = ""
            self._values["destino_id"] = ""
            self._reference_options["origen_id"] = ()
            self._reference_options["destino_id"] = ()
            self._clear_resolved_route()
            if self._coerce_positive_int(self._values.get("cliente_id")) is not None:
                self._load_reference_options("origen_id", "")
                self._load_reference_options("destino_id", "")
            else:
                self.referenceOptionsChanged.emit()
            return
        if field_name == "conductor_id":
            self._replace_equipment_from_conductor()
            self._refresh_viaje_ida_after_equipment_change()
            return
        if field_name == "camion_id":
            self._refresh_viaje_ida_after_equipment_change()
            return
        if field_name == "viaje_ida_id":
            self._replace_circuito_from_viaje_ida()
            if self._fixed_trip_type == str(TipoViaje.VACIO.value):
                self._apply_return_trip_defaults_from_viaje_ida()
            if self._fixed_trip_type == str(TipoViaje.VACIO.value):
                self._replace_empty_return_route_from_viaje_ida()
            return
        if field_name in {"origen_id", "destino_id"}:
            self._clear_resolved_route()
            self._refresh_route_reference_options(field_name)

    def _refresh_route_reference_options(self, changed_field_name: str) -> None:
        counterpart = "destino_id" if changed_field_name == "origen_id" else "origen_id"
        if self._coerce_positive_int(self._values.get("cliente_id")) is None:
            self._reference_options[counterpart] = ()
            self.referenceOptionsChanged.emit()
            return
        self._load_reference_options(counterpart, "")

    def _replace_equipment_from_conductor(self) -> None:
        conductor_id = self._coerce_positive_int(self._values.get("conductor_id"))
        defaults: dict[str, int | None] = {
            "camion_id": None,
            "furgon_id": None,
            "thermo_id": None,
        }
        if conductor_id is not None:
            try:
                resolved = self._workflow_service.viaje.resolve_conductor_equipment_defaults(conductor_id)
            except Exception:
                resolved = {}
            defaults.update({key: self._coerce_positive_int(resolved.get(key)) for key in defaults})

        for field_name in ("furgon_id", "camion_id", "thermo_id"):
            value = defaults.get(field_name)
            self._values[field_name] = value if value is not None else ""
            self._clear_field_error(field_name)
            self._load_reference_options(field_name, "")

    def _apply_return_trip_defaults_from_viaje_ida(self) -> None:
        viaje_ida_id = self._coerce_positive_int(self._values.get("viaje_ida_id"))
        if viaje_ida_id is None:
            return
        try:
            viaje_ida = self._workflow_service.viaje.get(viaje_ida_id)
        except Exception:
            return
        if viaje_ida is None:
            return
        conductor_id = self._coerce_positive_int(viaje_ida.get("conductor_id"))
        if conductor_id is None:
            return
        self._values["conductor_id"] = conductor_id
        if self._fixed_trip_type == str(TipoViaje.VACIO.value):
            for field_name in ("furgon_id", "camion_id", "thermo_id"):
                equipment_id = self._coerce_positive_int(viaje_ida.get(field_name))
                self._values[field_name] = equipment_id if equipment_id is not None else ""
                self._clear_field_error(field_name)
                self._load_reference_options(field_name, "")
        else:
            self._replace_equipment_from_conductor()
        self._prime_reference_field("conductor_id")

    def _refresh_viaje_ida_after_equipment_change(self) -> None:
        if self._fixed_trip_type not in {str(TipoViaje.IMPOR.value), str(TipoViaje.VACIO.value)}:
            return
        if self.is_field_locked("viaje_ida_id") or self.is_field_locked("_circuito_id"):
            return
        self._values["viaje_ida_id"] = ""
        self._values["_circuito_id"] = ""
        self._load_reference_options("viaje_ida_id", "")

    def _replace_circuito_from_viaje_ida(self) -> None:
        viaje_ida_id = self._coerce_positive_int(self._values.get("viaje_ida_id"))
        self._values["_circuito_id"] = ""
        if viaje_ida_id is None:
            self._clear_field_error("_circuito_id")
            return
        try:
            circuito_id = self._workflow_service.viaje.resolve_viaje_ida_circuito(viaje_ida_id)
        except Exception as exc:
            self._field_errors["viaje_ida_id"] = str(exc)
            self.fieldErrorsChanged.emit()
            return
        if circuito_id is not None:
            self._values["_circuito_id"] = int(circuito_id)
            self._clear_field_error("_circuito_id")

    def _replace_empty_return_route_from_viaje_ida(self) -> None:
        viaje_ida_id = self._coerce_positive_int(self._values.get("viaje_ida_id"))
        self._values["origen_id"] = ""
        self._values["destino_id"] = ""
        self._clear_resolved_route()
        if viaje_ida_id is None:
            return
        try:
            resolved = self._workflow_service.viaje.resolve_empty_return_route(viaje_ida_id)
        except Exception as exc:
            self._route_resolution_error = str(exc)
            return
        self._route_resolution_error = ""
        self._resolved_route_id = int(resolved["_ruta_id"])
        self._values["_ruta_id"] = int(resolved["_ruta_id"])
        self._values["origen_id"] = int(resolved["origen_id"])
        self._values["destino_id"] = int(resolved["destino_id"])
        self._clear_field_error("destino_id")

    def _resolve_viaje_ida_for_circuito(self, circuito_id: int) -> int | None:
        try:
            return self._workflow_service.viaje.resolve_circuito_viaje_ida(int(circuito_id))
        except Exception:
            return None

    def _clear_resolved_route(self) -> None:
        self._resolved_route_id = None
        self._values["_ruta_id"] = ""
        self._route_resolution_error = ""

    def _reset_route_selection(self) -> None:
        self._values["cliente_id"] = ""
        self._values["origen_id"] = ""
        self._values["destino_id"] = ""
        self._reference_options["cliente_id"] = ()
        self._reference_options["origen_id"] = ()
        self._reference_options["destino_id"] = ()
        self._clear_resolved_route()
        self.referenceOptionsChanged.emit()

    def _resolve_route_id(self, *, required: bool) -> int:
        if self._resolved_route_id is not None:
            return int(self._resolved_route_id)
        if self._fixed_trip_type == str(TipoViaje.VACIO.value):
            if required:
                raise ValueError("Debes seleccionar un viaje de ida con una ruta de retorno valida.")
            return 0
        cliente_id = self._coerce_positive_int(self._values.get("cliente_id"))
        origen_id = self._coerce_positive_int(self._values.get("origen_id"))
        destino_id = self._coerce_positive_int(self._values.get("destino_id"))
        if cliente_id is None or origen_id is None or destino_id is None:
            if required:
                raise ValueError("Debes seleccionar cliente, origen y destino.")
            return 0
        resolved = self._workflow_service.viaje.resolve_route(cliente_id, origen_id, destino_id)
        self._resolved_route_id = int(resolved)
        return int(resolved)

    @staticmethod
    def _format_enum_ui(value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _format_decimal_ui(value: Any) -> str:
        return "" if value in (None, "") else str(value)

    @staticmethod
    def _coerce_trip_type(value: Any) -> TipoViaje:
        if isinstance(value, TipoViaje):
            return value
        return TipoViaje(str(value))

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            normalized = int(value)
            return normalized if normalized > 0 else None
        return None
