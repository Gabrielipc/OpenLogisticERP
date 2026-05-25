from __future__ import annotations

from openlogistic_erp.infrastructure.persistence.session_identity import clear_authenticated_user_id
from openlogistic_erp.domain.modelo.catalog_queries import CatalogFilter, CatalogFilterOperator
from openlogistic_erp.presentation.app_shell import AppShellViewModel, ModuleDescriptor, WorkflowPlaceholderViewModel
from openlogistic_erp.presentation.catalog import (
    BaseFormViewModel,
    CatalogScreenViewModel,
    CatalogViewDefinition,
    FormDefinition,
    FormHostViewModel,
    FormRegistry,
)
from openlogistic_erp.presentation.viewmodels import RuntimeSessionViewModel
from openlogistic_erp.presentation.workflows.circuito import CircuitoWorkflowViewModel
from openlogistic_erp.presentation.workflows.common import WorkflowDescriptor, WorkflowModuleViewModel
from openlogistic_erp.presentation.workflows.viaje import ViajeWorkflowViewModel


class StubAuthorization:
    def __init__(self, grants: set[tuple[str, str]]) -> None:
        self.grants = set(grants)

    def can(self, resource: str, action: str) -> bool:
        return (str(resource), str(action)) in self.grants

    def resource_permissions(self, resource: str) -> dict[str, bool]:
        return {
            "read": self.can(resource, "read"),
            "create": self.can(resource, "create"),
            "edit": self.can(resource, "edit"),
            "delete": self.can(resource, "delete"),
        }


class StubRuntimeSession:
    def __init__(self, *, is_authenticated: bool = True, is_superuser: bool = False) -> None:
        self.is_authenticated = is_authenticated
        self.is_superuser = is_superuser


class StubFormViewModel(BaseFormViewModel):
    def load(self, record_id: int | None) -> None:
        self._set_record_id(record_id)
        self.loaded.emit({})

    def reset(self) -> None:
        self._set_record_id(None)

    def submit(self):
        return {"id": self.record_id or 1}


def _form_registry() -> FormRegistry:
    return FormRegistry(
        (
            FormDefinition(
                form_id="stub",
                qml_component="StubForm.qml",
                view_model_factory=lambda catalog_name, mode, context: StubFormViewModel(catalog_name),
            ),
        )
    )


def _descriptor(
    module_id: str,
    *,
    kind: str = "workflow",
    catalog_name: str | None = None,
    access_policy: str = "permission",
) -> ModuleDescriptor:
    return ModuleDescriptor(
        module_id=module_id,
        title=module_id.title(),
        domain_id="domain",
        domain_title="Domain",
        kind=kind,
        monogram=module_id[:2].upper(),
        icon_source=f"qrc:/icons/modules/{module_id}.svg",
        summary="",
        access_policy=access_policy,
        catalog_name=catalog_name,
        qml_component="WorkflowPlaceholderPage.qml",
    )


def test_app_shell_starts_on_dashboard_view():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="cliente"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    shell = AppShellViewModel(
        module_definitions=(cliente,),
        catalog_screens={"cliente": screen},
        workflow_modules={},
    )

    assert shell.current_view == "dashboard"
    assert shell.current_module_id == "cliente"


def test_app_shell_logo_home_returns_from_module_to_dashboard():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    viaje = _descriptor("viaje")
    workflow = WorkflowPlaceholderViewModel(viaje)
    shell = AppShellViewModel(
        module_definitions=(cliente, viaje),
        catalog_screens={},
        workflow_modules={"viaje": workflow},
        authorization_service=StubAuthorization({("cliente", "read"), ("viaje", "read")}),
    )

    shell.select_module("viaje")
    assert shell.current_view == "module"

    shell.go_home()

    assert shell.current_view == "dashboard"
    assert shell.current_module_id == "viaje"


