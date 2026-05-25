"""Application shell view models and curated module registry."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..application.auth import AuthModuleService
from ..application.dashboard import DashboardService
from ..application.modelo.query_service import ModeloCatalogQueryService
from ..application.modelo.reference_service import ReferenceLookupService
from ..application.modelo.services import ModeloCatalogService, ModeloWorkflowService
from ..application.rbac import RbacPermissionService
from ..application.reports import ReportCatalogService, ReportExportService, ReportGenerationService
from .authorization import PresentationAuthorizationService
from .catalog.column_overrides import apply_catalog_column_overrides
from .catalog.definitions import CatalogViewDefinition, FormDefinition
from .catalog.form_host_view_model import FormHostViewModel
from .catalog.forms import GenericCatalogFormViewModel
from .catalog.registry import FormRegistry
from .catalog.screen_view_model import CatalogScreenViewModel
from .catalog.table_preferences import CatalogTablePreferencesStore, InMemoryCatalogTablePreferencesStore
from .catalog.types import FormMode
from .dashboard import DashboardViewModel
from .qt import Property, QmlNamedElement, QmlUncreatable, QObject, Signal, Slot
from .reports import ReportsModuleViewModel
from .viewmodels.base_view_model import BaseViewModel
from .viewmodels.runtime_session_view_model import RuntimeSessionViewModel
from .workflows.circuito import CircuitoBasicFormViewModel, CircuitoWorkflowViewModel
from .workflows.common import WorkflowDescriptor, WorkflowModuleViewModel
from .workflows.factura import FacturaFormViewModel
from .workflows.recibo import ReciboFormViewModel
from .workflows.seguridad import SecurityAdminViewModel
from .workflows.viaje import ViajeFormViewModel, ViajeWorkflowViewModel

QML_IMPORT_NAME = "OpenLogistic.Models"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    title: str
    domain_id: str
    domain_title: str
    kind: str
    monogram: str
    summary: str
    icon_source: str = ""
    access_policy: str = "permission"
    enabled: bool = True
    catalog_name: str | None = None
    qml_component: str | None = None
    planned_actions: tuple[str, ...] = ()

    def to_map(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "title": self.title,
            "domain_id": self.domain_id,
            "domain_title": self.domain_title,
            "kind": self.kind,
            "monogram": self.monogram,
            "iconSource": self.icon_source,
            "summary": self.summary,
            "access_policy": self.access_policy,
            "enabled": self.enabled,
            "catalog_name": self.catalog_name,
            "module_type": self.kind,
            "qml_component": self.qml_component or "",
            "planned_actions": list(self.planned_actions),
        }


@dataclass(frozen=True)
class ModuleGroupDescriptor:
    domain_id: str
    title: str
    modules: tuple[ModuleDescriptor, ...]

    def to_map(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "title": self.title,
            "modules": [module.to_map() for module in self.modules],
        }


APP_MODULES: tuple[ModuleDescriptor, ...] = (
    ModuleDescriptor(
        "cliente",
        "Clientes",
        "planificacion",
        "Planificacion",
        "catalog",
        "CL",
        "Gestión de clientes y condiciones comerciales.",
        catalog_name="cliente",
        icon_source="qrc:/icons/modules/person_book",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "ubicacion",
        "Ubicaciones",
        "planificacion",
        "Planificacion",
        "catalog",
        "UB",
        "Destinos y puntos operativos disponibles.",
        catalog_name="ubicacion",
        icon_source="qrc:/icons/modules/location",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "camion",
        "Camiones",
        "planificacion",
        "Planificacion",
        "catalog",
        "CA",
        "Flota tractora disponible para operacion.",
        catalog_name="camion",
        icon_source="qrc:/icons/modules/truck",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "conductor",
        "Conductores",
        "planificacion",
        "Planificacion",
        "catalog",
        "CO",
        "Personal asignable a viajes y circuitos.",
        catalog_name="conductor",
        icon_source="qrc:/icons/modules/driver",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "furgon",
        "Furgones",
        "planificacion",
        "Planificacion",
        "catalog",
        "FU",
        "Unidades de arrastre y su configuracion.",
        icon_source="qrc:/icons/modules/package",
        catalog_name="furgon",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "thermo",
        "Thermos",
        "planificacion",
        "Planificacion",
        "catalog",
        "TH",
        "Inventario de thermos y su estado.",
        catalog_name="thermo",
        icon_source="qrc:/icons/modules/ac_unit",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "impuesto",
        "Impuestos",
        "contabilidad",
        "Contabilidad",
        "catalog",
        "IM",
        "Catálogo de impuestos y porcentajes.",
        catalog_name="impuesto",
        icon_source="qrc:/icons/modules/percent",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "viaje",
        "Viajes",
        "operacion",
        "Operacion",
        "workflow",
        "VI",
        "",
        qml_component="ViajeWorkflowPage.qml",
        icon_source="qrc:/icons/modules/road",
    ),
    ModuleDescriptor(
        "circuito",
        "Circuitos",
        "operacion",
        "Operacion",
        "workflow",
        "CI",
        "",
        qml_component="CircuitoWorkflowPage.qml",
        icon_source="qrc:/icons/modules/route",
    ),
    ModuleDescriptor(
        "factura",
        "Facturas",
        "tesoreria_facturacion",
        "Tesoreria / Facturacion",
        "catalog",
        "FA",
        "Listado estandar con formulario especializado para emision y ajuste de facturas.",
        catalog_name="factura",
        icon_source="qrc:/icons/modules/receipt_long",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "recibo",
        "Recibos",
        "tesoreria_facturacion",
        "Tesoreria / Facturacion",
        "catalog",
        "RE",
        "Listado estandar con formulario especializado para aplicaciones de cobro.",
        catalog_name="recibo",
        icon_source="qrc:/icons/modules/cash",
        qml_component="CatalogScreenPage.qml",
    ),
    ModuleDescriptor(
        "reportes",
        "Reportes",
        "analitica",
        "Analitica",
        "workflow",
        "RP",
        "Reportes operativos, financieros y comerciales.",
        access_policy="superuser",
        icon_source="qrc:/actions/general/monitoring",
        qml_component="ReportsModulePage.qml",
    ),
    ModuleDescriptor(
        "seguridad",
        "Seguridad",
        "administracion",
        "Administracion",
        "workflow",
        "SE",
        "Administracion de usuarios, roles y permisos.",
        access_policy="superuser",
        icon_source="qrc:/icons/modules/security",
        qml_component="SecurityAdminPage.qml",
    ),
)

INITIAL_MODULE_ID = "cliente"
SHELL_HOME_VIEW = "dashboard"
SHELL_MODULE_VIEW = "module"
SPECIALIZED_DASHBOARD_MODULE_IDS = frozenset({"reportes", "seguridad"})


def _build_form_registry(
    catalog_service: ModeloCatalogService,
    workflow_service: ModeloWorkflowService | None = None,
    reference_lookup_service: ReferenceLookupService | None = None,
    table_preferences_store: CatalogTablePreferencesStore | None = None,
) -> FormRegistry:
    definitions: list[FormDefinition] = [
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
    ]
    if workflow_service is not None:
        definitions.extend(
            (
                FormDefinition(
                    form_id="circuito-basic",
                    qml_component="GenericCatalogForm.qml",
                    presentation_mode="page",
                    navigation_title="Circuitos",
                    catalog_names=("circuito",),
                    supported_modes=(FormMode.EDIT,),
                    view_model_factory=lambda catalog_name, mode, context: CircuitoBasicFormViewModel(
                        workflow_service=workflow_service,
                    ),
                    priority=100,
                ),
                FormDefinition(
                    form_id="viaje-workflow",
                    qml_component="ViajeWorkflowForm.qml",
                    presentation_mode="page",
                    navigation_title="Viajes",
                    catalog_names=("viaje",),
                    view_model_factory=lambda catalog_name, mode, context: ViajeFormViewModel(
                        workflow_service=workflow_service,
                        reference_lookup_service=reference_lookup_service,
                    ),
                    priority=100,
                ),
                FormDefinition(
                    form_id="factura-workflow",
                    qml_component="FacturaWorkflowForm.qml",
                    presentation_mode="page",
                    navigation_title="Facturas",
                    catalog_names=("factura",),
                    view_model_factory=lambda catalog_name, mode, context: FacturaFormViewModel(
                        catalog_service=catalog_service,
                        workflow_service=workflow_service,
                        reference_lookup_service=reference_lookup_service,
                        table_preferences_store=table_preferences_store,
                    ),
                    priority=100,
                ),
                FormDefinition(
                    form_id="recibo-workflow",
                    qml_component="ReciboWorkflowForm.qml",
                    presentation_mode="page",
                    navigation_title="Recibos",
                    catalog_names=("recibo",),
                    view_model_factory=lambda catalog_name, mode, context: ReciboFormViewModel(
                        catalog_service=catalog_service,
                        workflow_service=workflow_service,
                        reference_lookup_service=reference_lookup_service,
                    ),
                    priority=100,
                ),
            )
        )
    return FormRegistry(tuple(definitions))


@QmlNamedElement("WorkflowPlaceholderViewModel")
@QmlUncreatable("WorkflowPlaceholderViewModel instances are created in Python and injected into QML.")
class WorkflowPlaceholderViewModel(WorkflowModuleViewModel):
    plannedActionsChanged = Signal()

    def __init__(self, descriptor: ModuleDescriptor) -> None:
        super().__init__(
            WorkflowDescriptor(
                module_id=descriptor.module_id,
                title=descriptor.title,
                domain_title=descriptor.domain_title,
                summary=descriptor.summary,
                qml_component="WorkflowPlaceholderPage.qml",
            )
        )
        self._module_descriptor = descriptor

    @Property("QVariantList", notify=plannedActionsChanged)
    def planned_actions(self) -> list[str]:
        return list(self._module_descriptor.planned_actions)


@QmlNamedElement("AppShellViewModel")
@QmlUncreatable("AppShellViewModel instances are created in Python and injected into QML.")
class AppShellViewModel(BaseViewModel):
    titleChanged = Signal()
    currentViewChanged = Signal(str)
    moduleGroupsChanged = Signal()
    dashboardModulesChanged = Signal()
    currentModuleIdChanged = Signal(str)
    currentModuleChanged = Signal()
    currentCatalogScreenChanged = Signal()
    currentWorkflowModuleChanged = Signal()
    currentWorkflowComponentChanged = Signal(str)
    errorMessageChanged = Signal(str)
    emptyStateChanged = Signal(str)
    dashboardViewModelChanged = Signal()
    currentCatalogSubpageChanged = Signal(str)

    def __init__(
        self,
        module_definitions: tuple[ModuleDescriptor, ...],
        catalog_screens: dict[str, CatalogScreenViewModel],
        workflow_modules: dict[str, Any],
        *,
        initial_module_id: str = INITIAL_MODULE_ID,
        runtime_session: RuntimeSessionViewModel | None = None,
        authorization_service: PresentationAuthorizationService | None = None,
        dashboard_view_model: DashboardViewModel | None = None,
    ) -> None:
        super().__init__()
        self._module_definitions = module_definitions
        self._module_by_id = {descriptor.module_id: descriptor for descriptor in module_definitions}
        self._module_groups = _build_module_groups(module_definitions)
        self._catalog_screens = dict(catalog_screens)
        self._workflow_modules = dict(workflow_modules)
        self._authorization = authorization_service
        self._current_module_id = initial_module_id
        self._current_view = SHELL_HOME_VIEW
        self._error_message = ""
        self._empty_state_message = ""
        self._initialized = False
        self._observed_catalog_screen: CatalogScreenViewModel | None = None
        self._runtime_session = runtime_session
        self._dashboard_view_model = dashboard_view_model or DashboardViewModel(
            _EmptyDashboardService(),
            authorization_service=authorization_service,
        )
        self._current_catalog_subpage = ""

        if self._current_module_id not in self._module_by_id:
            raise ValueError(f"Initial module {initial_module_id!r} is not defined")
        self._apply_authorization_permissions()
        self._ensure_current_module_allowed()
        self._observe_current_catalog_screen()

    @Property(str, notify=titleChanged)
    def title(self) -> str:
        if self._current_view == SHELL_HOME_VIEW:
            return "Inicio | OpenLogisticERP"
        if not self._current_module_id:
            return "OpenLogisticERP"
        descriptor = self._module_by_id[self._current_module_id]
        return f"{descriptor.title} | OpenLogisticERP"

    @Property(str, notify=currentViewChanged)
    def current_view(self) -> str:
        return self._current_view

    @Property(DashboardViewModel, notify=dashboardViewModelChanged)
    def dashboard_view_model(self) -> DashboardViewModel:
        return self._dashboard_view_model

    @Property("QVariantList", notify=moduleGroupsChanged)
    def module_groups(self) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for group in self._module_groups:
            modules = tuple(module for module in group.modules if self._is_sidebar_module(module) and self._can_read_module(module))
            if modules:
                groups.append(replace(group, modules=modules).to_map())
        return groups

    @Property("QVariantList", notify=dashboardModulesChanged)
    def dashboard_modules(self) -> list[dict[str, Any]]:
        return [
            descriptor.to_map()
            for descriptor in self._module_definitions
            if self._is_dashboard_module(descriptor) and self._can_read_module(descriptor)
        ]

    @Property(str, notify=currentModuleIdChanged)
    def current_module_id(self) -> str:
        return self._current_module_id

    @Property("QVariantMap", notify=currentModuleChanged)
    def current_module(self) -> dict[str, Any]:
        if not self._current_module_id:
            return {}
        return self._module_by_id[self._current_module_id].to_map()

    @Property(CatalogScreenViewModel, notify=currentCatalogScreenChanged)
    def current_catalog_screen(self) -> CatalogScreenViewModel | None:
        if not self._current_module_id:
            return None
        descriptor = self._module_by_id[self._current_module_id]
        if descriptor.kind != "catalog":
            return None
        return self._catalog_screens.get(self._current_module_id)

    @Property(str, notify=currentCatalogSubpageChanged)
    def current_catalog_subpage(self) -> str:
        return self._current_catalog_subpage

    @Property(QObject, notify=currentWorkflowModuleChanged)
    def current_workflow_module(self) -> QObject | None:
        if not self._current_module_id:
            return None
        descriptor = self._module_by_id[self._current_module_id]
        if descriptor.kind != "workflow":
            return None
        return self._workflow_modules.get(self._current_module_id)

    @Property(str, notify=currentWorkflowComponentChanged)
    def current_workflow_component(self) -> str:
        if not self._current_module_id or self._current_module_id not in self._module_by_id:
            return ""
        descriptor = self._module_by_id[self._current_module_id]
        module = self.current_workflow_module
        if module is None:
            return ""
        qml_component = getattr(module, "qml_component", "")
        if qml_component:
            return str(qml_component)
        return descriptor.qml_component or ""

    @Property(str, notify=currentWorkflowComponentChanged)
    def current_workflow_source(self) -> str:
        if not self._current_module_id or self._current_module_id not in self._module_by_id:
            return ""
        descriptor = self._module_by_id[self._current_module_id]
        if descriptor.kind != "workflow" or self.current_workflow_module is None:
            return ""
        workflow_component = self.current_workflow_component
        if not workflow_component:
            return ""
        if workflow_component == "WorkflowPlaceholderPage.qml":
            return f"workflows/common/{workflow_component}"
        if self._current_module_id == "reportes":
            return f"reports/{workflow_component}"
        return f"workflows/{self._current_module_id}/{workflow_component}"

    @Property(str, notify=errorMessageChanged)
    def error_message(self) -> str:
        return self._error_message

    @Property(str, notify=emptyStateChanged)
    def empty_state_message(self) -> str:
        return self._empty_state_message

    def _set_error_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._error_message != normalized:
            self._error_message = normalized
            self.errorMessageChanged.emit(normalized)

    def _set_empty_state_message(self, message: str) -> None:
        normalized = str(message or "")
        if self._empty_state_message != normalized:
            self._empty_state_message = normalized
            self.emptyStateChanged.emit(normalized)

    def _load_current_module(self) -> None:
        if not self._ensure_current_module_allowed():
            self._observe_current_catalog_screen()
            return
        descriptor = self._module_by_id[self._current_module_id]
        if descriptor.kind != "catalog":
            self._observe_current_catalog_screen()
            workflow_module = self.current_workflow_module
            initialize = getattr(workflow_module, "initialize", None)
            if callable(initialize):
                initialize()
            return
        screen = self._catalog_screens[self._current_module_id]
        self._observe_current_catalog_screen()
        screen.load_screen()

    @Slot()
    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._load_current_module()

    @Slot()
    def activate_runtime_session(self) -> None:
        self._apply_authorization_permissions()
        self._ensure_current_module_allowed()
        self.moduleGroupsChanged.emit()
        self.dashboardModulesChanged.emit()
        self.currentModuleIdChanged.emit(self._current_module_id)
        self.currentModuleChanged.emit()
        self.currentCatalogScreenChanged.emit()
        self.currentWorkflowModuleChanged.emit()
        self.currentWorkflowComponentChanged.emit(self.current_workflow_component)
        self.titleChanged.emit()
        if not self._initialized:
            self.initialize()
            return
        self.reload_current_module()

    @Slot()
    def reload_current_module(self) -> None:
        self._load_current_module()

    @Slot(bool)
    def handle_runtime_auth_changed(self, authenticated: bool) -> None:
        self._apply_authorization_permissions()
        self._ensure_current_module_allowed()
        self.moduleGroupsChanged.emit()
        self.dashboardModulesChanged.emit()
        self.currentModuleIdChanged.emit(self._current_module_id)
        self.currentModuleChanged.emit()
        self.currentCatalogScreenChanged.emit()
        self.currentWorkflowModuleChanged.emit()
        self.currentWorkflowComponentChanged.emit(self.current_workflow_component)
        self.titleChanged.emit()
        if bool(authenticated):
            self.activate_runtime_session()
            return
        if self._initialized:
            self.reload_current_module()
            return
        self._sync_current_catalog_state()

    @Slot()
    def go_home(self) -> None:
        if self._current_view == SHELL_HOME_VIEW:
            return
        self._reset_current_catalog_context()
        self._current_view = SHELL_HOME_VIEW
        self.currentViewChanged.emit(self._current_view)
        self.titleChanged.emit()

    @Slot(str)
    def select_module(self, module_id: str) -> None:
        normalized = str(module_id or "").strip().lower()
        if not normalized or normalized not in self._module_by_id:
            return
        if not self._can_read_module(self._module_by_id[normalized]):
            self._set_error_message(self._module_access_denied_message(self._module_by_id[normalized]))
            return
        if normalized == self._current_module_id:
            if self._current_view != SHELL_MODULE_VIEW:
                self._current_view = SHELL_MODULE_VIEW
                self.currentViewChanged.emit(self._current_view)
                self.titleChanged.emit()
                self._load_current_module()
            return
        self._reset_current_catalog_context()
        self._current_module_id = normalized
        if self._current_view != SHELL_MODULE_VIEW:
            self._current_view = SHELL_MODULE_VIEW
            self.currentViewChanged.emit(self._current_view)
        self._observe_current_catalog_screen()
        self.currentModuleIdChanged.emit(normalized)
        self.currentModuleChanged.emit()
        self.currentCatalogScreenChanged.emit()
        self.currentWorkflowModuleChanged.emit()
        self.currentWorkflowComponentChanged.emit(self.current_workflow_component)
        self.titleChanged.emit()
        self._load_current_module()

    @Slot(dict, result=bool)
    def navigate_to(self, route: object) -> bool:
        if not isinstance(route, dict):
            self._set_error_message("Se requiere una ruta valida.")
            return False
        module_id = str(route.get("module_id") or "").strip().lower()
        target = str(route.get("target") or "list").strip().lower() or "list"
        record_id = route.get("record_id")
        filters = route.get("filters")
        subpage = str(route.get("subpage") or "").strip()
        subpage_context = route.get("subpage_context") or route.get("subpageContext") or {}
        workflow_context = route.get("workflow_context") or route.get("workflowContext") or {}
        if not module_id or module_id not in self._module_by_id:
            self._set_error_message("Se requiere un modulo destino valido.")
            return False
        descriptor = self._module_by_id[module_id]
        if not self._can_read_module(descriptor):
            self._set_error_message(self._module_access_denied_message(descriptor))
            return False

        self.select_module(module_id)
        if self._current_module_id != module_id or self._current_view != SHELL_MODULE_VIEW:
            return False

        if target == "list":
            self._close_active_subpage()
            return True
        if target == "filtered_list":
            return self._open_filtered_list_route_target(descriptor, filters)
        if target == "subpage":
            return self._open_subpage_route_target(descriptor, subpage, subpage_context)
        if target == "create_form":
            return self._open_create_route_target(descriptor)
        if target == "create_form_with_context":
            return self._open_create_with_context_route_target(descriptor, workflow_context)
        if target == "edit_form":
            normalized_record_id = self._route_record_id(record_id)
            if normalized_record_id is None:
                return False
            return self._open_record_form_route_target(descriptor, normalized_record_id)
        if target == "detail":
            normalized_record_id = self._route_record_id(record_id)
            if normalized_record_id is None:
                return False
            return self._open_detail_route_target(descriptor, normalized_record_id)

        self._set_error_message(f"Destino de ruta no soportado: {target}")
        return False

    def _close_active_subpage(self) -> None:
        if self._current_catalog_subpage:
            self._current_catalog_subpage = ""
            self.currentCatalogSubpageChanged.emit("")
        screen = self.current_catalog_screen
        if screen is not None:
            screen.close_active_form()
            return
        workflow = self.current_workflow_module
        for method_name in ("close_form", "close_detalle"):
            method = getattr(workflow, method_name, None)
            if callable(method):
                method()

    def _reset_current_catalog_context(self) -> None:
        screen = self.current_catalog_screen
        if screen is not None:
            screen.reset_transient_state()
        if self._current_catalog_subpage:
            self._current_catalog_subpage = ""
            self.currentCatalogSubpageChanged.emit("")

    def _open_create_route_target(self, descriptor: ModuleDescriptor) -> bool:
        if descriptor.kind == "catalog":
            screen = self.current_catalog_screen
            return bool(screen and screen.open_create_form())
        workflow = self.current_workflow_module
        open_create = getattr(workflow, "open_create", None)
        if callable(open_create):
            return bool(open_create())
        self._set_error_message("Este modulo no soporta creacion desde rutas.")
        return False

    def _open_filtered_list_route_target(self, descriptor: ModuleDescriptor, filters: object) -> bool:
        self._close_active_subpage()
        screen = self.current_catalog_screen
        if descriptor.kind != "catalog":
            workflow = self.current_workflow_module
            screen = getattr(workflow, "list_screen", None)
        if screen is None:
            self._set_error_message("Este modulo no soporta listas filtradas.")
            return False
        if filters in (None, ""):
            screen.set_filters(())
            return True
        if not isinstance(filters, list):
            self._set_error_message("Se requiere una lista de filtros valida.")
            return False
        for payload in filters:
            if not screen.apply_filter_payload(payload):
                return False
        return True

    def _open_subpage_route_target(self, descriptor: ModuleDescriptor, subpage: str, context: object) -> bool:
        if not subpage:
            self._set_error_message("Se requiere una subpagina valida.")
            return False
        workflow = self.current_workflow_module
        open_subpage = getattr(workflow, "open_subpage", None)
        if callable(open_subpage):
            return bool(open_subpage(subpage, context if isinstance(context, dict) else {}))
        if descriptor.kind == "catalog" and descriptor.module_id == "cliente" and subpage == "client_debt":
            if not self._dashboard_view_model.load_client_debt():
                return False
            self._current_catalog_subpage = subpage
            self.currentCatalogSubpageChanged.emit(subpage)
            return True
        self._set_error_message("Este modulo no soporta subpaginas desde rutas.")
        return False

    def _open_create_with_context_route_target(self, descriptor: ModuleDescriptor, context: object) -> bool:
        if not self._open_create_route_target(descriptor):
            return False
        if descriptor.kind != "catalog":
            workflow = self.current_workflow_module
            form = getattr(workflow, "active_form", None)
        else:
            screen = self.current_catalog_screen
            form = None if screen is None else screen.form_host.active_form
        apply_context = getattr(form, "apply_navigation_context", None)
        if callable(apply_context):
            return bool(apply_context(context if isinstance(context, dict) else {}))
        return True

    def _open_record_form_route_target(self, descriptor: ModuleDescriptor, record_id: int) -> bool:
        if descriptor.kind == "catalog":
            screen = self.current_catalog_screen
            return bool(screen and screen.open_record_form(record_id))
        workflow = self.current_workflow_module
        open_record_form = getattr(workflow, "open_record_form", None)
        if callable(open_record_form):
            return bool(open_record_form(record_id))
        self._set_error_message("Este modulo no soporta formularios por ruta.")
        return False

    def _open_detail_route_target(self, descriptor: ModuleDescriptor, record_id: int) -> bool:
        workflow = self.current_workflow_module
        open_detail = getattr(workflow, "open_detalle", None)
        if callable(open_detail):
            open_detail(record_id)
            return True
        if descriptor.kind == "catalog":
            screen = self.current_catalog_screen
            return bool(screen and screen.open_record_detail(record_id))
        self._set_error_message("Este modulo no soporta detalle por ruta.")
        return False

    def _route_record_id(self, value: object) -> int | None:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            self._set_error_message("record_id es requerido para esta ruta.")
            return None
        if normalized < 0:
            self._set_error_message("record_id es requerido para esta ruta.")
            return None
        return normalized

    def _can_open_superuser_module(self) -> bool:
        return bool(self._runtime_session and self._runtime_session.is_authenticated and self._runtime_session.is_superuser)

    def _has_authenticated_session(self) -> bool:
        return bool(self._runtime_session and self._runtime_session.is_authenticated)

    @staticmethod
    def _superuser_required_message(module_id: str) -> str:
        title = "Reportes" if module_id == "reportes" else "Seguridad"
        return f"Se requiere usuario superuser para abrir {title}."

    def _module_access_denied_message(self, descriptor: ModuleDescriptor) -> str:
        if descriptor.access_policy == "superuser":
            return self._superuser_required_message(descriptor.module_id)
        if descriptor.access_policy == "authenticated":
            return f"Debes iniciar sesion para abrir {descriptor.title}."
        return "No tienes permiso para abrir este modulo."

    def _apply_authorization_permissions(self) -> None:
        if self._authorization is None:
            return
        for module_id, screen in self._catalog_screens.items():
            descriptor = self._module_by_id.get(module_id)
            resource = self._module_resource(descriptor) if descriptor is not None else screen.catalog_name
            screen.set_permissions(self._authorization.resource_permissions(resource))
        viaje = self._workflow_modules.get("viaje")
        if isinstance(viaje, ViajeWorkflowViewModel):
            viaje.set_permissions(self._authorization.resource_permissions("viaje"))
        circuito = self._workflow_modules.get("circuito")
        if isinstance(circuito, CircuitoWorkflowViewModel):
            circuito.set_permissions(
                can_edit_circuito=self._authorization.can("circuito", "edit"),
                can_create_return_trip=self._authorization.can("viaje", "create"),
            )

    def _module_resource(self, descriptor: ModuleDescriptor) -> str:
        return descriptor.catalog_name or descriptor.module_id

    def _can_read_module(self, descriptor: ModuleDescriptor) -> bool:
        if descriptor.access_policy == "superuser":
            return self._can_open_superuser_module()
        if descriptor.access_policy == "authenticated":
            return self._has_authenticated_session()
        if self._authorization is None:
            return True
        return self._authorization.can(self._module_resource(descriptor), "read")

    @staticmethod
    def _is_dashboard_module(descriptor: ModuleDescriptor) -> bool:
        return descriptor.module_id in SPECIALIZED_DASHBOARD_MODULE_IDS

    @staticmethod
    def _is_sidebar_module(descriptor: ModuleDescriptor) -> bool:
        return descriptor.module_id not in SPECIALIZED_DASHBOARD_MODULE_IDS

    def _visible_module_ids(self) -> list[str]:
        return [descriptor.module_id for descriptor in self._module_definitions if self._can_read_module(descriptor)]

    def _ensure_current_module_allowed(self) -> bool:
        visible_ids = self._visible_module_ids()
        if visible_ids and self._current_module_id in visible_ids:
            self._set_empty_state_message("")
            return True
        current_screen = self.current_catalog_screen if self._current_module_id else None
        if current_screen is not None:
            current_screen.close_active_form()
        self._current_module_id = visible_ids[0] if visible_ids else ""
        self._set_empty_state_message("" if visible_ids else "No hay modulos disponibles para este usuario.")
        return bool(self._current_module_id)

    def _observe_current_catalog_screen(self) -> None:
        next_screen = self.current_catalog_screen
        if next_screen is self._observed_catalog_screen:
            self._sync_current_catalog_state()
            return
        if self._observed_catalog_screen is not None:
            self._disconnect_catalog_screen(self._observed_catalog_screen)
        self._observed_catalog_screen = next_screen
        if next_screen is not None:
            next_screen.busyChanged.connect(self._handle_current_screen_busy_changed)
            next_screen.errorMessageChanged.connect(self._handle_current_screen_error_changed)
        self._sync_current_catalog_state()

    def _disconnect_catalog_screen(self, screen: CatalogScreenViewModel) -> None:
        for signal, slot in (
            (screen.busyChanged, self._handle_current_screen_busy_changed),
            (screen.errorMessageChanged, self._handle_current_screen_error_changed),
        ):
            try:
                signal.disconnect(slot)
            except TypeError:
                pass

    def _sync_current_catalog_state(self) -> None:
        screen = self._observed_catalog_screen
        if screen is None:
            self.is_busy = False
            self._set_error_message("")
            return
        self.is_busy = screen.is_busy
        self._set_error_message(screen.error_message)

    def _handle_current_screen_busy_changed(self, busy: bool) -> None:
        self.is_busy = bool(busy)

    def _handle_current_screen_error_changed(self, message: str) -> None:
        self._set_error_message(message)

    @Slot()
    def dispose(self) -> None:
        if getattr(self, "_disposed", False):
            return
        if self._observed_catalog_screen is not None:
            self._disconnect_catalog_screen(self._observed_catalog_screen)
            self._observed_catalog_screen = None
        for screen in self._catalog_screens.values():
            screen.dispose()
            screen.deleteLater()
        for workflow in self._workflow_modules.values():
            dispose = getattr(workflow, "dispose", None)
            if callable(dispose):
                dispose()
            delete_later = getattr(workflow, "deleteLater", None)
            if callable(delete_later):
                delete_later()
        self._dashboard_view_model.dispose()
        self._dashboard_view_model.deleteLater()
        self._catalog_screens.clear()
        self._workflow_modules.clear()
        super().dispose()


def build_default_app_shell(
    query_service: ModeloCatalogQueryService,
    catalog_service: ModeloCatalogService,
    reference_lookup_service: ReferenceLookupService | None = None,
    *,
    workflow_service: ModeloWorkflowService | None = None,
    auth_service: AuthModuleService | None = None,
    rbac_service: RbacPermissionService | None = None,
    runtime_session: RuntimeSessionViewModel | None = None,
    authorization_service: PresentationAuthorizationService | None = None,
    table_preferences_store: CatalogTablePreferencesStore | None = None,
    report_catalog_service: ReportCatalogService | None = None,
    report_generation_service: ReportGenerationService | None = None,
    report_export_service: ReportExportService | None = None,
    dashboard_service: DashboardService | None = None,
) -> AppShellViewModel:
    resolved_table_preferences_store = table_preferences_store or InMemoryCatalogTablePreferencesStore()
    registry = _build_form_registry(
        catalog_service,
        workflow_service=workflow_service,
        reference_lookup_service=reference_lookup_service,
        table_preferences_store=resolved_table_preferences_store,
    )
    catalog_screens: dict[str, CatalogScreenViewModel] = {}
    workflow_modules: dict[str, Any] = {}

    for descriptor in APP_MODULES:
        if descriptor.kind == "catalog":
            catalog_name = descriptor.catalog_name or descriptor.module_id
            preferred_form_id = "generic-catalog"
            screen_kwargs: dict[str, Any] = {}
            if workflow_service is not None and catalog_name == "factura":
                preferred_form_id = "factura-workflow"
                screen_kwargs["delete_handler"] = workflow_service.factura.delete
                screen_kwargs["export_handler"] = workflow_service.factura.export_excel
            elif workflow_service is not None and catalog_name == "recibo":
                preferred_form_id = "recibo-workflow"
                screen_kwargs["delete_handler"] = workflow_service.recibo.delete
            schema = query_service.get_schema(catalog_name)
            view_definition = CatalogViewDefinition.from_schema(
                schema,
                form_id=preferred_form_id,
            )
            if authorization_service is not None:
                view_definition = replace(
                    view_definition,
                    permissions=authorization_service.resource_permissions(catalog_name),
                )
            view_definition = apply_catalog_column_overrides(view_definition)
            form_host = FormHostViewModel(registry)
            if preferred_form_id == "factura-workflow":
                form_host.set_navigation_defaults(
                    presentation_mode="page",
                    navigation_title=descriptor.title,
                )
            elif preferred_form_id == "recibo-workflow":
                form_host.set_navigation_defaults(
                    presentation_mode="page",
                    navigation_title=descriptor.title,
                )
            catalog_screens[descriptor.module_id] = CatalogScreenViewModel(
                view_definition=view_definition,
                query_service=query_service,
                catalog_service=catalog_service,
                form_host=form_host,
                table_preferences_store=resolved_table_preferences_store,
                **screen_kwargs,
            )
            continue
        if descriptor.module_id == "viaje" and workflow_service is not None:
            viaje_schema = query_service.get_schema("viaje")
            viaje_view_definition = replace(
                CatalogViewDefinition.from_schema(
                    viaje_schema,
                    form_id="viaje-workflow",
                    page_size=12,
                ),
                permissions=authorization_service.resource_permissions("viaje")
                if authorization_service is not None
                else {
                    **dict(viaje_schema.permissions),
                    "delete": True,
                },
            )
            viaje_view_definition = apply_catalog_column_overrides(viaje_view_definition)
            viaje_form_host = FormHostViewModel(registry)
            viaje_form_host.set_navigation_defaults(
                presentation_mode="page",
                navigation_title=descriptor.title,
            )
            viaje_list_screen = CatalogScreenViewModel(
                view_definition=viaje_view_definition,
                query_service=query_service,
                catalog_service=catalog_service,
                form_host=viaje_form_host,
                table_preferences_store=resolved_table_preferences_store,
                delete_handler=workflow_service.viaje.delete,
            )
            workflow_modules[descriptor.module_id] = ViajeWorkflowViewModel(
                WorkflowDescriptor(
                    module_id=descriptor.module_id,
                    title=descriptor.title,
                    domain_title=descriptor.domain_title,
                    summary=descriptor.summary,
                    qml_component=descriptor.qml_component or "ViajeWorkflowPage.qml",
                ),
                list_screen=viaje_list_screen,
                workflow_service=workflow_service,
            )
            continue
        if descriptor.module_id == "circuito" and workflow_service is not None:
            circuito_schema = query_service.get_schema("circuito")
            circuito_view_definition = replace(
                CatalogViewDefinition.from_schema(
                    circuito_schema,
                    form_id="circuito-basic",
                    page_size=12,
                ),
                permissions={
                    **(
                        authorization_service.resource_permissions("circuito")
                        if authorization_service is not None
                        else dict(circuito_schema.permissions)
                    ),
                    "create": False,
                    "delete": False,
                },
            )
            circuito_view_definition = apply_catalog_column_overrides(circuito_view_definition)
            circuito_form_host = FormHostViewModel(registry)
            circuito_form_host.set_navigation_defaults(
                presentation_mode="page",
                navigation_title=descriptor.title,
            )
            circuito_list_screen = CatalogScreenViewModel(
                view_definition=circuito_view_definition,
                query_service=query_service,
                catalog_service=catalog_service,
                form_host=circuito_form_host,
                table_preferences_store=resolved_table_preferences_store,
            )
            workflow_modules[descriptor.module_id] = CircuitoWorkflowViewModel(
                WorkflowDescriptor(
                    module_id=descriptor.module_id,
                    title=descriptor.title,
                    domain_title=descriptor.domain_title,
                    summary=descriptor.summary,
                    qml_component=descriptor.qml_component or "CircuitoWorkflowPage.qml",
                ),
                list_screen=circuito_list_screen,
                workflow_service=workflow_service,
                reference_lookup_service=reference_lookup_service,
                can_create_return_trip=authorization_service.can("viaje", "create")
                if authorization_service is not None
                else True,
            )
            continue
        if descriptor.module_id == "seguridad" and auth_service is not None and rbac_service is not None and runtime_session is not None:
            workflow_modules[descriptor.module_id] = SecurityAdminViewModel(
                auth_service=auth_service,
                rbac_service=rbac_service,
                runtime_session=runtime_session,
            )
            continue
        if (
            descriptor.module_id == "reportes"
            and report_catalog_service is not None
            and report_generation_service is not None
            and report_export_service is not None
        ):
            workflow_modules[descriptor.module_id] = ReportsModuleViewModel(
                catalog_service=report_catalog_service,
                generation_service=report_generation_service,
                export_service=report_export_service,
            )
            continue
        workflow_modules[descriptor.module_id] = WorkflowPlaceholderViewModel(descriptor)

    return AppShellViewModel(
        module_definitions=APP_MODULES,
        catalog_screens=catalog_screens,
        workflow_modules=workflow_modules,
        initial_module_id=INITIAL_MODULE_ID,
        runtime_session=runtime_session,
        authorization_service=authorization_service,
        dashboard_view_model=DashboardViewModel(
            dashboard_service or _EmptyDashboardService(),
            authorization_service=authorization_service,
        ),
    )


class _EmptyDashboardService:
    def get_kpis(self) -> dict[str, int]:
        return {}

    def get_client_debt_rows(self) -> list[dict[str, Any]]:
        return []


def _build_module_groups(module_definitions: tuple[ModuleDescriptor, ...]) -> tuple[ModuleGroupDescriptor, ...]:
    grouped: list[ModuleGroupDescriptor] = []
    current_domain_id = ""
    current_title = ""
    current_modules: list[ModuleDescriptor] = []

    for descriptor in module_definitions:
        if descriptor.domain_id != current_domain_id:
            if current_modules:
                grouped.append(
                    ModuleGroupDescriptor(
                        domain_id=current_domain_id,
                        title=current_title,
                        modules=tuple(current_modules),
                    )
                )
            current_domain_id = descriptor.domain_id
            current_title = descriptor.domain_title
            current_modules = [descriptor]
            continue
        current_modules.append(descriptor)

    if current_modules:
        grouped.append(
            ModuleGroupDescriptor(
                domain_id=current_domain_id,
                title=current_title,
                modules=tuple(current_modules),
            )
        )

    return tuple(grouped)
