"""Specialized catalog-form view model for Factura."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloCatalogService, ModeloWorkflowService
from ....domain.modelo.field_validation import format_field_value_for_ui
from ....infrastructure.persistence.modelo.workflow_orm import (
    Moneda,
    TipoDetalle,
    TipoGasto,
    TipoImpuesto,
    q2,
)
from ...catalog.definitions import FormFieldOption, GenericFormFieldDefinition
from ...catalog.form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from ...catalog.table_preferences import CatalogTablePreferencesStore, InMemoryCatalogTablePreferencesStore
from ...catalog.types import FormMode
from ...qt import Property, QmlNamedElement, QmlUncreatable, QObject, Signal, Slot
from ..common import (
    SelectableCandidateTableModel,
    WorkflowFormViewModelBase,
    _as_decimal,
    _money_display_text,
    _money_text,
    _normalize_datetime_input,
    _normalize_int_input,
    _normalize_money_input,
    _normalize_rate_input,
    _normalize_reference_id,
    _rate_text,
)

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

_VIAJE_SELECTOR_TABLE_KEY = "factura_viaje_selector"

FACTURA_HEADER_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutSectionItem(title="Cabecera"),
        FormLayoutFieldItem(field_name="numero_factura"),
        FormLayoutFieldItem(field_name="fecha_emision"),
        FormLayoutFieldItem(field_name="cliente_id", full_width=True),
        FormLayoutFieldItem(field_name="dias_credito"),
        FormLayoutFieldItem(field_name="moneda"),
        FormLayoutFieldItem(field_name="tasa_cambio", full_width=True),
    )
)

FACTURA_HEADER_FIELDS: dict[str, GenericFormFieldDefinition] = {
    "numero_factura": GenericFormFieldDefinition(
        name="numero_factura",
        label="Numero factura",
        kind="text",
        required=True,
        nullable=False,
    ),
    "fecha_emision": GenericFormFieldDefinition(
        name="fecha_emision",
        label="Fecha emision",
        kind="datetime",
        required=True,
        nullable=False,
    ),
    "cliente_id": GenericFormFieldDefinition(
        name="cliente_id",
        label="Cliente",
        kind="reference",
        required=True,
        nullable=False,
    ),
    "dias_credito": GenericFormFieldDefinition(
        name="dias_credito",
        label="Dias credito",
        kind="integer",
        required=True,
        nullable=False,
    ),
    "moneda": GenericFormFieldDefinition(
        name="moneda",
        label="Moneda",
        kind="enum",
        required=True,
        nullable=False,
        options=(
            FormFieldOption(value=Moneda.NIO.value, label=Moneda.NIO.value),
            FormFieldOption(value=Moneda.USD.value, label=Moneda.USD.value),
        ),
    ),
    "tasa_cambio": GenericFormFieldDefinition(
        name="tasa_cambio",
        label="Tasa cambio",
        kind="percent",
        required=True,
        nullable=False,
    ),
}


def _apply_column_width_overrides(
    columns: list[dict[str, Any]],
    overrides: Mapping[str, int],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for column in columns:
        next_column = dict(column)
        key = str(next_column.get("key") or "")
        if key in overrides:
            min_width = int(next_column.get("minWidth") or 40)
            next_column["width"] = max(int(overrides[key]), min_width)
        resolved.append(next_column)
    return resolved


@QmlNamedElement("FacturaFormViewModel")
@QmlUncreatable("FacturaFormViewModel instances are created in Python and injected into QML.")
class FacturaFormViewModel(WorkflowFormViewModelBase):
    detailsChanged = Signal()
    taxOptionsChanged = Signal()
    selectedTaxesChanged = Signal()
    summaryChanged = Signal()
    viajeCandidatesChanged = Signal()
    includeNonFinalizedChanged = Signal(bool)
    pendingTarifaChanged = Signal()
    viajeSelectorOpenChanged = Signal(bool)
    selectedViajeCandidatesChanged = Signal()
    pendingTarifaChoicesChanged = Signal()
    detailFieldsChanged = Signal()
    viajeCandidateColumnsChanged = Signal()
    headerLayoutItemsChanged = Signal()

    def __init__(
        self,
        *,
        catalog_service: ModeloCatalogService,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
        table_preferences_store: CatalogTablePreferencesStore | None = None,
    ) -> None:
        super().__init__(
            title="Nueva factura",
            catalog_service=catalog_service,
            workflow_service=workflow_service,
            reference_lookup_service=reference_lookup_service,
            client_lookup_key="factura.cliente_id",
        )
        self._selected_tax_ids: list[int] = []
        self._tax_options: list[dict[str, Any]] = []
        self._summary: dict[str, Any] = {}
        self._include_non_finalized = False
        self._pending_tarifa: dict[str, Any] = {}
        self._pending_tarifa_choices: list[dict[str, Any]] = []
        self._selected_viaje_candidate_ids: set[int] = set()
        self._viaje_selector_open = False
        self._table_preferences_store = table_preferences_store or InMemoryCatalogTablePreferencesStore()
        self._viaje_candidate_column_widths = self._table_preferences_store.load_column_widths(
            _VIAJE_SELECTOR_TABLE_KEY
        )
        self._viaje_candidate_model = SelectableCandidateTableModel(
            self,
            field_name="viaje_id",
            selected_ids_getter=lambda: self._selected_viaje_candidate_ids,
            columns=_apply_column_width_overrides(
                [
                    {"key": "selected", "label": "", "width": 40, "minWidth": 40, "alignment": "center", "resizable": False},
                    {"key": "referencia", "label": "Referencia", "width": 120, "minWidth": 96, "resizable": True},
                    {"key": "conductor_label", "label": "Conductor", "width": 130, "minWidth": 110, "resizable": True},
                    {"key": "ruta_label", "label": "Ruta", "width": 260, "minWidth": 180, "resizable": True},
                    {"key": "fecha_posicionamiento", "label": "Posicionamiento", "width": 132, "minWidth": 120, "resizable": True},
                    {"key": "tipo_viaje", "label": "Tipo", "width": 110, "minWidth": 90, "resizable": True},
                    {"key": "dias_viajados", "label": "Dias viajados", "width": 54, "minWidth": 54, "alignment": "right", "resizable": True},
                ],
                self._viaje_candidate_column_widths,
            ),
        )
        self._register_lookup_field(
            "viaje_id",
            search=self._search_viaje_lookup_options,
            resolve=self._resolve_viaje_lookup_options,
        )
        self._details: list[dict[str, Any]] = []
        self.reset()
        self._load_tax_options()

    @Property("QVariantList", notify=detailsChanged)
    def details(self) -> list[dict[str, Any]]:
        return [self._detail_display(item) for item in self._details]

    @Property("QVariantList", notify=detailFieldsChanged)
    def detail_fields(self) -> list[dict[str, Any]]:
        return [
            {"name": "descripcion", "label": "Descripcion", "kind": "text", "span": 2, "full_width": True},
            {"name": "source_costo", "label": "Costo", "kind": "money", "span": 1, "full_width": False},
            {"name": "source_moneda", "label": "Moneda", "kind": "enum", "span": 1, "full_width": False},
            {"name": "costo", "label": "Total", "kind": "money", "span": 1, "full_width": False, "read_only": True},
            {"name": "conductor", "label": "Conductor", "kind": "text", "span": 1, "full_width": False, "read_only": True},
            {"name": "ruta", "label": "Ruta", "kind": "text", "span": 1, "full_width": False, "read_only": True},
        ]

    @Property("QVariantList", notify=headerLayoutItemsChanged)
    def header_layout_items(self) -> list[dict[str, Any]]:
        return self._serialize_header_layout_items()

    @Property("QVariantList", notify=taxOptionsChanged)
    def tax_options(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._tax_options]

    @Property("QVariantList", notify=selectedTaxesChanged)
    def selected_taxes(self) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        option_index = {int(option["id"]): option for option in self._tax_options if option.get("id") is not None}
        for tax_id in self._selected_tax_ids:
            option = option_index.get(int(tax_id))
            if option is not None:
                selected.append(dict(option))
        return selected

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, Any]:
        return dict(self._summary)

    @Property("QVariantList", notify=viajeCandidatesChanged)
    def viaje_candidates(self) -> list[dict[str, Any]]:
        return self.lookup_options("viaje_id")

    @Property(QObject, constant=True)
    def viaje_candidate_model(self) -> SelectableCandidateTableModel:
        return self._viaje_candidate_model

    @Property("QVariantList", notify=viajeCandidateColumnsChanged)
    def viaje_candidate_columns(self) -> list[dict[str, Any]]:
        return self._viaje_candidate_model.columns()

    @Property(bool, notify=includeNonFinalizedChanged)
    def include_non_finalized(self) -> bool:
        return self._include_non_finalized

    @Property("QVariantMap", notify=pendingTarifaChanged)
    def pending_tarifa(self) -> dict[str, Any]:
        return dict(self._pending_tarifa)

    @Property("QVariantList", notify=pendingTarifaChoicesChanged)
    def pending_tarifa_choices(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._pending_tarifa_choices]

    @Property("QVariantList", notify=selectedViajeCandidatesChanged)
    def selected_viaje_candidate_ids(self) -> list[int]:
        return sorted(self._selected_viaje_candidate_ids)

    @Property(bool, notify=viajeSelectorOpenChanged)
    def viaje_selector_open(self) -> bool:
        return self._viaje_selector_open

    def load(self, record_id: int | None) -> None:
        self.is_busy = True
        self._set_error_message("")
        try:
            if record_id is None:
                self._set_mode(FormMode.CREATE)
                self._set_record_id(None)
                self._set_title("Nueva factura")
                self.reset()
                self._set_dirty(False)
                self.loaded.emit(dict(self._values))
                return

            payload = self._workflow_service.factura.get_form_state(int(record_id))
            self._set_mode(FormMode.VIEW if self._mode == FormMode.VIEW else FormMode.EDIT)
            self._set_record_id(int(record_id))
            action_label = "Detalle" if self._mode == FormMode.VIEW else "Editar"
            self._set_title(f"{action_label} factura #{record_id}")
            self._replace_values(payload["values"], dirty=False)
            self._details = payload["details"]
            self._selected_tax_ids = payload["tax_ids"]
            self.detailsChanged.emit()
            self.selectedTaxesChanged.emit()
            self._refresh_summary()
            self.prime_client_field()
            self._set_dirty(False)
            self.loaded.emit(dict(self._values))
        except Exception as exc:
            self._set_error_message(str(exc))
            self._set_valid(False)
        finally:
            self.is_busy = False

    def reset(self) -> None:
        now_text = format_field_value_for_ui(kind="datetime", value=datetime.now())
        self._replace_values(
            {
                "numero_factura": "",
                "fecha_emision": now_text,
                "cliente_id": "",
                "dias_credito": "30",
                "moneda": Moneda.NIO.value,
                "tasa_cambio": "1.0000",
            },
            dirty=False,
        )
        self._details = []
        self._selected_tax_ids = []
        self._pending_tarifa = {}
        self._pending_tarifa_choices = []
        self._selected_viaje_candidate_ids = set()
        self._viaje_selector_open = False
        self._include_non_finalized = False
        self._set_lookup_options("viaje_id", [])
        self._set_field_errors({})
        self._refresh_summary()
        self.detailsChanged.emit()
        self.selectedTaxesChanged.emit()
        self.viajeCandidatesChanged.emit()
        self.pendingTarifaChanged.emit()
        self.pendingTarifaChoicesChanged.emit()
        self.selectedViajeCandidatesChanged.emit()
        self.viajeSelectorOpenChanged.emit(False)
        self.includeNonFinalizedChanged.emit(False)
        self.prime_client_field()
        self._set_valid(True)
        self._set_error_message("")
        self._set_dirty(False)

    @Slot(str, result=str)
    def field_error(self, field_name: str) -> str:
        return self._field_errors.get(field_name, "")

    @Slot(str)
    def prime_reference_field(self, field_name: str) -> None:
        self.prime_lookup_field(field_name)

    @Slot(str, str)
    def search_reference_options(self, field_name: str, term: str) -> None:
        self.search_lookup_options(field_name, term)

    @Slot(str, "QVariant", str)
    def set_reference_field_value(self, field_name: str, value: Any, label: str) -> None:
        self.set_lookup_field_value(field_name, value, label)

    def _serialize_header_layout_items(self) -> list[dict[str, Any]]:
        layout_items: list[dict[str, Any]] = []
        pending_row: list[dict[str, Any]] = []

        def flush_row() -> None:
            if not pending_row:
                return
            layout_items.append({"type": "row", "fields": list(pending_row)})
            pending_row.clear()

        for item in FACTURA_HEADER_LAYOUT.items:
            if isinstance(item, FormLayoutSectionItem):
                flush_row()
                layout_items.append({"type": "section", "title": item.title})
                continue

            field = FACTURA_HEADER_FIELDS.get(item.field_name)
            if field is None:
                continue

            entry = {
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
                "options": [
                    {"value": option.value, "label": option.display_label()}
                    for option in field.options
                ],
                "span": 2 if item.full_width else max(1, int(item.span or 1)),
                "full_width": bool(item.full_width),
            }
            if field.kind == "reference":
                entry["options"] = self.lookup_options(field.name)
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

    def submit(self) -> Mapping[str, Any] | None:
        if self.is_read_only:
            self._set_error_message("El formulario esta en modo solo lectura.")
            return None
        self._set_error_message("")
        payload, field_errors = self._build_submit_payload()
        self._set_field_errors(field_errors)
        if field_errors:
            self._set_error_message("Formulario invalido.")
            self._set_valid(False)
            return None

        self.is_busy = True
        try:
            if self._mode == FormMode.CREATE:
                result = self._workflow_service.factura.create(payload)
                result_id = result.get("id") if result is not None else None
                if result_id is not None:
                    self._set_record_id(int(result_id))
                    self._set_mode(FormMode.EDIT)
                    self._set_title(f"Editar factura #{result_id}")
            else:
                if self._record_id is None:
                    raise ValueError("record_id es requerido para editar")
                result = self._workflow_service.factura.update(int(self._record_id), payload)
            if result is None:
                raise ValueError("No se pudo guardar la factura.")
            self.load(int(result["id"]))
            self.saved.emit(dict(result))
            return result
        except Exception as exc:
            self._set_error_message(str(exc))
            return None
        finally:
            self.is_busy = False

    @Slot(int)
    def set_include_non_finalized(self, value: int) -> None:
        if self.is_read_only:
            return
        normalized = bool(value)
        if self._include_non_finalized != normalized:
            self._include_non_finalized = normalized
            self.includeNonFinalizedChanged.emit(normalized)
            self.search_viaje_candidates("")

    @Slot()
    def open_viaje_selector(self) -> None:
        if self.is_read_only:
            return
        if not self._viaje_selector_open:
            self._viaje_selector_open = True
            self.viajeSelectorOpenChanged.emit(True)
        self.search_viaje_candidates("")

    @Slot()
    def close_viaje_selector(self) -> None:
        if self._viaje_selector_open:
            self._viaje_selector_open = False
            self.viajeSelectorOpenChanged.emit(False)

    @Slot(int, int)
    def toggle_viaje_candidate_selection(self, viaje_id: int, selected: int) -> None:
        if self.is_read_only:
            return
        normalized = int(viaje_id)
        if bool(selected):
            self._selected_viaje_candidate_ids.add(normalized)
        else:
            self._selected_viaje_candidate_ids.discard(normalized)
        self.selectedViajeCandidatesChanged.emit()
        self._viaje_candidate_model.emit_selection_changed()

    @Slot(str, int)
    def set_viaje_candidate_column_width(self, column_key: str, width: int) -> None:
        normalized_key = str(column_key or "").strip()
        if not normalized_key or normalized_key == "selected":
            return
        column_map = {column["key"]: column for column in self._viaje_candidate_model.columns()}
        column = column_map.get(normalized_key)
        if column is None or not bool(column.get("resizable", True)):
            return
        min_width = int(column.get("minWidth") or 40)
        normalized_width = max(int(width), min_width)
        if not self._viaje_candidate_model.set_column_width(normalized_key, normalized_width):
            return
        self._viaje_candidate_column_widths[normalized_key] = normalized_width
        self._table_preferences_store.save_column_width(
            _VIAJE_SELECTOR_TABLE_KEY,
            normalized_key,
            normalized_width,
        )
        self.viajeCandidateColumnsChanged.emit()

    @Slot(int, result=bool)
    def is_viaje_candidate_selected(self, viaje_id: int) -> bool:
        return int(viaje_id) in self._selected_viaje_candidate_ids

    @Slot(result=bool)
    def add_selected_viajes(self) -> bool:
        if self.is_read_only:
            return False
        candidates = [
            item
            for item in self.lookup_options("viaje_id")
            if int(item.get("value", 0)) in self._selected_viaje_candidate_ids
        ]
        if not candidates:
            self._set_error_message("Selecciona al menos un viaje.")
            return False

        pending_choices: list[dict[str, Any]] = []
        no_tarifa: list[dict[str, Any]] = []
        added = False
        for candidate in candidates:
            if self._has_viaje_detail(int(candidate["value"])):
                continue
            tarifas = self._candidate_tarifas(candidate)
            if len(tarifas) == 1:
                self._append_viaje_detail(candidate, tarifas[0])
                added = True
            elif len(tarifas) > 1:
                pending_choices.append(self._pending_tarifa_choice(candidate))
            else:
                no_tarifa.append(candidate)

        self._selected_viaje_candidate_ids = set()
        self.selectedViajeCandidatesChanged.emit()
        self._viaje_candidate_model.emit_selection_changed()

        if pending_choices:
            self._pending_tarifa_choices = pending_choices
            self.pendingTarifaChoicesChanged.emit()
            self._set_error_message("Selecciona la tarifa para los viajes con multiples tarifas.")
            return False

        if no_tarifa:
            self._prepare_pending_tarifa(no_tarifa[0])
            return False

        return added

    @Slot(int, int)
    def set_pending_tarifa_selection(self, viaje_id: int, tarifa_id: int) -> None:
        if self.is_read_only:
            return
        changed = False
        next_choices: list[dict[str, Any]] = []
        for choice in self._pending_tarifa_choices:
            next_choice = dict(choice)
            if int(next_choice.get("viaje_id", 0)) == int(viaje_id):
                next_choice["selected_tarifa_id"] = int(tarifa_id)
                changed = True
            next_choices.append(next_choice)
        if changed:
            self._pending_tarifa_choices = next_choices
            self.pendingTarifaChoicesChanged.emit()

    @Slot(result=bool)
    def confirm_pending_tarifa_choices(self) -> bool:
        if self.is_read_only:
            return False
        if not self._pending_tarifa_choices:
            return False
        candidate_index = {int(item["value"]): item for item in self.lookup_options("viaje_id")}
        for choice in self._pending_tarifa_choices:
            viaje_id = int(choice.get("viaje_id", 0))
            tarifa_id = choice.get("selected_tarifa_id")
            candidate = candidate_index.get(viaje_id)
            if candidate is None or tarifa_id in (None, ""):
                self._set_error_message("Selecciona una tarifa para cada viaje.")
                return False
            tarifa = self._tarifa_by_id(candidate, int(tarifa_id))
            if tarifa is None:
                self._set_error_message("Selecciona una tarifa valida.")
                return False

        for choice in list(self._pending_tarifa_choices):
            viaje_id = int(choice["viaje_id"])
            candidate = candidate_index[viaje_id]
            tarifa = self._tarifa_by_id(candidate, int(choice["selected_tarifa_id"]))
            if tarifa is not None and not self._has_viaje_detail(viaje_id):
                self._append_viaje_detail(candidate, tarifa)
        self._pending_tarifa_choices = []
        self.pendingTarifaChoicesChanged.emit()
        return True

    @Slot()
    def cancel_pending_tarifa_choices(self) -> None:
        self._pending_tarifa_choices = []
        self.pendingTarifaChoicesChanged.emit()

    @Slot(str)
    def search_viaje_candidates(self, term: str) -> None:
        cliente_id = self._values.get("cliente_id")
        if cliente_id in (None, ""):
            self._set_lookup_options("viaje_id", [])
            return
        self.search_lookup_options("viaje_id", term)

    @Slot("QVariantMap", result=bool)
    def apply_navigation_context(self, context: object) -> bool:
        if self.is_read_only:
            return False
        if not isinstance(context, dict):
            self._set_error_message("Se requiere contexto de navegacion valido.")
            return False
        cliente_id = context.get("cliente_id")
        viaje_id = context.get("viaje_id")
        if cliente_id in (None, "") or viaje_id in (None, ""):
            self._set_error_message("Se requiere cliente y viaje para precargar la factura.")
            return False
        cliente_label = str(context.get("cliente_label") or "").strip()
        search_term = str(context.get("search_term") or "").strip()
        self.set_lookup_field_value("cliente_id", cliente_id, cliente_label)
        self.search_viaje_candidates(search_term)
        available_ids = {int(item["value"]) for item in self.lookup_options("viaje_id")}
        normalized_viaje_id = int(viaje_id)
        if normalized_viaje_id not in available_ids:
            self._set_error_message("El viaje ya no esta disponible para facturar.")
            return False
        self._selected_viaje_candidate_ids = {normalized_viaje_id}
        self.selectedViajeCandidatesChanged.emit()
        self._viaje_candidate_model.emit_selection_changed()
        return True

    @Slot(int, result=bool)
    def add_viaje_detail(self, viaje_id: int) -> bool:
        if self.is_read_only:
            return False
        try:
            candidate = next(item for item in self.lookup_options("viaje_id") if int(item["value"]) == int(viaje_id))
        except StopIteration:
            self._set_error_message("Selecciona un viaje valido.")
            return False

        if self._has_viaje_detail(int(viaje_id)):
            self._set_error_message("El viaje ya fue agregado a la factura.")
            return False

        tarifas = self._candidate_tarifas(candidate)
        if not tarifas:
            self._prepare_pending_tarifa(candidate)
            return False
        if len(tarifas) > 1:
            self._pending_tarifa_choices = [self._pending_tarifa_choice(candidate)]
            self.pendingTarifaChoicesChanged.emit()
            self._set_error_message("Selecciona la tarifa del viaje.")
            return False

        self._append_viaje_detail(candidate, tarifas[0])
        return True

    @Slot()
    def cancel_pending_tarifa(self) -> None:
        self._pending_tarifa = {}
        self.pendingTarifaChanged.emit()

    @Slot(str, "QVariant")
    def set_pending_tarifa_field(self, field_name: str, value: Any) -> None:
        if self.is_read_only:
            return
        if field_name not in self._pending_tarifa:
            return
        self._pending_tarifa[field_name] = value
        self.pendingTarifaChanged.emit()

    @Slot(result=bool)
    def create_tarifa_and_add_pending_viaje(self) -> bool:
        if self.is_read_only:
            return False
        if not self._pending_tarifa:
            return False
        cliente_id = self._values.get("cliente_id")
        if cliente_id in (None, ""):
            self._set_error_message("Selecciona un cliente antes de crear la tarifa.")
            return False
        try:
            payload = {
                "cliente_id": int(cliente_id),
                "ruta_id": int(self._pending_tarifa["ruta_id"]),
                "costo": _money_text(_normalize_money_input(self._pending_tarifa.get("costo"))),
                "moneda": str(self._pending_tarifa.get("moneda") or Moneda.NIO.value),
                "descripcion": str(self._pending_tarifa.get("descripcion") or "").strip() or None,
            }
            self._catalog_service.create("tarifa_flete", payload)
            candidate = next(item for item in self.lookup_options("viaje_id") if int(item["value"]) == int(self._pending_tarifa["viaje_id"]))
            candidate["tiene_tarifa"] = True
            candidate["tarifa_count"] = 1
            candidate["tarifa_costo"] = payload["costo"]
            candidate["tarifa_moneda"] = payload["moneda"]
            candidate["tarifas"] = [
                {
                    "id": None,
                    "label": f"{payload['moneda']} {payload['costo']}",
                    "costo": payload["costo"],
                    "moneda": payload["moneda"],
                    "descripcion": payload["descripcion"] or "",
                }
            ]
            self._set_lookup_options(
                "viaje_id",
                [
                    candidate if int(option["value"]) == int(self._pending_tarifa["viaje_id"]) else option
                    for option in self.lookup_options("viaje_id")
                ],
            )
            self._append_viaje_detail(candidate)
            self._pending_tarifa = {}
            self.pendingTarifaChanged.emit()
            return True
        except Exception as exc:
            self._set_error_message(str(exc))
            return False

    @Slot()
    def add_gasto_detail(self) -> None:
        if self.is_read_only:
            return
        index = len(self._details)
        self._details.append(
            {
                "id": None,
                "tipo": TipoDetalle.GASTO.value,
                "viaje_id": None,
                "gasto_id": None,
                "label": f"Gasto #{index + 1}",
                "descripcion": "",
                "gasto_tipo": TipoGasto.OTRO.value,
                "source_costo": "0.00",
                "source_moneda": self._values.get("moneda") or Moneda.NIO.value,
                "costo": "0.00",
            }
        )
        self._touch_details()

    @Slot(int)
    def remove_detail(self, index: int) -> None:
        if self.is_read_only:
            return
        if index < 0 or index >= len(self._details):
            return
        self._details.pop(index)
        self._touch_details()

    @Slot(int, str, "QVariant")
    def set_detail_field(self, index: int, field_name: str, value: Any) -> None:
        if self.is_read_only:
            return
        if index < 0 or index >= len(self._details):
            return
        detail = dict(self._details[index])
        if field_name not in detail:
            return
        detail[field_name] = value
        if field_name in {"source_costo", "source_moneda"}:
            detail["costo"] = self._convert_cost(detail.get("source_costo"), detail.get("source_moneda"))
        if field_name == "descripcion" and detail.get("tipo") == TipoDetalle.GASTO.value:
            label = str(value or "").strip()
            detail["label"] = label or f"Gasto #{index + 1}"
        self._details[index] = detail
        self._touch_details()

    @Slot(int)
    def add_tax(self, impuesto_id: int) -> None:
        if self.is_read_only:
            return
        normalized = int(impuesto_id)
        if normalized in self._selected_tax_ids:
            return
        self._selected_tax_ids.append(normalized)
        self.selectedTaxesChanged.emit()
        self._refresh_summary()
        self._set_dirty(True)

    @Slot(int)
    def remove_tax(self, impuesto_id: int) -> None:
        if self.is_read_only:
            return
        normalized = int(impuesto_id)
        if normalized in self._selected_tax_ids:
            self._selected_tax_ids = [item for item in self._selected_tax_ids if int(item) != normalized]
            self.selectedTaxesChanged.emit()
            self._refresh_summary()
            self._set_dirty(True)

    def _handle_client_change(self) -> None:
        self._set_lookup_options("viaje_id", [])
        self._pending_tarifa = {}
        self.pendingTarifaChanged.emit()
        retained = [detail for detail in self._details if detail.get("tipo") == TipoDetalle.GASTO.value]
        if len(retained) != len(self._details):
            self._details = retained
            self.detailsChanged.emit()
            self._refresh_summary()
        self._selected_viaje_candidate_ids = set()
        self._pending_tarifa_choices = []
        self.selectedViajeCandidatesChanged.emit()
        self.pendingTarifaChoicesChanged.emit()

    def _after_field_change(self, field_name: str) -> None:
        super()._after_field_change(field_name)
        if field_name in {"moneda", "tasa_cambio"}:
            if self._pending_tarifa:
                self._pending_tarifa["moneda"] = str(self._values.get("moneda") or Moneda.NIO.value)
                self.pendingTarifaChanged.emit()
            self._touch_details()

    def _is_dirty_externally(self) -> bool:
        return bool(self._details or self._selected_tax_ids)

    def _load_tax_options(self) -> None:
        self._tax_options = self._workflow_service.factura.list_tax_options()
        self.taxOptionsChanged.emit()

    def _append_viaje_detail(self, candidate: Mapping[str, Any], tarifa: Mapping[str, Any] | None = None) -> None:
        selected_tarifa = dict(tarifa or {})
        source_costo = selected_tarifa.get("costo", candidate.get("tarifa_costo") or "0.00")
        source_moneda = selected_tarifa.get("moneda", candidate.get("tarifa_moneda") or self._values.get("moneda") or Moneda.NIO.value)
        self._details.append(
            {
                "id": None,
                "tipo": TipoDetalle.VIAJE.value,
                "viaje_id": int(candidate["value"]),
                "gasto_id": None,
                "tarifa_id": selected_tarifa.get("id"),
                "label": candidate["label"],
                "descripcion": candidate.get("descripcion", ""),
                "ruta_label": candidate.get("ruta_label", ""),
                "conductor_label": candidate.get("conductor_label", ""),
                "fecha_posicionamiento": candidate.get("fecha_posicionamiento", ""),
                "tipo_viaje": candidate.get("tipo_viaje", ""),
                "gasto_tipo": "",
                "source_costo": str(source_costo or "0.00"),
                "source_moneda": str(source_moneda),
                "costo": self._convert_cost(source_costo, source_moneda),
            }
        )
        self._set_lookup_options(
            "viaje_id",
            [item for item in self.lookup_options("viaje_id") if int(item["value"]) != int(candidate["value"])],
        )
        self._touch_details()

    def _search_viaje_lookup_options(self, term: str) -> list[dict[str, Any]]:
        cliente_id = self._values.get("cliente_id")
        if cliente_id in (None, ""):
            return []
        selected_ids = {
            int(item["viaje_id"])
            for item in self._details
            if item.get("tipo") == TipoDetalle.VIAJE.value and item.get("viaje_id") not in (None, "")
        }
        return self._workflow_service.factura.search_viaje_candidates(
            int(cliente_id),
            str(term or ""),
            include_non_finalized=self._include_non_finalized,
            excluded_viaje_ids=tuple(selected_ids),
        )

    def _resolve_viaje_lookup_options(self, value: Any) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        for detail in self._details:
            if detail.get("tipo") == TipoDetalle.VIAJE.value and int(detail.get("viaje_id") or 0) == int(value):
                return [
                    {
                        "value": int(detail["viaje_id"]),
                        "label": str(detail.get("label") or f"Viaje #{detail['viaje_id']}"),
                        "descripcion": str(detail.get("descripcion") or ""),
                        "ruta_label": str(detail.get("ruta_label") or ""),
                        "tiene_tarifa": True,
                        "tarifa_count": 1,
                        "tarifas": [
                            {
                                "id": detail.get("tarifa_id"),
                                "label": f"{detail.get('source_moneda') or self._values.get('moneda') or Moneda.NIO.value} {detail.get('source_costo') or '0.00'}",
                                "costo": str(detail.get("source_costo") or "0.00"),
                                "moneda": str(detail.get("source_moneda") or self._values.get("moneda") or Moneda.NIO.value),
                                "descripcion": "",
                            }
                        ],
                        "tarifa_costo": str(detail.get("source_costo") or "0.00"),
                        "tarifa_moneda": str(detail.get("source_moneda") or self._values.get("moneda") or Moneda.NIO.value),
                    }
                ]
        return []

    def _after_lookup_options_changed(self, field_name: str) -> None:
        super()._after_lookup_options_changed(field_name)
        if field_name == "viaje_id":
            available_ids = {int(item["value"]) for item in self.lookup_options("viaje_id")}
            retained = {viaje_id for viaje_id in self._selected_viaje_candidate_ids if viaje_id in available_ids}
            if retained != self._selected_viaje_candidate_ids:
                self._selected_viaje_candidate_ids = retained
                self.selectedViajeCandidatesChanged.emit()
            self._viaje_candidate_model.reset_model()
            self.viajeCandidatesChanged.emit()

    def _candidate_tarifas(self, candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
        tarifas = candidate.get("tarifas") or []
        if isinstance(tarifas, list):
            return [dict(tarifa) for tarifa in tarifas if isinstance(tarifa, Mapping)]
        return []

    def _tarifa_by_id(self, candidate: Mapping[str, Any], tarifa_id: int) -> dict[str, Any] | None:
        for tarifa in self._candidate_tarifas(candidate):
            if tarifa.get("id") is not None and int(tarifa["id"]) == int(tarifa_id):
                return tarifa
        return None

    def _pending_tarifa_choice(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "viaje_id": int(candidate["value"]),
            "referencia": str(candidate.get("label") or f"Viaje #{candidate['value']}"),
            "ruta_label": str(candidate.get("ruta_label") or ""),
            "tarifas": self._candidate_tarifas(candidate),
            "selected_tarifa_id": None,
        }

    def _prepare_pending_tarifa(self, candidate: Mapping[str, Any]) -> None:
        self._pending_tarifa = {
            "viaje_id": int(candidate["value"]),
            "referencia": candidate["label"],
            "ruta_id": int(candidate["ruta_id"]),
            "ruta_label": candidate["ruta_label"],
            "costo": "",
            "moneda": self._values.get("moneda") or Moneda.NIO.value,
            "descripcion": "",
        }
        self.pendingTarifaChanged.emit()
        self._set_error_message("El viaje no tiene tarifa de flete. Crea una tarifa para agregarlo.")

    def _has_viaje_detail(self, viaje_id: int) -> bool:
        return any(
            int(item.get("viaje_id", -1)) == int(viaje_id)
            for item in self._details
            if item.get("viaje_id") is not None
        )

    def _touch_details(self) -> None:
        refreshed: list[dict[str, Any]] = []
        for index, detail in enumerate(self._details, start=1):
            next_detail = dict(detail)
            if "source_costo" in next_detail and "source_moneda" in next_detail:
                next_detail["costo"] = self._convert_cost(next_detail.get("source_costo"), next_detail.get("source_moneda"))
            if next_detail.get("tipo") == TipoDetalle.GASTO.value:
                label = str(next_detail.get("descripcion") or "").strip()
                next_detail["label"] = label or f"Gasto #{index}"
            refreshed.append(next_detail)
        self._details = refreshed
        self.detailsChanged.emit()
        self._refresh_summary()
        self._set_dirty(True)

    def _refresh_summary(self) -> None:
        subtotal = q2(sum((_as_decimal(item.get("costo"), places=2) for item in self._details), Decimal("0.00")))
        impuestos = Decimal("0.00")
        retenciones = Decimal("0.00")
        for option in self.selected_taxes:
            porcentaje = _as_decimal(option.get("porcentaje"), places=4)
            if option.get("tipo") == TipoImpuesto.RETENCION.value:
                retenciones += porcentaje
            else:
                impuestos += porcentaje
        total = q2(subtotal + subtotal * (impuestos / Decimal("100")) - subtotal * (retenciones / Decimal("100")))
        self._summary = {
            "subtotal": _money_text(subtotal),
            "subtotal_display": _money_display_text(subtotal, self._values.get("moneda")),
            "retenciones": _money_text(subtotal * (retenciones / Decimal("100"))),
            "retenciones_display": _money_display_text(subtotal * (retenciones / Decimal("100")), self._values.get("moneda")),
            "impuestos": _money_text(subtotal * (impuestos / Decimal("100"))),
            "impuestos_display": _money_display_text(subtotal * (impuestos / Decimal("100")), self._values.get("moneda")),
            "total": _money_text(total),
            "total_display": _money_display_text(total, self._values.get("moneda")),
            "details_count": len(self._details),
        }
        self.summaryChanged.emit()
        self._set_valid(not bool(self._validate_form()[1]))

    def _convert_cost(self, source_cost: Any, source_currency: Any) -> str:
        base_cost = _as_decimal(source_cost, places=2)
        invoice_currency = str(self._values.get("moneda") or Moneda.NIO.value)
        detail_currency = str(source_currency or invoice_currency)
        rate = _as_decimal(self._values.get("tasa_cambio") or "1.0000", places=4)
        if detail_currency == invoice_currency or rate <= Decimal("0"):
            return _money_text(base_cost)
        if detail_currency == Moneda.USD.value and invoice_currency == Moneda.NIO.value:
            return _money_text(base_cost * rate)
        if detail_currency == Moneda.NIO.value and invoice_currency == Moneda.USD.value:
            return _money_text(base_cost / rate)
        return _money_text(base_cost)

    def _validate_form(self) -> tuple[dict[str, Any], dict[str, str]]:
        payload: dict[str, Any] = {}
        errors: dict[str, str] = {}

        numero_factura = str(self._values.get("numero_factura") or "").strip()
        if not numero_factura:
            errors["numero_factura"] = "Este campo es obligatorio."
        payload["numero_factura"] = numero_factura

        try:
            payload["fecha_emision"] = _normalize_datetime_input(self._values.get("fecha_emision"), label="Fecha emision")
        except ValueError as exc:
            errors["fecha_emision"] = str(exc)

        try:
            payload["cliente_id"] = _normalize_reference_id(self._values.get("cliente_id"), label="Cliente")
        except ValueError as exc:
            errors["cliente_id"] = str(exc)

        try:
            payload["dias_credito"] = _normalize_int_input(self._values.get("dias_credito"), label="Dias de credito")
        except ValueError as exc:
            errors["dias_credito"] = str(exc)

        moneda = str(self._values.get("moneda") or Moneda.NIO.value)
        if moneda not in {Moneda.NIO.value, Moneda.USD.value}:
            errors["moneda"] = "Selecciona una moneda valida."
        payload["moneda"] = moneda

        try:
            payload["tasa_cambio"] = _rate_text(_normalize_rate_input(self._values.get("tasa_cambio")))
        except ValueError as exc:
            errors["tasa_cambio"] = str(exc)

        if not self._details:
            errors["details"] = "Agrega al menos un detalle."

        detail_payloads: list[dict[str, Any]] = []
        seen_viaje_ids: set[int] = set()
        for index, detail in enumerate(self._details, start=1):
            if detail.get("tipo") == TipoDetalle.VIAJE.value:
                viaje_id = detail.get("viaje_id")
                if viaje_id in (None, ""):
                    errors[f"detail_{index}"] = "Cada detalle de viaje requiere un viaje."
                    continue
                normalized_viaje_id = int(viaje_id)
                if normalized_viaje_id in seen_viaje_ids:
                    errors[f"detail_{index}"] = "No puedes repetir el mismo viaje."
                    continue
                seen_viaje_ids.add(normalized_viaje_id)
                detail_payloads.append(
                    {
                        **({"id": int(detail["id"])} if detail.get("id") is not None else {}),
                        "tipo": TipoDetalle.VIAJE.value,
                        "viaje_id": normalized_viaje_id,
                        "costo": self._convert_cost(detail.get("source_costo"), detail.get("source_moneda")),
                    }
                )
                continue

            try:
                gasto_data = {
                    **({"id": int(detail["gasto_id"])} if detail.get("gasto_id") not in (None, "") else {}),
                    "tipo": str(detail.get("gasto_tipo") or TipoGasto.OTRO.value),
                    "descripcion": str(detail.get("descripcion") or "").strip() or None,
                    "costo": _money_text(_normalize_money_input(detail.get("source_costo"))),
                    "moneda": str(detail.get("source_moneda") or payload.get("moneda", Moneda.NIO.value)),
                }
                detail_payloads.append(
                    {
                        **({"id": int(detail["id"])} if detail.get("id") is not None else {}),
                        "tipo": TipoDetalle.GASTO.value,
                        **({"gasto_id": int(detail["gasto_id"])} if detail.get("gasto_id") not in (None, "") else {}),
                        "costo": self._convert_cost(gasto_data["costo"], gasto_data["moneda"]),
                        "gasto_data": gasto_data,
                    }
                )
            except ValueError as exc:
                errors[f"detail_{index}"] = f"Gasto {index}: {exc}"

        if errors:
            return {}, errors

        factura_payload = {
            "numero_factura": payload["numero_factura"],
            "fecha_emision": payload["fecha_emision"],
            "cliente_id": payload["cliente_id"],
            "dias_credito": payload["dias_credito"],
            "moneda": payload["moneda"],
            "tasa_cambio": payload["tasa_cambio"],
        }
        if self._record_id is not None:
            factura_payload["id"] = int(self._record_id)
        return {
            "factura": factura_payload,
            "detalles_data": detail_payloads,
            "impuestos": [int(tax_id) for tax_id in self._selected_tax_ids],
        }, errors

    def _build_submit_payload(self) -> tuple[dict[str, Any], dict[str, str]]:
        payload, errors = self._validate_form()
        self._set_valid(not bool(errors))
        return payload, errors

    def _detail_display(self, item: Mapping[str, Any]) -> dict[str, Any]:
        detail = dict(item)
        detail["costo_display"] = _money_display_text(detail.get("costo"), self._values.get("moneda"))
        detail["source_costo_display"] = _money_display_text(detail.get("source_costo"), detail.get("source_moneda"))
        return detail