def test_app_shell_sidebar_groups_exclude_specialized_modules_and_dashboard_exposes_them_for_superuser():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    reportes = _descriptor("reportes", access_policy="superuser")
    seguridad = _descriptor("seguridad", access_policy="superuser")
    shell = AppShellViewModel(
        module_definitions=(cliente, reportes, seguridad),
        catalog_screens={},
        workflow_modules={
            "reportes": WorkflowPlaceholderViewModel(reportes),
            "seguridad": WorkflowPlaceholderViewModel(seguridad),
        },
        authorization_service=StubAuthorization({("cliente", "read"), ("reportes", "read"), ("seguridad", "read")}),
        runtime_session=StubRuntimeSession(is_superuser=True),
    )

    sidebar_ids = [module["module_id"] for group in shell.module_groups for module in group["modules"]]
    dashboard_ids = [module["module_id"] for module in shell.dashboard_modules]

    assert sidebar_ids == ["cliente"]
    assert dashboard_ids == ["reportes", "seguridad"]
    assert shell.module_groups[0]["modules"][0]["iconSource"] == "qrc:/icons/modules/cliente.svg"
    assert shell.dashboard_modules[0]["iconSource"] == "qrc:/icons/modules/reportes.svg"


def test_app_shell_navigate_to_create_form_selects_module_and_opens_form():
    factura = _descriptor("factura", kind="catalog", catalog_name="factura")
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="factura"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    shell = AppShellViewModel(
        module_definitions=(factura,),
        catalog_screens={"factura": screen},
        workflow_modules={},
        initial_module_id="factura",
        authorization_service=StubAuthorization({("factura", "read"), ("factura", "create")}),
    )

    assert shell.navigate_to({"module_id": "factura", "target": "create_form"}) is True

    assert shell.current_view == "module"
    assert shell.current_module_id == "factura"
    assert screen.form_host.is_open is True
    assert screen.form_host.active_form is not None
    assert screen.form_host.active_form.mode == "create"


def test_app_shell_navigate_to_filtered_list_applies_filter_payload():
    camion = _descriptor("camion", kind="catalog", catalog_name="camion")
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="camion"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    shell = AppShellViewModel(
        module_definitions=(camion,),
        catalog_screens={"camion": screen},
        workflow_modules={},
        initial_module_id="camion",
        authorization_service=StubAuthorization({("camion", "read")}),
    )
    applied_payloads = []
    screen.apply_filter_payload = lambda payload: applied_payloads.append(payload) or True  # type: ignore[method-assign]

    assert shell.navigate_to(
        {
            "module_id": "camion",
            "target": "filtered_list",
            "filters": [{"field": "estado", "operator": "eq", "value": "ACTIVO"}],
        }
    ) is True

    assert applied_payloads == [{"field": "estado", "operator": "eq", "value": "ACTIVO"}]


def test_app_shell_navigate_to_subpage_delegates_to_workflow():
    class StubWorkflow(WorkflowPlaceholderViewModel):
        def __init__(self, descriptor):
            super().__init__(descriptor)
            self.last_subpage = None
            self.last_context = None

        def open_subpage(self, subpage, context=None):
            self.last_subpage = subpage
            self.last_context = context
            return True

    viaje = _descriptor("viaje")
    workflow = StubWorkflow(viaje)
    shell = AppShellViewModel(
        module_definitions=(viaje,),
        catalog_screens={},
        workflow_modules={"viaje": workflow},
        initial_module_id="viaje",
        authorization_service=StubAuthorization({("viaje", "read")}),
    )

    assert shell.navigate_to(
        {
            "module_id": "viaje",
            "target": "subpage",
            "subpage": "unbilled_trips",
            "subpage_context": {"mode": "pending"},
        }
    ) is True
    assert workflow.last_subpage == "unbilled_trips"
    assert workflow.last_context == {"mode": "pending"}


