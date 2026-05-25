"""Specialized catalog-form view model for Recibo."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from ....application.modelo.reference_service import ReferenceLookupService
from ....application.modelo.services import ModeloCatalogService, ModeloWorkflowService
from ....domain.modelo.field_validation import format_field_value_for_ui
from ....infrastructure.persistence.modelo.workflow_orm import Moneda, q2
from ...catalog.definitions import FormFieldOption, GenericFormFieldDefinition
from ...catalog.form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from ...catalog.types import FormMode
from ...qt import Property, QmlNamedElement, QmlUncreatable, QObject, Signal, Slot
from ..common import (
    SelectableCandidateTableModel,
    WorkflowFormViewModelBase,
    _as_decimal,
    _money_display_text,
    _money_text,
    _normalize_datetime_input,
    _normalize_money_input,
    _normalize_rate_input,
    _normalize_reference_id,
    _rate_text,
)

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

RECIBO_HEADER_LAYOUT = FormLayoutDefinition(
    items=(
        FormLayoutSectionItem(title="Cabecera"),
        FormLayoutFieldItem(field_name="referencia"),
        FormLayoutFieldItem(field_name="fecha_emision"),
        FormLayoutFieldItem(field_name="cliente_id", full_width=True),
        FormLayoutSectionItem(title="Pago"),
        FormLayoutFieldItem(field_name="monto"),
        FormLayoutFieldItem(field_name="moneda"),
        FormLayoutFieldItem(field_name="tasa_cambio", full_width=True),
    )
)

RECIBO_HEADER_FIELDS: dict[str, GenericFormFieldDefinition] = {
    "referencia": GenericFormFieldDefinition(
        name="referencia",
        label="Referencia",
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
    "monto": GenericFormFieldDefinition(
        name="monto",
        label="Monto",
        kind="money",
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
            FormFieldOption(value=Moneda.USD.value, label=Moneda.USD.value),
            FormFieldOption(value=Moneda.NIO.value, label=Moneda.NIO.value),
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


@QmlNamedElement("ReciboFormViewModel")
@QmlUncreatable("ReciboFormViewModel instances are created in Python and injected into QML.")
class ReciboFormViewModel(WorkflowFormViewModelBase):
    facturaCandidatesChanged = Signal()
    selectedFacturasChanged = Signal()
    allocationDraftFacturasChanged = Signal()
    summaryChanged = Signal()
    allocationEditorOpenChanged = Signal(bool)
    facturaSelectorOpenChanged = Signal(bool)
    selectedFacturaCandidatesChanged = Signal()
    selectedFacturaFieldsChanged = Signal()
    facturaCandidateColumnsChanged = Signal()
    headerLayoutItemsChanged = Signal()

    def __init__(
        self,
        *,
        catalog_service: ModeloCatalogService,
        workflow_service: ModeloWorkflowService,
        reference_lookup_service: ReferenceLookupService | None = None,
    ) -> None:
        super().__init__(
            title="Nuevo recibo",
            catalog_service=catalog_service,
            workflow_service=workflow_service,
            reference_lookup_service=reference_lookup_service,
            client_lookup_key="recibo.cliente_id",
        )
        self._register_lookup_field(
            "factura_id",
            search=self._search_factura_lookup_options,
            resolve=self._resolve_factura_lookup_options,
        )
        self._selected_facturas: list[dict[str, Any]] = []
        self._allocation_draft_facturas: list[dict[str, Any]] = []
        self._summary: dict[str, Any] = {}
        self._allocation_editor_open = False
        self._factura_selector_open = False
        self._selected_factura_candidate_ids: set[int] = set()
        self._factura_candidate_model = SelectableCandidateTableModel(
            self,
            field_name="factura_id",
            selected_ids_getter=lambda: self._selected_factura_candidate_ids,
            columns=[
                {"key": "selected", "label": "", "width": 40, "alignment": "center"},
                {"key": "label", "label": "Factura", "width": 320},
                {"key": "estado", "label": "Estado", "width": 150},
                {"key": "saldo_restante_display", "label": "Saldo restante", "width": 120, "alignment": "right"},
            ],
        )
        self.reset()

    @Property("QVariantList", notify=facturaCandidatesChanged)
    def factura_candidates(self) -> list[dict[str, Any]]:
        return self.lookup_options("factura_id")

    @Property(QObject, constant=True)
    def factura_candidate_model(self) -> SelectableCandidateTableModel:
        return self._factura_candidate_model

    @Property("QVariantList", notify=facturaCandidateColumnsChanged)
    def factura_candidate_columns(self) -> list[dict[str, Any]]:
        return self._factura_candidate_model.columns()

    @Property("QVariantList", notify=selectedFacturasChanged)
    def selected_facturas(self) -> list[dict[str, Any]]:
        return [self._factura_display(item) for item in self._selected_facturas]

    @Property("QVariantList", notify=allocationDraftFacturasChanged)
    def allocation_draft_facturas(self) -> list[dict[str, Any]]:
        return [self._factura_display(item) for item in self._allocation_draft_facturas]

    @Property("QVariantList", notify=selectedFacturaFieldsChanged)
    def selected_factura_fields(self) -> list[dict[str, Any]]:
        return [
            {"name": "label", "label": "Factura", "kind": "text", "span": 2, "full_width": True, "read_only": True},
            {"name": "applied_amount", "label": "Aplicado", "kind": "money", "span": 1, "full_width": False},
            {"name": "saldo_restante", "label": "Saldo restante", "kind": "money", "span": 1, "full_width": False, "read_only": True},
            {"name": "subtotal", "label": "Subtotal", "kind": "money", "span": 1, "full_width": False, "read_only": True},
            {"name": "retenciones", "label": "Retenciones", "kind": "money", "span": 1, "full_width": False, "read_only": True},
            {"name": "total", "label": "Total", "kind": "money", "span": 1, "full_width": False, "read_only": True},
            {"name": "estado", "label": "Estado", "kind": "text", "span": 1, "full_width": False, "read_only": True},
            {"name": "moneda", "label": "Moneda", "kind": "text", "span": 1, "full_width": False, "read_only": True},
        ]

    @Property("QVariantList", notify=headerLayoutItemsChanged)
    def header_layout_items(self) -> list[dict[str, Any]]:
        return self._serialize_header_layout_items()

    @Property("QVariantMap", notify=summaryChanged)
    def summary(self) -> dict[str, Any]:
        return dict(self._summary)

    @Property(bool, notify=allocationEditorOpenChanged)
    def allocation_editor_open(self) -> bool:
        return self._allocation_editor_open

    @Property(bool, notify=facturaSelectorOpenChanged)
    def factura_selector_open(self) -> bool:
        return self._factura_selector_open

    @Property("QVariantList", notify=selectedFacturaCandidatesChanged)
    def selected_factura_candidate_ids(self) -> list[int]:
        return sorted(self._selected_factura_candidate_ids)

    def load(self, record_id: int | None) -> None:
        self.is_busy = True
        self._set_error_message("")
        try:
            if record_id is None:
                self._set_mode(FormMode.CREATE)
                self._set_record_id(None)
                self._set_title("Nuevo recibo")
                self.reset()
                self._set_dirty(False)
                self.loaded.emit(dict(self._values))
                return

            payload = self._workflow_service.recibo.get_form_state(int(record_id))
            self._set_mode(FormMode.VIEW if self._mode == FormMode.VIEW else FormMode.EDIT)
            self._set_record_id(int(record_id))
            action_label = "Detalle" if self._mode == FormMode.VIEW else "Editar"
            self._set_title(f"{action_label} recibo #{record_id}")
            self._replace_values(payload["values"], dirty=False)
            self._selected_facturas = payload["selected_facturas"]
            self._factura_selector_open = False
            self._selected_factura_candidate_ids = set()
            self.selectedFacturasChanged.emit()
            self._set_lookup_options("factura_id", [])
            self.facturaSelectorOpenChanged.emit(False)
            self.selectedFacturaCandidatesChanged.emit()
            self.prime_client_field()
            self._refresh_summary(sync_allocations=False)
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
                "referencia": "",
                "fecha_emision": now_text,
                "cliente_id": "",
                "monto": "0.00",
                "moneda": Moneda.USD.value,
                "tasa_cambio": "1.0000",
            },
            dirty=False,
        )
        self._set_lookup_options("factura_id", [])
        self._selected_facturas = []
        self._allocation_draft_facturas = []
        self._allocation_editor_open = False
        self._factura_selector_open = False
        self._selected_factura_candidate_ids = set()
        self._set_field_errors({})
        self.selectedFacturasChanged.emit()
        self.allocationDraftFacturasChanged.emit()
        self.allocationEditorOpenChanged.emit(False)
        self.facturaSelectorOpenChanged.emit(False)
        self.selectedFacturaCandidatesChanged.emit()
        self._refresh_summary(sync_allocations=False)
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

        for item in RECIBO_HEADER_LAYOUT.items:
            if isinstance(item, FormLayoutSectionItem):
                flush_row()
                layout_items.append({"type": "section", "title": item.title})
                continue

            field = RECIBO_HEADER_FIELDS.get(item.field_name)
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
            if "allocations" in field_errors:
                self._set_allocation_editor_open(True)
            return None

        self.is_busy = True
        try:
            if self._mode == FormMode.CREATE:
                result = self._workflow_service.recibo.create(payload)
                result_id = result.get("id") if result is not None else None
                if result_id is not None:
                    self._set_record_id(int(result_id))
                    self._set_mode(FormMode.EDIT)
                    self._set_title(f"Editar recibo #{result_id}")
            else:
                if self._record_id is None:
                    raise ValueError("record_id es requerido para editar")
                result = self._workflow_service.recibo.update(int(self._record_id), payload)
            if result is None:
                raise ValueError("No se pudo guardar el recibo.")
            self._set_allocation_editor_open(False)
            self.load(int(result["id"]))
            self.saved.emit(dict(result))
            return result
        except Exception as exc:
            self._set_error_message(str(exc))
            return None
        finally:
            self.is_busy = False

    @Slot(str)
    def search_factura_candidates(self, term: str) -> None:
        cliente_id = self._values.get("cliente_id")
        if cliente_id in (None, ""):
            self._set_lookup_options("factura_id", [])
            return
        self.search_lookup_options("factura_id", term)

    @Slot("QVariantMap", result=bool)
    def apply_navigation_context(self, context: object) -> bool:
        if self.is_read_only:
            return False
        if not isinstance(context, dict):
            self._set_error_message("Se requiere contexto de navegacion valido.")
            return False
        cliente_id = context.get("cliente_id")
        factura_id = context.get("factura_id")
        if cliente_id in (None, "") or factura_id in (None, ""):
            self._set_error_message("Se requiere cliente y factura para precargar el recibo.")
            return False
        try:
            normalized_factura_id = int(factura_id)
        except (TypeError, ValueError):
            self._set_error_message("Se requiere una factura valida para precargar el recibo.")
            return False
        if normalized_factura_id <= 0:
            self._set_error_message("Se requiere una factura valida para precargar el recibo.")
            return False
        cliente_label = str(context.get("cliente_label") or "").strip()
        search_term = str(context.get("search_term") or context.get("numero_factura") or "").strip()
        if not search_term:
            factura = self._workflow_service.factura.get(normalized_factura_id)
            search_term = str(factura.get("numero_factura") or "").strip() if factura is not None else ""
        self.set_lookup_field_value("cliente_id", cliente_id, cliente_label)
        self.search_factura_candidates(search_term)
        available_ids = {int(item["value"]) for item in self.lookup_options("factura_id")}
        if normalized_factura_id not in available_ids:
            self._set_error_message("La factura ya no esta disponible para crear recibo.")
            return False
        return self.add_factura(normalized_factura_id)

    @Slot(int, result=bool)
    def add_factura(self, factura_id: int) -> bool:
        if self.is_read_only:
            return False
        try:
            candidate = next(item for item in self.lookup_options("factura_id") if int(item["value"]) == int(factura_id))
        except StopIteration:
            self._set_error_message("Selecciona una factura valida.")
            return False
        if any(int(item["id"]) == int(factura_id) for item in self._selected_facturas):
            self._set_error_message("La factura ya fue agregada al recibo.")
            return False
        candidate_copy = dict(candidate)
        candidate_copy["id"] = int(candidate_copy.get("id", candidate_copy["value"]))
        candidate_copy.setdefault("applied_amount", "0.00")
        self._selected_facturas.append(candidate_copy)
        self._set_lookup_options(
            "factura_id",
            [item for item in self.lookup_options("factura_id") if int(item["value"]) != int(factura_id)],
        )
        self.selectedFacturasChanged.emit()
        self._refresh_summary(sync_allocations=True)
        return True

    @Slot(int)
    def remove_factura(self, index: int) -> None:
        if self.is_read_only:
            return
        if index < 0 or index >= len(self._selected_facturas):
            return
        self._selected_facturas.pop(index)
        self.selectedFacturasChanged.emit()
        self._refresh_summary(sync_allocations=True)

    @Slot(int, str)
    def set_factura_applied_amount(self, index: int, value: str) -> None:
        if self.is_read_only:
            return
        if index < 0 or index >= len(self._allocation_draft_facturas):
            return
        factura = dict(self._allocation_draft_facturas[index])
        factura["applied_amount"] = value
        self._allocation_draft_facturas[index] = factura

    @Slot()
    def open_allocation_editor(self) -> None:
        if self.is_read_only:
            return
        self._allocation_draft_facturas = [dict(item) for item in self._selected_facturas]
        self.allocationDraftFacturasChanged.emit()
        self._refresh_summary(sync_allocations=False)
        self._set_allocation_editor_open(True)

    @Slot(result=bool)
    def apply_allocation_editor(self) -> bool:
        if self.is_read_only:
            return False
        if len(self._allocation_draft_facturas) != len(self._selected_facturas):
            return False
        self._selected_facturas = [dict(item) for item in self._allocation_draft_facturas]
        self.selectedFacturasChanged.emit()
        self._refresh_summary(sync_allocations=False)
        self._set_dirty(True)
        self._set_allocation_editor_open(False)
        return True

    @Slot()
    def close_allocation_editor(self) -> None:
        self._set_allocation_editor_open(False)

    @Slot()
    def open_factura_selector(self) -> None:
        if self.is_read_only:
            return
        if not self._factura_selector_open:
            self._factura_selector_open = True
            self.facturaSelectorOpenChanged.emit(True)
        self.search_factura_candidates("")

    @Slot()
    def close_factura_selector(self) -> None:
        if self._factura_selector_open:
            self._factura_selector_open = False
            self.facturaSelectorOpenChanged.emit(False)

    @Slot(int, int)
    def toggle_factura_candidate_selection(self, factura_id: int, selected: int) -> None:
        if self.is_read_only:
            return
        normalized = int(factura_id)
        if bool(selected):
            self._selected_factura_candidate_ids.add(normalized)
        else:
            self._selected_factura_candidate_ids.discard(normalized)
        self.selectedFacturaCandidatesChanged.emit()
        self._factura_candidate_model.emit_selection_changed()

    @Slot(int, result=bool)
    def is_factura_candidate_selected(self, factura_id: int) -> bool:
        return int(factura_id) in self._selected_factura_candidate_ids

    @Slot(result=bool)
    def add_selected_facturas(self) -> bool:
        if self.is_read_only:
            return False
        selected_candidates = [
            item
            for item in self.lookup_options("factura_id")
            if int(item.get("value", 0)) in self._selected_factura_candidate_ids
        ]
        if not selected_candidates:
            self._set_error_message("Selecciona al menos una factura.")
            return False

        added = False
        for candidate in list(selected_candidates):
            if self.add_factura(int(candidate["value"])):
                added = True
        self._selected_factura_candidate_ids = set()
        self.selectedFacturaCandidatesChanged.emit()
        self._factura_candidate_model.emit_selection_changed()
        return added

    def _is_dirty_externally(self) -> bool:
        return bool(self._selected_facturas)

    def _handle_client_change(self) -> None:
        self._set_lookup_options("factura_id", [])
        self._selected_facturas = []
        self.selectedFacturasChanged.emit()
        self._set_allocation_editor_open(False)
        self._selected_factura_candidate_ids = set()
        self.selectedFacturaCandidatesChanged.emit()
        self.close_factura_selector()
        self._refresh_summary(sync_allocations=False)

    def _after_field_change(self, field_name: str) -> None:
        super()._after_field_change(field_name)
        if field_name in {"monto", "moneda", "tasa_cambio"}:
            self._refresh_summary(sync_allocations=True)

    def _set_allocation_editor_open(self, value: bool) -> None:
        normalized = bool(value)
        if self._allocation_editor_open != normalized:
            self._allocation_editor_open = normalized
            self.allocationEditorOpenChanged.emit(normalized)

    def _search_factura_lookup_options(self, term: str) -> list[dict[str, Any]]:
        cliente_id = self._values.get("cliente_id")
        if cliente_id in (None, ""):
            return []
        selected_ids = {int(item["id"]) for item in self._selected_facturas}
        candidates = self._workflow_service.recibo.search_factura_candidates(
            int(cliente_id),
            str(term or ""),
            exclude_recibo_id=self._record_id,
            excluded_factura_ids=tuple(selected_ids),
        )
        return [self._factura_display(candidate) for candidate in candidates]

    def _resolve_factura_lookup_options(self, value: Any) -> list[dict[str, Any]]:
        if value in (None, ""):
            return []
        for factura in self._selected_facturas:
            if int(factura.get("id") or 0) == int(value):
                return [self._factura_display(factura)]
        return []

    def _after_lookup_options_changed(self, field_name: str) -> None:
        super()._after_lookup_options_changed(field_name)
        if field_name == "factura_id":
            available_ids = {int(item["value"]) for item in self.lookup_options("factura_id")}
            retained = {factura_id for factura_id in self._selected_factura_candidate_ids if factura_id in available_ids}
            if retained != self._selected_factura_candidate_ids:
                self._selected_factura_candidate_ids = retained
                self.selectedFacturaCandidatesChanged.emit()
            self._factura_candidate_model.reset_model()
            self.facturaCandidatesChanged.emit()

    def _recibo_currency(self) -> str:
        return str(self._values.get("moneda") or Moneda.USD.value)

    def _exchange_rate(self) -> Decimal:
        rate = _as_decimal(self._values.get("tasa_cambio") or "1.0000", places=4)
        return rate if rate > Decimal("0") else Decimal("0.0000")

    def _convert_invoice_to_recibo(self, amount: Any, invoice_currency: Any) -> Decimal:
        value = _as_decimal(amount, places=2)
        source = str(invoice_currency or self._recibo_currency())
        target = self._recibo_currency()
        rate = self._exchange_rate()
        if source == target or rate <= Decimal("0"):
            return q2(value)
        if source == Moneda.USD.value and target == Moneda.NIO.value:
            return q2(value * rate)
        if source == Moneda.NIO.value and target == Moneda.USD.value:
            return q2(value / rate)
        return q2(value)

    def _convert_recibo_to_invoice(self, amount: Any, invoice_currency: Any) -> Decimal:
        value = _as_decimal(amount, places=2)
        target = str(invoice_currency or self._recibo_currency())
        source = self._recibo_currency()
        rate = self._exchange_rate()
        if source == target or rate <= Decimal("0"):
            return q2(value)
        if source == Moneda.USD.value and target == Moneda.NIO.value:
            return q2(value * rate)
        if source == Moneda.NIO.value and target == Moneda.USD.value:
            return q2(value / rate)
        return q2(value)

    def _max_invoice_amount_within_recibo(self, recibo_amount: Decimal, invoice_currency: Any) -> Decimal:
        candidate = self._convert_recibo_to_invoice(recibo_amount, invoice_currency)
        cent = Decimal("0.01")
        while candidate > Decimal("0.00") and self._convert_invoice_to_recibo(candidate, invoice_currency) > recibo_amount:
            candidate = q2(candidate - cent)
        return candidate

    def _refresh_summary(self, *, sync_allocations: bool) -> None:
        subtotal = Decimal("0.00")
        retenciones = Decimal("0.00")
        total_facturas = Decimal("0.00")
        saldo_restante = Decimal("0.00")
        for item in self._selected_facturas:
            invoice_currency = item.get("moneda") or self._recibo_currency()
            subtotal += self._convert_invoice_to_recibo(item.get("subtotal"), invoice_currency)
            retenciones += self._convert_invoice_to_recibo(item.get("retenciones"), invoice_currency)
            total_facturas += self._convert_invoice_to_recibo(item.get("total"), invoice_currency)
            saldo_restante += self._convert_invoice_to_recibo(item.get("saldo_restante"), invoice_currency)

        recibo_monto = _as_decimal(self._values.get("monto"), places=2)
        if sync_allocations:
            self._auto_distribute_allocations(recibo_monto)

        total_aplicado = q2(
            sum(
                (
                    self._convert_invoice_to_recibo(item.get("applied_amount"), item.get("moneda"))
                    for item in self._selected_facturas
                ),
                Decimal("0.00"),
            )
        )
        balance = q2(recibo_monto - total_aplicado)
        self._summary = {
            "subtotal_facturas": _money_text(subtotal),
            "subtotal_facturas_display": _money_display_text(subtotal, self._values.get("moneda")),
            "retenciones": _money_text(retenciones),
            "retenciones_display": _money_display_text(retenciones, self._values.get("moneda")),
            "total_facturas": _money_text(total_facturas),
            "total_facturas_display": _money_display_text(total_facturas, self._values.get("moneda")),
            "saldo_restante_facturas": _money_text(saldo_restante),
            "saldo_restante_facturas_display": _money_display_text(saldo_restante, self._values.get("moneda")),
            "monto_recibo": _money_text(recibo_monto),
            "monto_recibo_display": _money_display_text(recibo_monto, self._values.get("moneda")),
            "total_aplicado": _money_text(total_aplicado),
            "total_aplicado_display": _money_display_text(total_aplicado, self._values.get("moneda")),
            "saldo_disponible": _money_text(balance if balance > Decimal("0.00") else Decimal("0.00")),
            "saldo_disponible_display": _money_display_text(balance if balance > Decimal("0.00") else Decimal("0.00"), self._values.get("moneda")),
            "faltante": _money_text(-balance if balance < Decimal("0.00") else Decimal("0.00")),
            "faltante_display": _money_display_text(-balance if balance < Decimal("0.00") else Decimal("0.00"), self._values.get("moneda")),
            "currency_context_display": self._summary_currency_context_display(),
        }
        self.summaryChanged.emit()
        if sync_allocations:
            self._sync_allocation_editor_state(recibo_monto=recibo_monto, saldo_restante=saldo_restante)
        self._set_valid(not bool(self._validate_form()[1]))

    def _sync_allocation_editor_state(self, *, recibo_monto: Decimal, saldo_restante: Decimal) -> None:
        if not self._selected_facturas or recibo_monto <= Decimal("0.00") or saldo_restante <= Decimal("0.00"):
            self._set_allocation_editor_open(False)
            return
        self._set_allocation_editor_open(False)

    def _auto_distribute_allocations(self, recibo_monto: Decimal) -> None:
        if not self._selected_facturas:
            return

        remaining_recibo = q2(recibo_monto)
        refreshed = []
        changed = False
        for item in self._selected_facturas:
            saldo_item = _as_decimal(item.get("saldo_restante"), places=2)
            invoice_currency = item.get("moneda") or self._recibo_currency()
            available_for_invoice = self._max_invoice_amount_within_recibo(remaining_recibo, invoice_currency)
            applied = Decimal("0.00")
            if remaining_recibo > Decimal("0.00") and saldo_item > Decimal("0.00"):
                applied = min(available_for_invoice, saldo_item)
                remaining_recibo = q2(
                    remaining_recibo - self._convert_invoice_to_recibo(applied, invoice_currency)
                )

            next_item = dict(item)
            next_amount = _money_text(applied)
            if str(next_item.get("applied_amount") or "") != next_amount:
                changed = True
            next_item["applied_amount"] = next_amount
            refreshed.append(next_item)

        if changed:
            self._selected_facturas = refreshed
            self.selectedFacturasChanged.emit()

    def _validate_form(self) -> tuple[dict[str, Any], dict[str, str]]:
        payload: dict[str, Any] = {}
        errors: dict[str, str] = {}

        referencia = str(self._values.get("referencia") or "").strip()
        if not referencia:
            errors["referencia"] = "Este campo es obligatorio."
        payload["referencia"] = referencia

        try:
            payload["fecha_emision"] = _normalize_datetime_input(self._values.get("fecha_emision"), label="Fecha emision")
        except ValueError as exc:
            errors["fecha_emision"] = str(exc)

        try:
            payload["cliente_id"] = _normalize_reference_id(self._values.get("cliente_id"), label="Cliente")
        except ValueError as exc:
            errors["cliente_id"] = str(exc)

        try:
            payload["monto"] = _money_text(_normalize_money_input(self._values.get("monto")))
        except ValueError as exc:
            errors["monto"] = str(exc)

        moneda = str(self._values.get("moneda") or Moneda.USD.value)
        if moneda not in {Moneda.USD.value, Moneda.NIO.value}:
            errors["moneda"] = "Selecciona una moneda valida."
        payload["moneda"] = moneda

        try:
            payload["tasa_cambio"] = _rate_text(_normalize_rate_input(self._values.get("tasa_cambio")))
        except ValueError as exc:
            errors["tasa_cambio"] = str(exc)

        if not self._selected_facturas:
            errors["facturas"] = "Agrega al menos una factura."
            return {}, errors

        total_saldo = q2(
            sum(
                (
                    self._convert_invoice_to_recibo(item.get("saldo_restante"), item.get("moneda"))
                    for item in self._selected_facturas
                ),
                Decimal("0.00"),
            )
        )
        recibo_monto = _as_decimal(payload.get("monto"), places=2)
        if recibo_monto > total_saldo:
            errors["monto"] = "El monto del recibo no puede exceder el saldo restante total."

        applications: list[dict[str, Any]] = []
        total_aplicado = Decimal("0.00")
        for item in self._selected_facturas:
            saldo_item = _as_decimal(item.get("saldo_restante"), places=2)
            aplicado = _as_decimal(item.get("applied_amount"), places=2)
            if aplicado <= Decimal("0.00"):
                continue
            if aplicado > saldo_item:
                errors["allocations"] = "No puedes aplicar mas que el saldo restante de una factura."
                break
            total_aplicado += self._convert_invoice_to_recibo(aplicado, item.get("moneda"))
            applications.append({"factura_id": int(item["id"]), "monto": _money_text(aplicado)})

        if not errors:
            if recibo_monto == total_saldo and total_aplicado == Decimal("0.00"):
                applications = [
                    {"factura_id": int(item["id"]), "monto": _money_text(item.get("saldo_restante"))}
                    for item in self._selected_facturas
                ]
                total_aplicado = total_saldo
            if recibo_monto < total_saldo and total_aplicado != recibo_monto:
                errors["allocations"] = "Asigna manualmente el monto del recibo a las facturas seleccionadas."
            if total_aplicado != recibo_monto:
                errors["allocations"] = "La suma aplicada debe consumir todo el monto del recibo."

        if errors:
            return {}, errors

        recibo_payload = {
            "referencia": payload["referencia"],
            "fecha_emision": payload["fecha_emision"],
            "cliente_id": payload["cliente_id"],
            "monto": payload["monto"],
            "moneda": payload["moneda"],
            "tasa_cambio": payload["tasa_cambio"],
        }
        if self._record_id is not None:
            recibo_payload["id"] = int(self._record_id)
        return {"recibo": recibo_payload, "facturas": applications}, errors

    def _build_submit_payload(self) -> tuple[dict[str, Any], dict[str, str]]:
        payload, errors = self._validate_form()
        self._set_valid(not bool(errors))
        return payload, errors

    def _summary_currency_context_display(self) -> str:
        recibo_currency = self._recibo_currency()
        invoice_currencies = sorted(
            {
                str(item.get("moneda") or recibo_currency)
                for item in self._selected_facturas
                if str(item.get("moneda") or recibo_currency) != recibo_currency
            }
        )
        if not invoice_currencies:
            return ""
        return (
            f"Recibo {recibo_currency} con facturas en {', '.join(invoice_currencies)} "
            f"@ {_rate_text(self._exchange_rate())}"
        )

    def _factura_display(self, item: Mapping[str, Any]) -> dict[str, Any]:
        factura = dict(item)
        currency = str(factura.get("moneda") or self._values.get("moneda") or self._recibo_currency())
        recibo_currency = self._recibo_currency()
        cross_currency = currency != recibo_currency
        for key in ("subtotal", "retenciones", "total", "saldo_restante", "applied_amount"):
            factura[f"{key}_display"] = _money_display_text(factura.get(key), currency)
            factura[f"{key}_recibo_display"] = _money_display_text(
                self._convert_invoice_to_recibo(factura.get(key), currency),
                recibo_currency,
            )
        factura["recibo_moneda"] = recibo_currency
        factura["cross_currency"] = cross_currency
        factura["currency_context_display"] = (
            f"Factura {currency} -> recibo {recibo_currency} @ {_rate_text(self._exchange_rate())}"
            if cross_currency
            else ""
        )
        factura["saldo_context_display"] = (
            f"{factura['saldo_restante_display']} / {factura['saldo_restante_recibo_display']}"
            if cross_currency
            else factura["saldo_restante_display"]
        )
        factura["applied_context_display"] = (
            f"{factura['applied_amount_display']} / {factura['applied_amount_recibo_display']}"
            if cross_currency
            else factura["applied_amount_display"]
        )
        return factura
