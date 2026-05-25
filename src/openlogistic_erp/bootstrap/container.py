"""Bootstrap package for dependency wiring."""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ..application.auth import AuthModuleService, build_auth_module
from ..application.dashboard import DashboardService
from ..application.modelo.factories import build_modelo_module
from ..application.modelo.query_service import ModeloCatalogQueryService
from ..application.modelo.reference_service import ReferenceLookupService
from ..application.modelo.services import ModeloWorkflowService
from ..application.rbac import RbacPermissionService, build_rbac_module
from ..application.reports import (
    ReportCatalogService,
    ReportExportService,
    ReportGenerationService,
    build_default_report_definitions,
)
from ..domain.reports import ReportFormat
from ..infrastructure.persistence.database import build_postgres_connect_args
from ..infrastructure.persistence.modelo.context import ModeloDataContext
from ..infrastructure.persistence.modelo.repositories import (
    SqlAlchemyCatalogQueryRepository,
    SqlAlchemyModeloRepository,
    SqlAlchemyReferenceLookupRepository,
)
from ..infrastructure.persistence.reports import (
    CuentasPorCobrarAgingReportReader,
    EstadoCuentaClienteReportReader,
    FacturacionPorClienteReportReader,
    ReportOptionsReader,
    ViajesPorConductorReportReader,
)
from ..infrastructure.persistence.security.context import SecurityDataContext
from ..infrastructure.persistence.security.repositories import (
    SqlAlchemyAuthRepository,
    SqlAlchemyRbacRepository,
)
from ..infrastructure.reports.export import PdfReportExporter, XlsxReportExporter
from ..presentation import (
    PresentationAuthorizationService,
    RuntimeSessionViewModel,
    build_default_app_shell,
    register_qml_types,
)
from ..presentation.catalog.table_preferences import QSettingsCatalogTablePreferencesStore
from ..presentation.qt import QApplication, QQmlApplicationEngine, QSettings, QUrl
from ..ui.resources import register_qt_resources

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    env: str


class AppContainer:
    """Service locator and wiring root for the new architecture."""

    def __init__(self, config: AppConfig):
        self.config = config

    @classmethod
    def build_from_env(cls) -> AppContainer:
        load_dotenv()
        env = os.getenv("OPENLOGISTIC_ENV", "development").strip() or "development"
        db_url = os.getenv("OPENLOGISTIC_DATABASE_URL", "").strip()
        if not db_url:
            from ..shared.errors import MigrationError

            raise MigrationError("OPENLOGISTIC_DATABASE_URL is required for bootstrap")
        return cls(AppConfig(database_url=db_url, env=env))

    def create_app(self) -> ApplicationShell:
        connect_args = build_postgres_connect_args(self.config.env)

        security_context = SecurityDataContext(
            engine_url=self.config.database_url,
            engine_kwargs={"connect_args": connect_args},
        )
        auth_repo = SqlAlchemyAuthRepository(security_context.session_factory())
        rbac_repo = SqlAlchemyRbacRepository(security_context.session_factory())
        auth_service = build_auth_module(auth_repo)
        rbac_service = build_rbac_module(rbac_repo, rbac_repo)

        modelo_context = ModeloDataContext(
            engine_url=self.config.database_url,
            engine_kwargs={"connect_args": connect_args},
        )
        modelo_session_factory = modelo_context.session_factory()
        modelo_repo = SqlAlchemyModeloRepository(modelo_session_factory)
        reference_lookup_repo = SqlAlchemyReferenceLookupRepository(modelo_session_factory)
        modelo_query_repo = SqlAlchemyCatalogQueryRepository(
            modelo_session_factory,
            reference_lookup_repository=reference_lookup_repo,
        )
        reference_lookup_service = ReferenceLookupService(repository=reference_lookup_repo)
        modelo_service = build_modelo_module(
            repository=modelo_repo,
            session_factory=modelo_session_factory,
        )
        modelo_query_service = ModeloCatalogQueryService(
            query_repository=modelo_query_repo,
            reference_lookup_service=reference_lookup_service,
        )
        report_options_reader = ReportOptionsReader(modelo_session_factory)
        report_definitions = build_default_report_definitions()
        report_catalog_service = ReportCatalogService(
            report_definitions,
            option_provider=report_options_reader,
        )
        report_generation_service = ReportGenerationService(
            report_definitions,
            readers={
                "viajes_por_conductor": ViajesPorConductorReportReader(modelo_session_factory),
                "cuentas_por_cobrar_aging": CuentasPorCobrarAgingReportReader(modelo_session_factory),
                "facturacion_por_cliente": FacturacionPorClienteReportReader(modelo_session_factory),
                "estado_cuenta_cliente": EstadoCuentaClienteReportReader(modelo_session_factory),
            },
        )
        report_export_service = ReportExportService(
            {
                ReportFormat.PDF: PdfReportExporter(),
                ReportFormat.XLSX: XlsxReportExporter(),
            }
        )
        dashboard_service = DashboardService(modelo_session_factory)

        return ApplicationShell(
            self.config,
            auth_service=auth_service,
            rbac_service=rbac_service,
            modelo_service=modelo_service,
            modelo_query_service=modelo_query_service,
            reference_lookup_service=reference_lookup_service,
            report_catalog_service=report_catalog_service,
            report_generation_service=report_generation_service,
            report_export_service=report_export_service,
            dashboard_service=dashboard_service,
        )