def test_app_shell_navigate_to_client_debt_subpage_uses_dashboard_view_model_without_priority_mode():
    class StubDashboardService:
        def get_kpis(self):
            return {}

        def get_client_debt_rows(self):
            return [{"cliente_id": 1}]

    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="cliente"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    from openlogistic_erp.presentation.dashboard import DashboardViewModel

    shell = AppShellViewModel(
        module_definitions=(cliente,),
        catalog_screens={"cliente": screen},
        workflow_modules={},
        initial_module_id="cliente",
        authorization_service=StubAuthorization({("cliente", "read")}),
        dashboard_view_model=DashboardViewModel(StubDashboardService()),
    )

    assert shell.navigate_to(
        {
            "module_id": "cliente",
            "target": "subpage",
            "subpage": "client_debt",
        }
    ) is True
    assert shell.current_catalog_subpage == "client_debt"
    assert shell.dashboard_view_model.clientDebtRows == [{"cliente_id": 1}]


def test_app_shell_clears_client_debt_subpage_when_navigating_to_another_catalog():
    class StubDashboardService:
        def get_kpis(self):
            return {}

        def get_client_debt_rows(self):
            return [{"cliente_id": 1}]

    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    recibo = _descriptor("recibo", kind="catalog", catalog_name="recibo")
    cliente_screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="cliente"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    recibo_screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="recibo"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    from openlogistic_erp.presentation.dashboard import DashboardViewModel

    shell = AppShellViewModel(
        module_definitions=(cliente, recibo),
        catalog_screens={"cliente": cliente_screen, "recibo": recibo_screen},
        workflow_modules={},
        initial_module_id="cliente",
        authorization_service=StubAuthorization({("cliente", "read"), ("recibo", "read"), ("recibo", "create")}),
        dashboard_view_model=DashboardViewModel(StubDashboardService()),
    )

    assert shell.navigate_to(
        {
            "module_id": "cliente",
            "target": "subpage",
            "subpage": "client_debt",
        }
    ) is True
    assert shell.current_catalog_subpage == "client_debt"

    assert shell.navigate_to({"module_id": "recibo", "target": "create_form"}) is True
    assert shell.current_module_id == "recibo"
    assert shell.current_catalog_subpage == ""
    assert recibo_screen.form_host.is_open is True


def test_app_shell_resets_catalog_transient_state_when_leaving_but_preserves_filters():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    viaje = _descriptor("viaje")
    workflow = WorkflowPlaceholderViewModel(viaje)
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="cliente"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    screen.load = lambda: 1  # type: ignore[method-assign]
    shell = AppShellViewModel(
        module_definitions=(cliente, viaje),
        catalog_screens={"cliente": screen},
        workflow_modules={"viaje": workflow},
        initial_module_id="cliente",
        authorization_service=StubAuthorization({("cliente", "read"), ("cliente", "create"), ("viaje", "read")}),
    )

    screen.set_filters((CatalogFilter("estado", CatalogFilterOperator.EQ, "ACTIVO"),))
    screen.apply_search("cliente demo")
    screen.set_page(3)
    screen.select_record(42)
    screen.open_create()

    shell.select_module("viaje")

    assert screen.form_host.is_open is False
    assert screen.search_term == ""
    assert screen.current_page == 0
    assert screen.selected_record_id is None
    assert [filter_state["field"] for filter_state in screen.active_filters] == ["estado"]


def test_app_shell_resets_catalog_transient_state_when_returning_home():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(catalog_name="cliente"),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(_form_registry()),
    )
    screen.load = lambda: 1  # type: ignore[method-assign]
    shell = AppShellViewModel(
        module_definitions=(cliente,),
        catalog_screens={"cliente": screen},
        workflow_modules={},
        initial_module_id="cliente",
        authorization_service=StubAuthorization({("cliente", "read"), ("cliente", "create")}),
    )
    shell.select_module("cliente")
    screen.open_create()
    screen.apply_search("cliente demo")

    shell.go_home()

    assert shell.current_view == "dashboard"
    assert screen.form_host.is_open is False
    assert screen.search_term == ""


