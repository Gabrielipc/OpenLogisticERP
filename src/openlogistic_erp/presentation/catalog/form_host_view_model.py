"""Host ViewModel that keeps catalog screens neutral to concrete forms."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..qt import Property, QmlNamedElement, QmlUncreatable, Signal
from ..viewmodels.base_view_model import BaseViewModel
from .definitions import FormDefinition
from .forms import BaseFormViewModel
from .registry import FormRegistry
from .types import FormMode

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

@QmlNamedElement("FormHostViewModel")
@QmlUncreatable("FormHostViewModel instances are created in Python and injected into QML.")
class FormHostViewModel(BaseViewModel):
    activeFormChanged = Signal()
    activeComponentChanged = Signal(str)
    activeFormIdChanged = Signal(str)
    presentationModeChanged = Signal(str)
    navigationTitleChanged = Signal(str)
    isOpenChanged = Signal(bool)
    formSaved = Signal("QVariantMap")
    formCancelled = Signal()

    def __init__(
        self,
        registry: FormRegistry,
        *,
        presentation_mode: str = "drawer",
        navigation_title: str = "",
    ) -> None:
        super().__init__()
        self._registry = registry
        self._active_form: BaseFormViewModel | None = None
        self._active_component = ""
        self._active_form_id = ""
        self._active_open_mode: FormMode | None = None
        self._presentation_mode = str(presentation_mode or "drawer")
        self._navigation_title = str(navigation_title or "")
        self._is_open = False

    @Property(BaseFormViewModel, notify=activeFormChanged)
    def active_form(self) -> BaseFormViewModel | None:
        return self._active_form

    @Property(str, notify=activeComponentChanged)
    def active_component(self) -> str:
        return self._active_component

    @Property(str, notify=activeFormIdChanged)
    def active_form_id(self) -> str:
        return self._active_form_id

    @Property(str, notify=presentationModeChanged)
    def presentation_mode(self) -> str:
        return self._presentation_mode

    @Property(str, notify=navigationTitleChanged)
    def navigation_title(self) -> str:
        return self._navigation_title

    @Property(bool, notify=isOpenChanged)
    def is_open(self) -> bool:
        return self._is_open

    def open_form(
        self,
        catalog_name: str,
        *,
        mode: FormMode,
        record_id: int | None = None,
        preferred_form_id: str | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> BaseFormViewModel:
        definition = self._registry.resolve(
            catalog_name,
            mode=mode,
            preferred_form_id=preferred_form_id,
            context=context,
        )
        return self._activate_form(definition, catalog_name, mode=mode, record_id=record_id, context=context)

    def close_form(self) -> None:
        active = self._active_form
        if active is not None:
            self._disconnect_form(active)
            active.dispose()
        self._active_form = None
        self._set_active_component("")
        self._set_active_form_id("")
        self._active_open_mode = None
        self._set_is_open(False)
        self.activeFormChanged.emit()

    def _activate_form(
        self,
        definition: FormDefinition,
        catalog_name: str,
        *,
        mode: FormMode,
        record_id: int | None,
        context: Mapping[str, Any] | None,
    ) -> BaseFormViewModel:
        self.close_form()
        safe_context = dict(context or {})
        form_view_model = definition.view_model_factory(catalog_name, mode, safe_context)
        if not isinstance(form_view_model, BaseFormViewModel):
            raise TypeError("view_model_factory debe devolver BaseFormViewModel")

        self._active_form = form_view_model
        self._set_active_component(definition.qml_component)
        self._set_active_form_id(definition.form_id)
        self._set_presentation_mode(definition.presentation_mode)
        if definition.navigation_title is not None:
            self._set_navigation_title(definition.navigation_title)
        self._active_open_mode = mode
        self._set_is_open(True)
        self._connect_form(form_view_model)
        self.activeFormChanged.emit()
        form_view_model._set_mode(mode)
        form_view_model.load(record_id if mode in {FormMode.EDIT, FormMode.VIEW} else None)
        return form_view_model

    def set_navigation_defaults(self, *, presentation_mode: str | None = None, navigation_title: str | None = None) -> None:
        if presentation_mode is not None:
            self._set_presentation_mode(presentation_mode)
        if navigation_title is not None:
            self._set_navigation_title(navigation_title)

    def _connect_form(self, form_view_model: BaseFormViewModel) -> None:
        form_view_model.saved.connect(self._handle_form_saved)
        form_view_model.cancelled.connect(self._handle_form_cancelled)

    def _disconnect_form(self, form_view_model: BaseFormViewModel) -> None:
        for signal, slot in (
            (form_view_model.saved, self._handle_form_saved),
            (form_view_model.cancelled, self._handle_form_cancelled),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass

    def _handle_form_saved(self, payload: dict[str, Any]) -> None:
        normalized_payload = dict(payload)
        if self._active_open_mode is not None:
            normalized_payload["__form_mode"] = self._active_open_mode.value
        self.formSaved.emit(normalized_payload)
        self.close_form()

    def _handle_form_cancelled(self) -> None:
        self.formCancelled.emit()
        self.close_form()

    def _set_active_component(self, value: str) -> None:
        value = str(value or "")
        if self._active_component != value:
            self._active_component = value
            self.activeComponentChanged.emit(value)

    def _set_active_form_id(self, value: str) -> None:
        value = str(value or "")
        if self._active_form_id != value:
            self._active_form_id = value
            self.activeFormIdChanged.emit(value)

    def _set_presentation_mode(self, value: str) -> None:
        value = str(value or "drawer").strip().lower() or "drawer"
        if self._presentation_mode != value:
            self._presentation_mode = value
            self.presentationModeChanged.emit(value)

    def _set_navigation_title(self, value: str) -> None:
        value = str(value or "")
        if self._navigation_title != value:
            self._navigation_title = value
            self.navigationTitleChanged.emit(value)

    def _set_is_open(self, value: bool) -> None:
        value = bool(value)
        if self._is_open != value:
            self._is_open = value
            self.isOpenChanged.emit(value)