class ApplicationShell:
    """Minimal app entry shell used by the script boundary."""

    def __init__(
        self,
        config: AppConfig,
        auth_service: AuthModuleService,
        rbac_service: RbacPermissionService,
        modelo_service: ModeloWorkflowService,
        modelo_query_service: ModeloCatalogQueryService,
        reference_lookup_service: ReferenceLookupService,
        report_catalog_service: ReportCatalogService | None = None,
        report_generation_service: ReportGenerationService | None = None,
        report_export_service: ReportExportService | None = None,
        dashboard_service: DashboardService | None = None,
    ):
        self.config = config
        self.auth_service = auth_service
        self.rbac_service = rbac_service
        self.modelo_service = modelo_service
        self.modelo_query_service = modelo_query_service
        self.reference_lookup_service = reference_lookup_service
        self.report_catalog_service = report_catalog_service
        self.report_generation_service = report_generation_service
        self.report_export_service = report_export_service
        self.dashboard_service = dashboard_service
        self._app: QApplication | None = None
        self._engine: QQmlApplicationEngine | None = None
        self._app_shell = None

    def run(self) -> int:
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
        os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_THEME", "Light")
        os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_VARIANT", "Normal")
        os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_ACCENT", "Blue")

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setOrganizationName("OpenLogistic")
        app.setApplicationName("OpenLogisticERP")
        app.lastWindowClosed.connect(self._on_last_window_closed)
        app.aboutToQuit.connect(self._on_about_to_quit)

        authorization_service = PresentationAuthorizationService(self.rbac_service)
        runtime_session = RuntimeSessionViewModel(self.auth_service, authorization_service=authorization_service)
        app_shell = build_default_app_shell(
            query_service=self.modelo_query_service,
            catalog_service=self.modelo_service.catalog,
            workflow_service=self.modelo_service,
            table_preferences_store=QSettingsCatalogTablePreferencesStore(QSettings()),
            reference_lookup_service=self.reference_lookup_service,
            report_catalog_service=self.report_catalog_service,
            report_generation_service=self.report_generation_service,
            report_export_service=self.report_export_service,
            dashboard_service=self.dashboard_service,
            auth_service=self.auth_service,
            rbac_service=self.rbac_service,
            runtime_session=runtime_session,
            authorization_service=authorization_service,
        )
        runtime_session.authenticatedChanged.connect(app_shell.handle_runtime_auth_changed)

        engine = QQmlApplicationEngine()
        qml_path = Path(__file__).resolve().parents[1] / "ui" / "qml" / "Main.qml"
        register_qt_resources()
        register_qml_types()
        engine.addImportPath(str(qml_path.parent))
        engine.warnings.connect(self._log_qml_warnings)
        engine.setInitialProperties(
            {
                "appShellViewModel": app_shell,
                "runtimeSessionViewModel": runtime_session,
                "launchVisible": True,
            }
        )
        logger.info("Loading QML shell from %s", qml_path)

        try:
            engine.load(QUrl.fromLocalFile(str(qml_path)))
        except Exception:
            logger.exception("Application shell failed while loading Main.qml")
            return 1

        if not engine.rootObjects():
            logger.error("QML engine loaded no root objects for %s", qml_path)
            return 1

        for root in engine.rootObjects():
            try:
                root.setProperty("launchVisible", True)
            except Exception:
                logger.debug("Root object does not expose launchVisible", exc_info=True)
            show = getattr(root, "show", None)
            if callable(show):
                show()
            is_visible = getattr(root, "isVisible", None)
            logger.info(
                "Root object loaded: type=%s visibleProperty=%s isVisible=%s title=%s",
                type(root).__name__,
                root.property("visible"),
                is_visible() if callable(is_visible) else None,
                root.property("title"),
            )

        self._app = app
        self._engine = engine
        self._app_shell = app_shell
        return app.exec()

    @staticmethod
    def _log_qml_warnings(warnings: list[object]) -> None:
        for warning in warnings:
            logger.error("QML warning: %s", warning)

    @staticmethod
    def _on_last_window_closed() -> None:
        logger.warning("Qt emitted lastWindowClosed")

    @staticmethod
    def _on_about_to_quit() -> None:
        logger.warning("Qt emitted aboutToQuit")