def test_app_shell_navigate_to_rejects_hidden_module():
    factura = _descriptor("factura", kind="catalog", catalog_name="factura")
    shell = AppShellViewModel(
        module_definitions=(factura,),
        catalog_screens={},
        workflow_modules={},
        initial_module_id="factura",
        authorization_service=StubAuthorization(set()),
    )

    assert shell.navigate_to({"module_id": "factura", "target": "list"}) is False
    assert shell.current_view == "dashboard"
    assert shell.error_message == "No tienes permiso para abrir este modulo."


def test_app_shell_filters_modules_without_read_permission():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    viaje = _descriptor("viaje")
    workflow = WorkflowPlaceholderViewModel(viaje)
    shell = AppShellViewModel(
        module_definitions=(cliente, viaje),
        catalog_screens={},
        workflow_modules={"viaje": workflow},
        authorization_service=StubAuthorization({("viaje", "read")}),
    )

    groups = shell.module_groups

    assert shell.current_module_id == "viaje"
    assert shell.empty_state_message == ""
    assert [module["module_id"] for module in groups[0]["modules"]] == ["viaje"]


def test_app_shell_exposes_empty_state_when_user_has_no_read_permissions():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    shell = AppShellViewModel(
        module_definitions=(cliente,),
        catalog_screens={},
        workflow_modules={},
        authorization_service=StubAuthorization(set()),
    )

    assert shell.module_groups == []
    assert shell.current_module_id == ""
    assert shell.current_module == {}
    assert shell.current_catalog_screen is None
    assert shell.current_workflow_component == ""
    assert shell.empty_state_message == "No hay modulos disponibles para este usuario."


def test_app_shell_rejects_selecting_hidden_module():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    viaje = _descriptor("viaje")
    workflow = WorkflowPlaceholderViewModel(viaje)
    shell = AppShellViewModel(
        module_definitions=(cliente, viaje),
        catalog_screens={},
        workflow_modules={"viaje": workflow},
        authorization_service=StubAuthorization({("viaje", "read")}),
    )

    shell.select_module("cliente")

    assert shell.current_module_id == "viaje"
    assert shell.error_message == "No tienes permiso para abrir este modulo."


def test_app_shell_limits_reports_module_to_superusers_even_with_read_permission():
    cliente = _descriptor("cliente", kind="catalog", catalog_name="cliente")
    reportes = _descriptor("reportes", access_policy="superuser")
    reportes_workflow = WorkflowPlaceholderViewModel(reportes)
    shell = AppShellViewModel(
        module_definitions=(cliente, reportes),
        catalog_screens={},
        workflow_modules={"reportes": reportes_workflow},
        authorization_service=StubAuthorization({("cliente", "read"), ("reportes", "read")}),
        runtime_session=StubRuntimeSession(is_superuser=False),
    )

    shell.select_module("reportes")

    assert shell.current_module_id == "cliente"
    assert shell.error_message == "Se requiere usuario superuser para abrir Reportes."
    assert [module["module_id"] for module in shell.module_groups[0]["modules"]] == ["cliente"]


def test_app_shell_shows_reports_module_for_superusers():
    reportes = _descriptor("reportes", access_policy="superuser")
    reportes_workflow = WorkflowPlaceholderViewModel(reportes)
    shell = AppShellViewModel(
        module_definitions=(reportes,),
        catalog_screens={},
        workflow_modules={"reportes": reportes_workflow},
        initial_module_id="reportes",
        authorization_service=StubAuthorization({("reportes", "read")}),
        runtime_session=StubRuntimeSession(is_superuser=True),
    )

    assert shell.current_module_id == "reportes"
    assert shell.module_groups == []
    assert shell.dashboard_modules[0]["module_id"] == "reportes"


def test_app_shell_shows_authenticated_module_without_rbac_permission_for_authenticated_user():
    configuracion = _descriptor("configuracion", access_policy="authenticated")
    shell = AppShellViewModel(
        module_definitions=(configuracion,),
        catalog_screens={},
        workflow_modules={"configuracion": WorkflowPlaceholderViewModel(configuracion)},
        initial_module_id="configuracion",
        authorization_service=StubAuthorization(set()),
        runtime_session=StubRuntimeSession(is_authenticated=True, is_superuser=False),
    )

    assert shell.current_module_id == "configuracion"
    assert shell.module_groups[0]["modules"][0]["module_id"] == "configuracion"


