"""QML workbench backed by catalog schemas from application services."""

from __future__ import annotations

from typing import cast

from ...application.modelo.query_service import ModeloCatalogQueryService
from ...application.modelo.reference_service import ReferenceLookupService
from ...application.modelo.services import ModeloCatalogService
from ..qt import Property, QmlNamedElement, QmlUncreatable, Signal, Slot
from ..viewmodels.base_view_model import BaseViewModel
from .column_overrides import apply_catalog_column_overrides
from .definitions import CatalogViewDefinition, FormDefinition
from .form_host_view_model import FormHostViewModel
from .forms import GenericCatalogFormViewModel
from .registry import FormRegistry
from .screen_view_model import CatalogScreenViewModel
from .table_preferences import CatalogTablePreferencesStore, InMemoryCatalogTablePreferencesStore

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0

DEFAULT_WORKBENCH_CATALOGS: tuple[str, ...] = (
    "cliente",
    "ubicacion",
    "impuesto",
    "camion",
    "conductor",
    "furgon",
    "thermo",
)


def _build_form_registry(
    catalog_service: ModeloCatalogService,
    reference_lookup_service: ReferenceLookupService | None = None,
) -> FormRegistry:
    return FormRegistry(
        (
            FormDefinition(
                form_id="generic-catalog",
                qml_component="GenericCatalogForm.qml",
                view_model_factory=lambda catalog_name, mode, context: GenericCatalogFormViewModel(
                    catalog_name=catalog_name,
                    fields=context["view_definition"].generic_form_fields,
                    catalog_service=catalog_service,
                    reference_lookup_service=reference_lookup_service,
                    form_layout=context["view_definition"].form_layout,
                    title=context["view_definition"].title or catalog_name.replace("_", " ").title(),
                ),
                priority=0,
            ),
        )
    )


@QmlNamedElement("CatalogWorkbenchViewModel")
@QmlUncreatable("CatalogWorkbenchViewModel instances are created in Python and injected into QML.")
class CatalogWorkbenchViewModel(BaseViewModel):
    """Top-level QML workbench that hosts catalog test screens."""

    screensChanged = Signal()
    titleChanged = Signal()
    currentScreenChanged = Signal()
    currentCatalogNameChanged = Signal(str)
    errorMessageChanged = Signal(str)

    def __init__(self, screens: tuple[CatalogScreenViewModel, ...]) -> None:
        super().__init__()
        if not screens:
            raise ValueError("Se requiere al menos una pantalla de Catálogo")
        self._screens = {cast(str, screen.catalog_name): screen for screen in screens}
        self._screen_order = [cast(str, screen.catalog_name) for screen in screens]
        self._current_catalog_name = self._screen_order[0]
        self._initialized = False
        self._error_message = ""
        self._observed_screen: CatalogScreenViewModel | None = None
        self._observe_current_screen()

    @Property("QVariantList", notify=screensChanged)
    def screens(self) -> list[dict[str, str]]:
        return [
            {
                "catalog_name": cast(str, screen.catalog_name),
                "title": cast(str, screen.title),
            }
            for screen in self._screens_in_order()
        ]

    @Property(CatalogScreenViewModel, notify=currentScreenChanged)
    def current_screen(self) -> CatalogScreenViewModel:
        return self._screens[self._current_catalog_name]

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        return "OpenLogisticERP Workbench"

    @Property(str, notify=currentCatalogNameChanged)
    def current_catalog_name(self) -> str:
        return self._current_catalog_name

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Slot()
    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._screens[self._current_catalog_name].load_screen()

    @Slot(str)
    def select_catalog(self, catalog_name: str) -> None:
        normalized = str(catalog_name or "").strip().lower()
        if not normalized or normalized not in self._screens:
            return
        if normalized == self._current_catalog_name:
            return
        self._current_catalog_name = normalized
        self._observe_current_screen()
        self.currentCatalogNameChanged.emit(normalized)
        self.currentScreenChanged.emit()
        self._screens[normalized].load_screen()

    def _screens_in_order(self) -> list[CatalogScreenViewModel]:
        return [self._screens[catalog_name] for catalog_name in self._screen_order]

    def _observe_current_screen(self) -> None:
        next_screen = self._screens[self._current_catalog_name]
        if next_screen is self._observed_screen:
            self._sync_current_screen_state()
            return
        if self._observed_screen is not None:
            self._disconnect_screen(self._observed_screen)
        self._observed_screen = next_screen
        next_screen.busyChanged.connect(self._handle_current_screen_busy_changed)
        next_screen.errorMessageChanged.connect(self._handle_current_screen_error_changed)
        self._sync_current_screen_state()

    def _disconnect_screen(self, screen: CatalogScreenViewModel) -> None:
        for signal, slot in (
            (screen.busyChanged, self._handle_current_screen_busy_changed),
            (screen.errorMessageChanged, self._handle_current_screen_error_changed),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass

    def _sync_current_screen_state(self) -> None:
        screen = self._observed_screen
        if screen is None:
            self.is_busy = False
            self._set_error_message("")
            return
        self.is_busy = screen.is_busy
        self._set_error_message(screen.error_message)

    def _set_error_message(self, value: str) -> None:
        normalized = str(value or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _handle_current_screen_busy_changed(self, busy: bool) -> None:
        self.is_busy = bool(busy)

    def _handle_current_screen_error_changed(self, message: str) -> None:
        self._set_error_message(message)


def build_default_catalog_workbench(
    query_service: ModeloCatalogQueryService,
    catalog_service: ModeloCatalogService,
    reference_lookup_service: ReferenceLookupService | None = None,
    *,
    catalog_names: tuple[str, ...] = DEFAULT_WORKBENCH_CATALOGS,
    table_preferences_store: CatalogTablePreferencesStore | None = None,
) -> CatalogWorkbenchViewModel:
    registry = _build_form_registry(catalog_service, reference_lookup_service=reference_lookup_service)
    resolved_table_preferences_store = table_preferences_store or InMemoryCatalogTablePreferencesStore()
    screens: list[CatalogScreenViewModel] = []
    for catalog_name in catalog_names:
        schema = query_service.get_schema(catalog_name)
        view_definition = CatalogViewDefinition.from_schema(
            schema,
            form_id="generic-catalog",
        )
        view_definition = apply_catalog_column_overrides(view_definition)
        form_host = FormHostViewModel(registry)
        screens.append(
            CatalogScreenViewModel(
                view_definition=view_definition,
                query_service=query_service,
                catalog_service=catalog_service,
                form_host=form_host,
                table_preferences_store=resolved_table_preferences_store,
            )
        )
    return CatalogWorkbenchViewModel(tuple(screens))