def test_app_shell_hides_authenticated_module_without_authenticated_session():
    configuracion = _descriptor("configuracion", access_policy="authenticated")
    shell = AppShellViewModel(
        module_definitions=(configuracion,),
        catalog_screens={},
        workflow_modules={"configuracion": WorkflowPlaceholderViewModel(configuracion)},
        initial_module_id="configuracion",
        authorization_service=StubAuthorization(set()),
        runtime_session=StubRuntimeSession(is_authenticated=False, is_superuser=False),
    )

    assert shell.module_groups == []
    assert shell.current_module_id == ""


def test_app_shell_rejects_navigation_to_authenticated_module_without_session():
    configuracion = _descriptor("configuracion", access_policy="authenticated")
    shell = AppShellViewModel(
        module_definitions=(configuracion,),
        catalog_screens={},
        workflow_modules={"configuracion": WorkflowPlaceholderViewModel(configuracion)},
        initial_module_id="configuracion",
        authorization_service=StubAuthorization(set()),
        runtime_session=StubRuntimeSession(is_authenticated=False, is_superuser=False),
    )

    assert shell.navigate_to({"module_id": "configuracion", "target": "list"}) is False
    assert shell.error_message == "Debes iniciar sesion para abrir Configuracion."


def test_app_shell_exposes_coherent_workflow_source_for_specialized_modules():
    reportes = ModuleDescriptor(
        module_id="reportes",
        title="Reportes",
        domain_id="analitica",
        domain_title="Analitica",
        kind="workflow",
        monogram="RP",
        summary="",
        access_policy="superuser",
        qml_component="ReportsModulePage.qml",
    )
    seguridad = ModuleDescriptor(
        module_id="seguridad",
        title="Seguridad",
        domain_id="administracion",
        domain_title="Administracion",
        kind="workflow",
        monogram="SE",
        summary="",
        access_policy="superuser",
        qml_component="SecurityAdminPage.qml",
    )
    shell = AppShellViewModel(
        module_definitions=(reportes, seguridad),
        catalog_screens={},
        workflow_modules={
            "reportes": WorkflowModuleViewModel(
                WorkflowDescriptor(
                    module_id="reportes",
                    title="Reportes",
                    domain_title="Analitica",
                    summary="",
                    qml_component="ReportsModulePage.qml",
                )
            ),
            "seguridad": WorkflowModuleViewModel(
                WorkflowDescriptor(
                    module_id="seguridad",
                    title="Seguridad",
                    domain_title="Administracion",
                    summary="",
                    qml_component="SecurityAdminPage.qml",
                )
            ),
        },
        initial_module_id="reportes",
        authorization_service=StubAuthorization({("reportes", "read"), ("seguridad", "read")}),
        runtime_session=StubRuntimeSession(is_superuser=True),
    )

    shell.select_module("reportes")
    assert shell.current_workflow_source == "reports/ReportsModulePage.qml"

    shell.select_module("seguridad")
    assert shell.current_workflow_source == "workflows/seguridad/SecurityAdminPage.qml"


def test_app_shell_refreshes_superuser_modules_after_runtime_login(auth_service):
    username = "sidebar_superuser"
    password = "abc12345"
    auth_service.create_user(username=username, password=password, is_superuser=True)
    reportes = _descriptor("reportes", access_policy="superuser")
    seguridad = _descriptor("seguridad", access_policy="superuser")
    runtime = RuntimeSessionViewModel(auth_service)
    shell = AppShellViewModel(
        module_definitions=(reportes, seguridad),
        catalog_screens={},
        workflow_modules={
            "reportes": WorkflowPlaceholderViewModel(reportes),
            "seguridad": WorkflowPlaceholderViewModel(seguridad),
        },
        initial_module_id="reportes",
        runtime_session=runtime,
    )
    runtime.authenticatedChanged.connect(shell.handle_runtime_auth_changed)
    emitted_module_ids: list[list[str]] = []

    def capture_dashboard_modules() -> None:
        emitted_module_ids.append(
            [
                module["module_id"]
                for module in shell.dashboard_modules
            ]
        )

    shell.dashboardModulesChanged.connect(capture_dashboard_modules)

    try:
        runtime.login(username, password)

        assert emitted_module_ids
        assert "reportes" in emitted_module_ids[-1]
        assert "seguridad" in emitted_module_ids[-1]
    finally:
        runtime.logout()
        clear_authenticated_user_id()


def test_catalog_screen_rejects_direct_create_edit_delete_calls_without_permissions():
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="ruta",
            permissions={"create": False, "edit": False, "delete": False},
        ),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(FormRegistry(())),
    )

    assert screen.open_create() is None
    assert screen.error_message == "No tienes permiso para crear ruta"

    assert screen.open_edit(1) is None
    assert screen.error_message == "No tienes permiso para modificar ruta"

    assert screen.delete_record(1) is False
    assert screen.error_message == "No tienes permiso para eliminar ruta"


def test_catalog_screen_permissions_can_refresh_after_login():
    screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="ruta",
            permissions={"create": False, "edit": False, "delete": False},
        ),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(FormRegistry(())),
    )

    screen.set_permissions({"create": True, "edit": True, "delete": False})

    assert screen.can_create is True
    assert screen.can_edit is True
    assert screen.can_delete is False


def test_app_shell_refreshes_specialized_viaje_workflow_permissions_after_login():
    viaje = _descriptor("viaje")
    authorization = StubAuthorization({("viaje", "read")})
    list_screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="viaje",
            permissions={"create": False, "edit": False, "delete": False},
        ),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(FormRegistry(())),
    )
    workflow = ViajeWorkflowViewModel(
        WorkflowDescriptor(
            module_id="viaje",
            title="Viaje",
            domain_title="Domain",
            summary="",
            qml_component="ViajeWorkflowPage.qml",
        ),
        list_screen=list_screen,
        workflow_service=object(),
    )
    shell = AppShellViewModel(
        module_definitions=(viaje,),
        catalog_screens={},
        workflow_modules={"viaje": workflow},
        initial_module_id="viaje",
        authorization_service=authorization,
    )

    authorization.grants.update({("viaje", "create"), ("viaje", "edit"), ("viaje", "delete")})
    shell.activate_runtime_session()

    assert workflow.can_create_viaje is True
    assert workflow.can_edit_viaje is True
    assert workflow.list_screen.can_delete is True


def test_app_shell_refreshes_specialized_circuito_workflow_list_permissions_after_login():
    circuito = _descriptor("circuito")
    authorization = StubAuthorization({("circuito", "read")})
    list_screen = CatalogScreenViewModel(
        view_definition=CatalogViewDefinition(
            catalog_name="circuito",
            permissions={"create": False, "edit": False, "delete": False},
        ),
        query_service=object(),
        catalog_service=object(),
        form_host=FormHostViewModel(FormRegistry(())),
    )
    workflow = CircuitoWorkflowViewModel(
        WorkflowDescriptor(
            module_id="circuito",
            title="Circuito",
            domain_title="Domain",
            summary="",
            qml_component="CircuitoWorkflowPage.qml",
        ),
        list_screen=list_screen,
        workflow_service=object(),
    )
    shell = AppShellViewModel(
        module_definitions=(circuito,),
        catalog_screens={},
        workflow_modules={"circuito": workflow},
        initial_module_id="circuito",
        authorization_service=authorization,
    )

    authorization.grants.add(("circuito", "edit"))
    shell.activate_runtime_session()

    assert workflow.can_edit_circuito is True
    assert workflow.list_screen.can_create is False
    assert workflow.list_screen.can_delete is False
