from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QResource, qInstallMessageHandler
from PySide6.QtQml import QQmlComponent, QQmlContext

import openlogistic_erp.presentation.qml_registry as qml_registry
from openlogistic_erp.application.modelo.query_service import ModeloCatalogQueryService
from openlogistic_erp.application.reports import (
    ReportCatalogService,
    ReportExportService,
    ReportGenerationService,
    build_default_report_definitions,
)
from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyCatalogQueryRepository
import openlogistic_erp.presentation.app_shell as app_shell_module
from openlogistic_erp.presentation import (
    RuntimeSessionViewModel,
    SecurityAdminViewModel,
    ViajeFormViewModel,
    build_default_app_shell,
)
from openlogistic_erp.presentation.catalog import (
    FormLayoutDefinition,
    FormLayoutFieldItem,
    FormLayoutSectionItem,
    GenericCatalogFormViewModel,
    GenericFormFieldDefinition,
)
from openlogistic_erp.presentation.dashboard import DashboardViewModel
from openlogistic_erp.presentation.app_shell import ModuleDescriptor
from openlogistic_erp.presentation.qml_typegen import generate_qmltypes, main, run_qmllint
from openlogistic_erp.presentation.qt import QCoreApplication, QObject, QQmlApplicationEngine, QUrl, qmlTypeId
from openlogistic_erp.presentation.reports import ReportTableModel, ReportsModuleViewModel
from openlogistic_erp.presentation.workflows.viaje import ViajeWorkflowViewModel
from tests.builders.modelo_seed import build_viaje_export_payload, seed_viaje_dependencies
from tests.integration.catalog_test_support import run_action_and_wait_for_applied_load, run_action_and_wait_for_request


WINDOWS_LIVE_QML_SKIP = pytest.mark.skipif(
    os.name == "nt",
    reason="PySide6/Qt intermittently aborts the Windows pytest process when live QML is mounted in-process.",
)


def _flush_qt_events(*, passes: int = 3) -> None:
    for _ in range(max(1, int(passes))):
        QCoreApplication.sendPostedEvents(None, 0)
        QCoreApplication.processEvents()


def _dispose_qml_engine(engine: QQmlApplicationEngine) -> None:
    roots = list(engine.rootObjects())
    for root in roots:
        closer = getattr(root, "close", None)
        if callable(closer):
            closer()

    _flush_qt_events()

    collector = getattr(engine, "collectGarbage", None)
    if callable(collector):
        collector()

    for root in roots:
        delete_later = getattr(root, "deleteLater", None)
        if callable(delete_later):
            delete_later()

    engine.clearComponentCache()
    engine.deleteLater()
    _flush_qt_events(passes=5)


def _qml_component_path(qml_name: str) -> Path:
    paths = {
        "FacturaWorkflowForm.qml": Path("workflows") / "factura" / qml_name,
        "GenericCatalogForm.qml": Path("shared") / "forms" / qml_name,
        "DashboardPage.qml": Path(qml_name),
        "ReciboWorkflowForm.qml": Path("workflows") / "recibo" / qml_name,
        "SidebarNav.qml": Path("shell") / qml_name,
        "SecurityAdminPage.qml": Path("workflows") / "seguridad" / qml_name,
        "CircuitoWorkflowPage.qml": Path("workflows") / "circuito" / qml_name,
        "CircuitoDetailPage.qml": Path("workflows") / "circuito" / "detail" / qml_name,
        "ViajeDetailPage.qml": Path("workflows") / "viaje" / "detail" / qml_name,
        "ViajeWorkflowForm.qml": Path("workflows") / "viaje" / qml_name,
        "ViajeWorkflowPage.qml": Path("workflows") / "viaje" / qml_name,
        "WorkflowPlaceholderPage.qml": Path("workflows") / "common" / qml_name,
    }
    return paths[qml_name]


def test_register_qml_types_registers_runtime_types_once(monkeypatch):
    monkeypatch.setattr(qml_registry, "_REGISTERED", False)

    qml_registry.register_qml_types()
    qml_registry.register_qml_types()

    for _, qml_name in qml_registry.QML_NAMED_TYPES:
        type_id = qmlTypeId(
            qml_registry.QML_MODULE_URI,
            qml_registry.QML_MODULE_MAJOR_VERSION,
            qml_registry.QML_MODULE_MINOR_VERSION,
            qml_name,
        )
        assert type_id >= 0, f"{qml_name} no quedo registrado en runtime"


def test_qml_registry_includes_report_view_models():
    assert (ReportsModuleViewModel, "ReportsModuleViewModel") in qml_registry.QML_NAMED_TYPES
    assert (ReportTableModel, "ReportTableModel") in qml_registry.QML_NAMED_TYPES


def test_qml_registry_includes_dashboard_view_model():
    assert (DashboardViewModel, "DashboardViewModel") in qml_registry.QML_NAMED_TYPES


def test_build_default_app_shell_exposes_dashboard_view_model(session_factory, modelo_workflow):
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))

    app_shell = build_default_app_shell(query_service, modelo_workflow.catalog)

    try:
        assert isinstance(app_shell.dashboard_view_model, DashboardViewModel)
    finally:
        app_shell.dispose()


def test_build_default_app_shell_wires_reports_module_when_services_available(monkeypatch):
    descriptor = ModuleDescriptor(
        module_id="reportes",
        title="Reportes",
        domain_id="analitica",
        domain_title="Analitica",
        kind="workflow",
        monogram="RP",
        summary="Reportes unificados.",
        qml_component="ReportsModulePage.qml",
    )
    monkeypatch.setattr(app_shell_module, "APP_MODULES", (descriptor,))
    monkeypatch.setattr(app_shell_module, "INITIAL_MODULE_ID", "reportes")
    definitions = build_default_report_definitions()

    app_shell = build_default_app_shell(
        query_service=object(),
        catalog_service=object(),
        runtime_session=type("RuntimeSessionStub", (), {"is_authenticated": True, "is_superuser": True})(),
        report_catalog_service=ReportCatalogService(definitions),
        report_generation_service=ReportGenerationService(definitions, {}),
        report_export_service=ReportExportService({}),
    )

    try:
        module_view_model = app_shell.current_workflow_module

        assert isinstance(module_view_model, ReportsModuleViewModel)
        assert app_shell.current_workflow_component == "ReportsModulePage.qml"
        assert app_shell.current_module["domain_id"] == "analitica"
    finally:
        app_shell.dispose()


def test_qml_surface_does_not_hide_navigable_types_with_legacy_erasure():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    qml_files = (
        qml_root / "Main.qml",
        qml_root / "catalog" / "CatalogScreenPage.qml",
        qml_root / "DashboardPage.qml",
        qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml",
        qml_root / "shared" / "forms" / "GenericCatalogForm.qml",
        qml_root / "workflows" / "recibo" / "ReciboWorkflowForm.qml",
        qml_root / "workflows" / "seguridad" / "SecurityAdminPage.qml",
        qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml",
        qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml",
        qml_root / "workflows" / "viaje" / "ViajeWorkflowForm.qml",
        qml_root / "workflows" / "common" / "WorkflowPlaceholderPage.qml",
    )

    disallowed_snippets = (
        "required property QtObject appShellViewModel",
        "required property QtObject workbenchViewModel",
        "required property QtObject screenViewModel",
        "required property QtObject moduleViewModel",
        "required property QtObject formViewModel",
        "readonly property var formHost",
        "required property BaseFormViewModel formViewModel",
    )

    for qml_file in qml_files:
        source = qml_file.read_text(encoding="utf-8")
        for snippet in disallowed_snippets:
            assert snippet not in source, f"{qml_file.name} sigue usando {snippet!r}"


def test_qml_scroll_surfaces_use_shared_wheel_tuning_hooks():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    catalog_table = (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8")

    for qml_name in (
        "DashboardPage.qml",
        "FacturaWorkflowForm.qml",
        "GenericCatalogForm.qml",
        "ReciboWorkflowForm.qml",
        "SidebarNav.qml",
        "SecurityAdminPage.qml",
        "CircuitoWorkflowPage.qml",
        "CircuitoDetailPage.qml",
        "ViajeDetailPage.qml",
        "ViajeWorkflowForm.qml",
        "WorkflowPlaceholderPage.qml",
    ):
        source = (qml_root / _qml_component_path(qml_name)).read_text(encoding="utf-8")
        assert "onWheel:" in source, f"{qml_name} debe ajustar el wheel del scroll"
        assert "pixelDelta" in source, f"{qml_name} debe respetar pixelDelta"
        assert "angleDelta" in source, f"{qml_name} debe tener fallback a angleDelta"
        assert "wheelStep" in source, f"{qml_name} debe exponer wheelStep"

    assert "onWheel:" in catalog_table
    assert "pixelDelta" in catalog_table
    assert "angleDelta" in catalog_table
    assert "wheelStep" in catalog_table


def test_catalog_table_export_checkbox_reserves_text_space():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8")

    assert "id: exportSelectionCheckbox" in source
    assert "exportSelectionCheckbox.x + exportSelectionCheckbox.implicitWidth + theme.spacing2" in source
    assert "tableCard.exportSelectionMode && bodyCell.column === 0\n                                    ? theme.spacing8" not in source


def test_catalog_table_supports_drag_range_selection_and_copy():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8")

    assert "property bool hasCellRangeSelection: false" in source
    assert "function startCellRangeSelection(rowIndex, columnIndex)" in source
    assert "function updateCellRangeSelectionFromPoint(point)" in source
    assert "function rowIndexAtTablePoint(point)" in source
    assert "function columnIndexAtTablePoint(point)" in source
    assert "rowAtY(" not in source
    assert "columnAtX(" not in source
    assert "function copyCellRangeSelection()" in source
    assert "copy_display_range_to_clipboard(" in source
    assert "sequences: [StandardKey.Copy]" in source
    assert "tableCard.isCellRangeSelected(bodyCell.row, bodyCell.column)" in source
    assert "!tableCard.hasCellRangeSelection && tableCard.isSelectedRow(row)" in source
    assert "tableCard.clearCellRangeSelection()\n        tableCard.selectRow(rowIndex)" in source
    assert "tableCard.selectRow(bodyCell.row)\n                                    tableCard.startCellRangeSelection" not in source
    assert "id: cellRangeAutoScrollTimer" in source
    assert "function autoScrollCellRangeSelection()" in source
    assert "function updateCellRangeDragPoint(point)" in source
    assert "function isPointInsideBodyTable(point)" in source
    assert "function clearCellRangeSelectionIfOutsideBodyTable(point)" in source
    assert "function clearSelectionIfOutsideBodyTable(point, sourceItem)" in source
    assert "tableCard.screenViewModel.select_row_index(-1)" in source
    assert "function tableContentWidthFromColumns()" in source
    assert "tableCard.rowCount() * 50" in source
    assert "tableCard.clearCellRangeSelection()\n        tableCard.columnsSnapshot" in source
    assert "function onCurrentPageChanged()" in source
    assert "tableCard.clearCellRangeSelection()\n            tableCard.syncPageJumpText()" in source


def test_catalog_page_clears_table_selection_from_any_screen_click():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    page_source = (qml_root / "catalog" / "CatalogScreenPage.qml").read_text(encoding="utf-8")
    table_source = (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8")

    assert "id: catalogTableCard" in page_source
    assert "id: catalogScreenSelectionClearArea" in page_source
    assert "anchors.fill: parent" in page_source
    assert "catalogTableCard.clearSelectionIfOutsideBodyTable(Qt.point(mouse.x, mouse.y), catalogScreenSelectionClearArea)" in page_source
    assert "function clearSelectionIfOutsideBodyTable(point, sourceItem)" in table_source
    assert "sourceItem.mapToItem(tableCard, point.x, point.y)" in table_source
    assert "tableCard.screenViewModel.select_row_index(-1)" in table_source
    assert "id: outsideTableSelectionClearArea" not in table_source


def test_catalog_table_context_menu_collapses_hidden_actions():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8")

    assert source.count("height: visible ? implicitHeight : 0") >= 4
    assert "visible: bodyCell.recordId !== null\n                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_edit : false)" in source
    assert "visible: bodyCell.recordId !== null\n                                        && tableCard.showDeleteAction\n                                        && (tableCard.screenViewModel ? tableCard.screenViewModel.can_delete : false)" in source


def test_report_table_view_supports_drag_range_selection_and_copy():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "reports" / "ReportPreviewTable.qml").read_text(encoding="utf-8")

    for snippet in (
        "property bool hasCellRangeSelection: false",
        "function startCellRangeSelection(rowIndex, columnIndex)",
        "function updateCellRangeSelectionFromPoint(point)",
        "function copyCellRangeSelection()",
        "copy_display_range_to_clipboard(",
        "sequences: [StandardKey.Copy]",
        "root.isCellRangeSelected(reportCell.row, reportCell.column)",
        "id: cellRangeAutoScrollTimer",
        "function clearCellRangeSelectionIfOutsideBodyTable(point)",
    ):
        assert snippet in source, f"ReportPreviewTable.qml debe soportar seleccion por rango con {snippet!r}"

    assert "hasViajeCandidateCellRangeSelection" not in (
        qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml"
    ).read_text(encoding="utf-8")
    assert "hasFacturaCandidateCellRangeSelection" not in (
        qml_root / "workflows" / "recibo" / "ReciboWorkflowForm.qml"
    ).read_text(encoding="utf-8")
    assert "copyCellRangeSelection()" not in (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoMovimientosSection.qml"
    ).read_text(encoding="utf-8")


def test_relevant_table_text_is_mouse_selectable_for_copying():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    selectable_cells = {
        "catalog/CatalogScreenTableCard.qml": (
            "id: catalogSelectableCellText",
            "selectByMouse: true",
            "readOnly: true",
            "bodyCellMouseArea",
        ),
        "reports/ReportPreviewTable.qml": (
            "id: reportSelectableCellText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/factura/FacturaWorkflowForm.qml": (
            "id: viajeCandidateSelectableCellText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/recibo/ReciboWorkflowForm.qml": (
            "id: facturaCandidateSelectableCellText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "catalog/ClientDebtPage.qml": (
            "id: clientDebtSelectableText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/seguridad/SecurityPermissionTable.qml": (
            "id: permissionResourceSelectableText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/seguridad/SecurityUsersList.qml": (
            "id: securityUserSelectableText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/seguridad/SecurityRolesList.qml": (
            "id: securityRoleSelectableText",
            "selectByMouse: true",
            "readOnly: true",
        ),
        "workflows/circuito/detail/CircuitoMovimientosSection.qml": (
            "id: circuitoMovementSelectableCellText",
            "selectByMouse: true",
            "readOnly: true",
        ),
    }

    for relative_path, snippets in selectable_cells.items():
        source = (qml_root / relative_path).read_text(encoding="utf-8")
        for snippet in snippets:
            assert snippet in source, f"{relative_path} debe permitir sombrear texto con {snippet!r}"


def test_catalog_filter_panel_wires_semantic_sort_selector_without_id_label():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "catalog" / "CatalogFilterPanel.qml").read_text(encoding="utf-8")

    assert "screenViewModel.sort_options" in source
    assert "screenViewModel.sort_label" in source
    assert 'objectName: "catalogSortSelector"' in source
    assert 'text: panel.screenViewModel ? panel.screenViewModel.sort_label : ""' in source
    assert "apply_sort_payload" in source
    assert "Más recientes" not in source
    assert "Más antiguos" not in source
    assert 'qsTr("ID")' not in source


def test_client_debt_page_uses_formatted_invoice_balance_from_dashboard_contract():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "catalog" / "ClientDebtPage.qml").read_text(encoding="utf-8")

    assert "rowCard.modelData.saldo_display" in source
    assert "rowCard.modelData.saldo ||" not in source


def test_icon_only_actions_use_app_icon_button_component():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    component_source = (qml_root / "shared" / "controls" / "AppIconButton.qml").read_text(encoding="utf-8")
    app_button_source = (qml_root / "shared" / "controls" / "AppButton.qml").read_text(encoding="utf-8")

    assert "AppIcon" in component_source
    assert "TapHandler" in component_source
    assert "signal clicked()" in component_source
    assert "property string iconSource" not in component_source
    assert "property bool iconOnly" not in app_button_source

    icon_action_sources = {
        "Main.qml": (qml_root / "Main.qml").read_text(encoding="utf-8"),
        "CatalogFilterPanel.qml": (qml_root / "catalog" / "CatalogFilterPanel.qml").read_text(encoding="utf-8"),
        "CatalogScreenTableCard.qml": (qml_root / "catalog" / "CatalogScreenTableCard.qml").read_text(encoding="utf-8"),
        "AppDateField.qml": (qml_root / "shared" / "controls" / "AppDateField.qml").read_text(encoding="utf-8"),
        "AppDateTimeField.qml": (qml_root / "shared" / "controls" / "AppDateTimeField.qml").read_text(encoding="utf-8"),
        "StatusDistributionCard.qml": (
            qml_root / "shared" / "surfaces" / "StatusDistributionCard.qml"
        ).read_text(encoding="utf-8"),
        "FacturaWorkflowForm.qml": (
            qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml"
        ).read_text(encoding="utf-8"),
    }

    for qml_name, source in icon_action_sources.items():
        assert "AppIconButton" in source, f"{qml_name} debe usar AppIconButton para acciones icon-only"
        assert "display: AbstractButton.IconOnly" not in source, f"{qml_name} aun usa botones Qt icon-only"


@WINDOWS_LIVE_QML_SKIP
def test_main_qml_loads_with_registered_types(session_factory, modelo_workflow, auth_service):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    runtime_session = RuntimeSessionViewModel(auth_service)
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties(
        {
            "appShellViewModel": app_shell,
            "runtimeSessionViewModel": runtime_session,
        }
    )
    engine.load(QUrl.fromLocalFile(str(qml_root / "Main.qml")))

    try:
        assert engine.rootObjects(), "Main.qml no pudo cargar el modulo OpenLogistic.Models"
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()
        runtime_session.dispose()


def test_main_qml_uses_launch_visible_gate_for_window_visibility():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "Main.qml").read_text(encoding="utf-8")

    assert "required property RuntimeSessionViewModel runtimeSessionViewModel" in source
    assert "property bool launchVisible: false" in source
    assert "visible: launchVisible" in source


def test_main_qml_uses_frameless_custom_top_bar():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")
    sidebar_source = (qml_root / "shell" / "SidebarNav.qml").read_text(encoding="utf-8")

    assert "flags: Qt.FramelessWindowHint | Qt.Window" in main_source
    assert "id: shellTopBar" in main_source
    assert "id: shellDragArea" in main_source
    assert "window.startSystemMove()" in main_source
    assert "window.sidebarCollapsed = !window.sidebarCollapsed" in main_source
    assert "window.showMinimized()" in main_source
    assert "window.visibility === Window.Maximized" in main_source
    assert "window.showNormal()" in main_source
    assert "window.showMaximized()" in main_source
    assert "window.close()" in main_source

    assert "onTapped: root.collapseToggleRequested()" not in sidebar_source


def test_main_qml_frameless_window_exposes_resize_handles():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")

    assert "property int resizeHandleSize: 6" in main_source
    assert "function beginSystemResize(edges)" in main_source
    assert "window.startSystemResize(edges)" in main_source
    assert "window.visibility === Window.Windowed" in main_source

    for handle_id in (
        "resizeHandleTop",
        "resizeHandleBottom",
        "resizeHandleLeft",
        "resizeHandleRight",
        "resizeHandleTopLeft",
        "resizeHandleTopRight",
        "resizeHandleBottomLeft",
        "resizeHandleBottomRight",
    ):
        assert f"id: {handle_id}" in main_source

    for edge in (
        "Qt.TopEdge",
        "Qt.BottomEdge",
        "Qt.LeftEdge",
        "Qt.RightEdge",
        "Qt.TopEdge | Qt.LeftEdge",
        "Qt.TopEdge | Qt.RightEdge",
        "Qt.BottomEdge | Qt.LeftEdge",
        "Qt.BottomEdge | Qt.RightEdge",
    ):
        assert edge in main_source


def test_main_qml_loads_workflow_pages_through_generic_loader_contract():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "Main.qml").read_text(encoding="utf-8")

    assert '"ViajeWorkflowPage.qml"' not in source
    assert '"CircuitoWorkflowPage.qml"' not in source
    assert 'workflowComponent === "ViajeWorkflowPage.qml"' not in source
    assert 'workflowComponent === "CircuitoWorkflowPage.qml"' not in source
    assert "current_workflow_source" in source
    assert "Qt.resolvedUrl(workflowSource)" in source
    assert "workflowScreenHost.workflowSourceFor" not in source
    assert "setSource(resolvedSource, initialProperties)" in source
    assert "moduleViewModel: workflowViewModel" in source


def test_main_qml_loads_dashboard_as_home_view():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")
    dashboard_source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")
    sidebar_source = (qml_root / "shell" / "SidebarNav.qml").read_text(encoding="utf-8")
    compact_metric_source = (qml_root / "shared" / "surfaces" / "CompactMetricTile.qml").read_text(encoding="utf-8")

    assert "current_view" in main_source
    assert "dashboardScreenComponent" in main_source
    assert "DashboardPage {" in main_source
    assert "navigate_to" in dashboard_source
    assert "select_module(moduleAccessButton.modelData.module_id)" in dashboard_source
    assert "cursorShape: Qt.PointingHandCursor" in compact_metric_source
    assert "go_home()" in sidebar_source
    assert 'root.appShellViewModel.current_view === "module"' in sidebar_source


def test_sidebar_qml_supports_collapsed_icon_only_navigation():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")
    sidebar_source = (qml_root / "shell" / "SidebarNav.qml").read_text(encoding="utf-8")
    sidebar_button_source = (qml_root / "shell" / "SidebarNavButton.qml").read_text(encoding="utf-8")
    brand_source = (qml_root / "shell" / "SidebarBrandCard.qml").read_text(encoding="utf-8")

    assert "property bool sidebarCollapsed: false" in main_source
    assert "Layout.preferredWidth: window.sidebarCollapsed ? 104" in main_source
    assert "id: sidebarCollapseButton" in main_source
    assert "onClicked: window.sidebarCollapsed = !window.sidebarCollapsed" in main_source
    assert main_source.count("AppIconButton") >= 4
    assert "qrc:/actions/control/left_panel_open" in main_source
    assert "qrc:/actions/control/minimize" in main_source
    assert "qrc:/actions/control/fullscreen" in main_source
    assert "qrc:/actions/control/close" in main_source

    assert "property bool collapsed: false" in sidebar_source
    assert "signal collapseToggleRequested()" in sidebar_source
    assert "onTapped: root.collapseToggleRequested()" not in sidebar_source
    assert "contentWidth: availableWidth" in sidebar_source
    assert "ScrollBar.horizontal.policy: ScrollBar.AlwaysOff" in sidebar_source
    assert "width: navScroll.availableWidth" in sidebar_source
    assert "subtitle: root.collapsed ? \"\" : qsTr(\" \")" in sidebar_source
    assert "collapsed: root.collapsed" in sidebar_source

    assert "property bool collapsed: false" in sidebar_button_source
    assert "topPadding: control.collapsed ? 0 : theme.spacing3" in sidebar_button_source
    assert "bottomPadding: control.collapsed ? 0 : theme.spacing3" in sidebar_button_source
    assert "visible: !control.collapsed" in sidebar_button_source
    assert "ToolTip.text: control.text" in sidebar_button_source
    assert "Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter" in sidebar_button_source

    assert "property bool collapsed: false" in brand_source
    assert "visible: !root.collapsed" in brand_source


def test_main_qml_defers_dashboard_loading_and_blocks_login_overlay_events():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")

    assert "readonly property bool isAuthenticated: window.runtimeSessionViewModel" in main_source
    assert "window.runtimeSessionViewModel.is_authenticated" in main_source
    assert "active: window.visible && !!window.appShellViewModel && window.isAuthenticated" in main_source
    assert "if (!window.isAuthenticated) {" in main_source
    assert "return null" in main_source
    assert "id: loginEventBlocker" in main_source
    assert "acceptedButtons: Qt.AllButtons" in main_source
    assert "preventStealing: true" in main_source
    assert "onWheel: wheel => { wheel.accepted = true }" in main_source


def test_qml_icon_sources_are_wired_with_monogram_fallbacks():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    app_icon_source = (qml_root / "shared" / "controls" / "AppIcon.qml").read_text(encoding="utf-8")
    dashboard_source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")
    app_button_source = (qml_root / "shared" / "controls" / "AppButton.qml").read_text(encoding="utf-8")
    metric_card_source = (qml_root / "shared" / "surfaces" / "MetricCard.qml").read_text(encoding="utf-8")
    compact_metric_source = (qml_root / "shared" / "surfaces" / "CompactMetricTile.qml").read_text(encoding="utf-8")
    form_section_source = (qml_root / "shared" / "surfaces" / "FormSectionCard.qml").read_text(encoding="utf-8")
    sidebar_button_source = (qml_root / "shell" / "SidebarNavButton.qml").read_text(encoding="utf-8")
    sidebar_source = (qml_root / "shell" / "SidebarNav.qml").read_text(encoding="utf-8")

    assert "iconSource: String(modelData.iconSource || \"\")" in dashboard_source
    assert "iconSource: modelData.iconSource || \"\"" in sidebar_source
    assert "ColorOverlay" in app_icon_source
    assert "property color tintColor" in app_icon_source
    assert "property bool tinted" in app_icon_source

    for source in (
        app_button_source,
        metric_card_source,
        compact_metric_source,
        form_section_source,
        sidebar_button_source,
    ):
        assert "property string iconSource" in source
        assert "AppIcon {" in source
        assert "iconSource" in source
        assert "tintColor:" in source
        assert "visible: " in source
        assert "root.monogram" in source or "control.badgeText" in source or "control.text" in source


def test_qt_resource_assets_are_declared_and_registered_at_startup():
    project_root = Path(__file__).resolve().parents[2]
    ui_root = project_root / "src" / "openlogistic_erp" / "ui"
    qrc_path = ui_root / "assets.qrc"
    assets_dir = ui_root / "assets"
    compile_script = project_root / "scripts" / "compile_qrc_assets.py"
    compiler_module = ui_root / "asset_compiler.py"
    resources_helper = ui_root / "resources.py"
    bootstrap_source = (project_root / "src" / "openlogistic_erp" / "bootstrap" / "container.py").read_text(
        encoding="utf-8"
    )

    assert assets_dir.is_dir()
    assert qrc_path.is_file()
    assert compile_script.is_file()
    assert compiler_module.is_file()
    assert resources_helper.is_file()

    root = ET.parse(qrc_path).getroot()
    qresources = root.findall("qresource")
    assert qresources
    assert any(qresource.attrib["prefix"] == "/" for qresource in qresources)

    script_source = compile_script.read_text(encoding="utf-8")
    compiler_source = compiler_module.read_text(encoding="utf-8")
    assert "openlogistic_erp.ui.asset_compiler" in script_source
    assert "pyside6-rcc" in compiler_source
    assert "resources_rc.py" in compiler_source
    assert "assets.qrc" in compiler_source
    assert "discover_assets" not in compiler_source
    assert "write_qrc" not in compiler_source
    assert "--no-compile" not in compiler_source
    assert "tree.write(qrc_path" not in compiler_source

    helper_source = resources_helper.read_text(encoding="utf-8")
    assert "resources_rc" in helper_source
    assert "def register_qt_resources()" in helper_source
    assert "register_qt_resources()" in bootstrap_source

    from openlogistic_erp.ui.resources import register_qt_resources

    register_qt_resources()
    assert QResource(":/icons/placeholder.svg").isValid()


def test_dashboard_qml_uses_real_dashboard_metrics_contract():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    dashboard_source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")
    distribution_card_source = (qml_root / "shared" / "surfaces" / "StatusDistributionCard.qml").read_text(encoding="utf-8")

    assert "fleetStatusMetrics" in dashboard_source
    assert "driverStatusMetrics" in dashboard_source
    assert "summaryMetrics" in dashboard_source
    assert "financeMetrics" in dashboard_source
    assert "StatusDistributionCard" in dashboard_source
    assert "CompactMetricTile" in dashboard_source
    assert "Canvas" in distribution_card_source
    assert ".arc(" in distribution_card_source
    assert "function refreshDashboardMetrics()" in dashboard_source
    assert "root.runtimeSessionViewModel.is_authenticated" in dashboard_source
    assert "onCurrentViewChanged" in dashboard_source
    assert "Mock" not in dashboard_source


def test_billing_timeline_card_exposes_dashboard_controls():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "shared" / "surfaces" / "BillingTimelineCard.qml").read_text(encoding="utf-8")

    assert "property var rows" in source
    assert "property var currencies" in source
    assert "property string selectedCurrency" in source
    assert "property bool showReceipts" in source
    assert "property bool canCompareReceipts" in source
    assert "signal currencySelected(string currencyKey)" in source
    assert "signal receiptsVisibleChanged(bool visible)" in source
    assert 'qsTr("Facturacion mensual")' in source
    assert 'qsTr("Recibos")' in source
    assert "visible: root.canCompareReceipts" in source
    assert "facturado_display" in source
    assert "pagado_display" in source
    assert "max_value" in source
    assert "Canvas" in source
    assert ".lineTo(" in source
    assert ".arc(" in source
    assert "chartCanvas.requestPaint()" in source
    assert "anchors.bottom: parent.bottom" not in source


def test_dashboard_page_embeds_billing_timeline_card():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")

    assert "BillingTimelineCard" in source
    assert "billingTimelineRows" in source
    assert "billingTimelineCurrencies" in source
    assert "selectedBillingTimelineCurrency" in source
    assert "showBillingTimelineReceipts" in source
    assert "canViewBillingTimeline" in source
    assert "canCompareBillingTimelineReceipts" in source
    assert "selectBillingTimelineCurrency" in source
    assert "setBillingTimelineReceiptsVisible" in source


def test_status_distribution_card_exposes_hover_and_clickable_legend_contract():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "shared" / "surfaces" / "StatusDistributionCard.qml").read_text(encoding="utf-8")

    assert "property int hoveredSliceIndex" in source
    assert "function sliceIndexForPoint" in source
    assert "function routeForIndex" in source
    assert "onPointChanged" in source
    assert "MouseArea" in source
    assert "hoverEnabled: true" in source
    assert "root.hoveredSliceIndex = legendItem.index" in source
    assert "root.clicked(route)" in source
    assert "width: implicitWidth" in source
    assert "height: implicitHeight" in source
    assert "function sliceIndexForPoint(localX, localY)" in source
    assert "point.position.x + pieChart.x" not in source
    assert "eventPoint.position.x + pieChart.x" not in source
    assert source.count("pieChart.mapFromItem(") == 2
    assert "point.position.x" in source
    assert "point.position.y" in source
    assert "eventPoint.position.x" in source
    assert "eventPoint.position.y" in source


def test_status_distribution_card_allows_injected_settings_icon():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "shared" / "surfaces" / "StatusDistributionCard.qml").read_text(encoding="utf-8")

    assert 'import "../controls"' in source
    assert 'property string settingsIconSource: ""' in source
    assert "AppIconButton {" in source
    assert 'source: root.settingsIconSource !== "" ? root.settingsIconSource : "qrc:/actions/general/settings"' in source
    assert 'settingsIconSource: "qrc:/actions/general/settings"' in (
        qml_root / "DashboardPage.qml"
    ).read_text(encoding="utf-8")


def test_dashboard_scroll_mouse_area_does_not_overlay_interactive_cards():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")

    assert "WheelHandler {" in source
    assert "MouseArea {" not in source


def test_viaje_workflow_page_wires_form_save_and_cancel_signals():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml").read_text(encoding="utf-8")

    assert "function onSaveRequested()" in source
    assert "page.moduleViewModel.save_form()" in source
    assert "function onCancelRequested()" in source
    assert "page.closeSubpage()" in source


def test_viaje_workflow_page_wires_delete_from_detail_and_context_menu():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml").read_text(encoding="utf-8")

    assert "showDeleteAction: true" in source
    assert "onDeleteRecordRequested: recordId => {" in source
    assert "page.requestDelete(recordId)" in source
    assert "showClose: !(page.moduleViewModel" in source
    assert "page.moduleViewModel.detail_view_model.is_closed" in source
    assert "onDangerActionRequested:" in source
    assert "active_detail_record_id" in source


@WINDOWS_LIVE_QML_SKIP
def test_catalog_screen_page_loads_with_concrete_screen_view_model(session_factory, modelo_workflow):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"screenViewModel": app_shell.current_catalog_screen})
    engine.load(QUrl.fromLocalFile(str(qml_root / "catalog" / "CatalogScreenPage.qml")))

    try:
        assert engine.rootObjects(), "CatalogScreenPage.qml no pudo cargar con CatalogScreenViewModel"
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()


@WINDOWS_LIVE_QML_SKIP
def test_viaje_workflow_page_loads_with_concrete_view_model(session_factory, modelo_workflow, reference_lookup_service):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    module_view_model = app_shell._workflow_modules["viaje"]
    assert isinstance(module_view_model, ViajeWorkflowViewModel)
    run_action_and_wait_for_applied_load(module_view_model.list_screen, lambda: app_shell.select_module("viaje"))
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"moduleViewModel": module_view_model, "appShellViewModel": app_shell})
    engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml")))

    try:
        assert engine.rootObjects(), "ViajeWorkflowPage.qml no pudo cargar con ViajeWorkflowViewModel"
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()
        _flush_qt_events()


@WINDOWS_LIVE_QML_SKIP
def test_circuito_workflow_page_loads_with_concrete_view_model(session_factory, modelo_workflow, reference_lookup_service):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    module_view_model = app_shell._workflow_modules["circuito"]
    run_action_and_wait_for_applied_load(module_view_model.list_screen, lambda: app_shell.select_module("circuito"))
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"moduleViewModel": module_view_model, "appShellViewModel": app_shell})
    engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml")))

    try:
        assert engine.rootObjects(), "CircuitoWorkflowPage.qml no pudo cargar con CircuitoWorkflowViewModel"
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()
        _flush_qt_events()


@WINDOWS_LIVE_QML_SKIP
def test_security_admin_page_loads_with_concrete_view_model(auth_service, rbac_service):
    qml_registry.register_qml_types()

    runtime_session = RuntimeSessionViewModel(auth_service)
    module_view_model = SecurityAdminViewModel(auth_service, rbac_service, runtime_session)
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"moduleViewModel": module_view_model})
    engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "seguridad" / "SecurityAdminPage.qml")))

    try:
        assert engine.rootObjects(), "SecurityAdminPage.qml no pudo cargar con SecurityAdminViewModel"
    finally:
        _dispose_qml_engine(engine)
        module_view_model.dispose()
        runtime_session.dispose()
        _flush_qt_events()


def test_security_admin_page_syncs_detail_drafts_from_selected_profiles():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "workflows" / "seguridad" / "SecurityAdminPage.qml").read_text(encoding="utf-8")

    assert "function syncSelectedUserDrafts()" in source
    assert "function syncSelectedRoleDraft()" in source
    assert "function onSelectedUserProfileChanged()" in source
    assert "function onSelectedRoleProfileChanged()" in source
    assert "page.syncSelectedUserDrafts()" in source
    assert "page.syncSelectedRoleDraft()" in source


def test_main_qml_resolves_security_workflow_page():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    main_source = (qml_root / "Main.qml").read_text(encoding="utf-8")
    dashboard_source = (qml_root / "DashboardPage.qml").read_text(encoding="utf-8")

    assert "current_workflow_source" in main_source
    assert "dashboard_modules" in dashboard_source
    assert "navigate_to" in dashboard_source


def test_circuito_detail_page_switches_between_trips_and_detail_sections():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "workflows" / "circuito" / "detail" / "CircuitoDetailPage.qml").read_text(
        encoding="utf-8"
    )

    assert "property string activeContentMode" in source
    assert 'TabButton {' in source
    assert 'text: qsTr("Viajes")' in source
    assert 'text: qsTr("Detalles")' in source
    assert "Loader {" in source
    assert "sourceComponent: root.activeContentMode === \"trips\" ? tripsComponent : detailsComponent" in source
    assert "Layout.fillHeight: true" not in source
    assert "CircuitoTripsPanel {" in source
    assert "CircuitoSectionsPanel {" in source
    assert "Layout.fillWidth: true" in source


def test_report_filter_panel_uses_stable_field_renderer_component():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    panel_source = (qml_root / "reports" / "ReportFilterPanel.qml").read_text(encoding="utf-8")
    field_source = (qml_root / "reports" / "ReportFilterField.qml").read_text(encoding="utf-8")

    assert "ReportFilterField {" in panel_source
    assert "sourceComponent:" not in panel_source
    assert "required property var filterDef" in field_source
    assert "field.modelData" not in field_source
    assert "item.filterDef" not in field_source


def test_report_filter_field_omits_all_option_for_required_selects():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    field_source = (qml_root / "reports" / "ReportFilterField.qml").read_text(encoding="utf-8")

    assert "function allowsAllOption()" in field_source
    assert "if (!root.allowsAllOption())" in field_source
    assert 'return baseOptions' in field_source


def test_reports_module_page_uses_subpages_with_header_navigation():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    page_source = (qml_root / "reports" / "ReportsModulePage.qml").read_text(encoding="utf-8")

    assert 'import "../workflows/common"' in page_source
    assert 'property string activeSubpage: "selection"' in page_source
    assert "WorkflowSubpageHeader {" in page_source
    assert "currentTitle: root.reportTitle()" in page_source
    assert 'root.activeSubpage = "filters"' in page_source
    assert 'root.activeSubpage = "results"' in page_source
    assert "function generateReport()" in page_source
    assert "function closeSubpage()" in page_source


def test_reports_module_page_remounts_filter_panel_when_reopening_same_report():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    page_source = (qml_root / "reports" / "ReportsModulePage.qml").read_text(encoding="utf-8")

    assert "property int filterPanelRevision: 0" in page_source
    assert "root.filterPanelRevision += 1" in page_source
    assert "Loader {" in page_source
    assert "sourceComponent = null" in page_source
    assert "sourceComponent = reportFilterPanelComponent" in page_source
    assert "ReportFilterPanel {" in page_source


@WINDOWS_LIVE_QML_SKIP
def test_reports_module_page_loads_with_concrete_view_model(qapp):
    del qapp
    qml_registry.register_qml_types()
    definitions = build_default_report_definitions()
    view_model = ReportsModuleViewModel(
        catalog_service=ReportCatalogService(definitions),
        generation_service=ReportGenerationService(definitions, {}),
        export_service=ReportExportService({}),
    )
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    component = QQmlComponent(engine)
    component.loadUrl(QUrl.fromLocalFile(str(qml_root / "reports" / "ReportsModulePage.qml")))
    context = QQmlContext(engine.rootContext())
    root = component.createWithInitialProperties({"moduleViewModel": view_model}, context)

    try:
        assert root is not None, "\n".join(error.toString() for error in component.errors())
        _flush_qt_events(passes=5)
    finally:
        if root is not None:
            root.deleteLater()
        view_model.deleteLater()
        engine.clearComponentCache()
        engine.deleteLater()
        _flush_qt_events(passes=5)


def test_report_preview_table_uses_synced_header_mask_and_column_resize():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "reports" / "ReportPreviewTable.qml").read_text(encoding="utf-8")

    assert "HorizontalHeaderView {" in source
    assert "syncView: bodyTable" in source
    assert "OpacityMask {" in source
    assert "cursorShape: Qt.SizeHorCursor" in source
    assert "previewColumnWidth" in source
    assert "commitColumnWidth" in source
    assert "Repeater {" not in source


def test_report_preview_table_stretches_last_column_to_fill_available_width():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "reports" / "ReportPreviewTable.qml").read_text(encoding="utf-8")

    assert "property real baseWidthTotal" in source
    assert "property int stretchColumnIndex" in source
    assert "function refreshColumnMetrics()" in source
    assert "function availableTableWidth()" in source
    assert "viewportWidth <= totalBaseWidth" in source
    assert "return baseWidth + (viewportWidth - totalBaseWidth)" in source
    assert "root.refreshColumnMetrics()" in source


def test_report_preview_table_headers_toggle_sort_on_click():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "reports" / "ReportPreviewTable.qml").read_text(encoding="utf-8")

    assert "root.tableModel.toggle_sort(headerCell.columnMeta.key)" in source
    assert "root.tableModel.sort_field === headerCell.columnMeta.key" in source
    assert 'root.tableModel.sort_direction === "desc" ? "\\u2193" : "\\u2191"' in source


def test_circuito_detail_cards_expand_to_scroll_available_width():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    detail_source = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoDetailPage.qml"
    ).read_text(encoding="utf-8")
    auto_height_source = (qml_root / "shared" / "surfaces" / "AutoHeightSurfaceCard.qml").read_text(
        encoding="utf-8"
    )

    for panel_name in ("CircuitoHeaderPanel.qml", "CircuitoTripsPanel.qml", "CircuitoSectionsPanel.qml"):
        panel_source = (qml_root / "workflows" / "circuito" / "detail" / panel_name).read_text(
            encoding="utf-8"
        )
        assert "Layout.fillWidth: true" in panel_source
        assert "Layout.minimumWidth: 0" in panel_source

    assert "width: detailScroll.availableWidth" in detail_source
    assert "width: parent.availableWidth" not in detail_source
    assert "Layout.preferredWidth: Layout.fillWidth ? 0 : implicitWidth" in auto_height_source
    assert "Layout.preferredWidth: Layout.fillWidth ? -1 : implicitWidth" not in auto_height_source


def test_consumo_analysis_cards_render_inside_matching_detail_sections():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    analysis_cards = (
        qml_root / "workflows" / "common" / "ConsumoAnalysisCards.qml"
    ).read_text(encoding="utf-8")
    viaje_page = (
        qml_root / "workflows" / "viaje" / "detail" / "ViajeDetailPage.qml"
    ).read_text(encoding="utf-8")
    viaje_panel = (
        qml_root / "workflows" / "viaje" / "detail" / "ViajeDetailOperationsPanel.qml"
    ).read_text(encoding="utf-8")
    circuito_page = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoDetailPage.qml"
    ).read_text(encoding="utf-8")
    circuito_panel = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoSectionsPanel.qml"
    ).read_text(encoding="utf-8")

    assert "required property var analysis" in analysis_cards
    assert "MetricCard {" in analysis_cards
    assert "analysisType" in analysis_cards
    assert "consumo_thermo_analysis" not in viaje_page
    assert "consumo_camion_analysis" not in circuito_page
    assert "ConsumoAnalysisCards {" in viaje_panel
    assert "analysis: root.summary.consumo_thermo_analysis || ({})" in viaje_panel
    assert "analysisType: \"THERMO\"" in viaje_panel
    assert "ConsumoAnalysisCards {" in circuito_panel
    assert "analysis: root.summary.consumo_camion_analysis || ({})" in circuito_panel
    assert "analysisType: \"CAMION\"" in circuito_panel


def test_circuito_movimientos_section_keeps_table_chrome_when_empty():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoMovimientosSection.qml"
    ).read_text(encoding="utf-8")
    panel_source = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoSectionsPanel.qml"
    ).read_text(encoding="utf-8")

    assert "implicitHeight: contentLayout.implicitHeight" in source
    assert "function headerFields()" in source
    assert "headerModel: root.headerFields()" in source
    assert 'qsTr("Acciones")' in source
    assert 'emptyText: qsTr("Sin movimientos adicionales")' in source
    assert "tableModel: root.formViewModel ? root.formViewModel.table_model : null" in source
    assert 'text: qsTr("Guardar seccion")' in source
    assert "signal saveSucceeded()" in source
    assert "if (root.formViewModel.save_section())" in source
    assert "root.saveSucceeded()" in source
    assert "BaseConfirmDialog {" in panel_source
    assert "saveConfirmationOpen" in panel_source
    assert 'title: qsTr("Cambios guardados")' in panel_source
    assert "onSaveSucceeded: root.saveConfirmationOpen = true" in panel_source


@WINDOWS_LIVE_QML_SKIP
def test_circuito_detail_movimientos_loads_without_negative_model_warning(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                },
            },
        )
    )
    circuito_id = int(created["_circuito_id"])
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    module_view_model = app_shell._workflow_modules["circuito"]
    run_action_and_wait_for_applied_load(module_view_model.list_screen, lambda: app_shell.select_module("circuito"))
    module_view_model.open_detalle(circuito_id)
    module_view_model.detail_view_model.set_active_tab("movimientos_adicionales")

    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    warnings: list[str] = []

    def capture_qml_warning(_mode, _context, message):
        if "Model size of" in message or "less than 0" in message:
            warnings.append(str(message))

    previous_handler = qInstallMessageHandler(capture_qml_warning)
    engine = QQmlApplicationEngine()
    try:
        engine.addImportPath(str(qml_root))
        engine.setInitialProperties({"moduleViewModel": module_view_model, "appShellViewModel": app_shell})
        engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml")))
        _flush_qt_events(passes=5)

        assert engine.rootObjects(), "CircuitoWorkflowPage.qml no pudo cargar con detalle de circuito"
        assert warnings == []
    finally:
        _dispose_qml_engine(engine)
        qInstallMessageHandler(previous_handler)
        app_shell.dispose()
        _flush_qt_events()


def test_circuito_detail_page_renders_add_return_trip_action_when_allowed(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
    created = modelo_workflow.viaje.create(build_viaje_export_payload(deps))
    circuito_id = int(created["_circuito_id"])
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    module_view_model = app_shell._workflow_modules["circuito"]
    run_action_and_wait_for_applied_load(module_view_model.list_screen, lambda: app_shell.select_module("circuito"))
    module_view_model.open_detalle(circuito_id)

    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    engine = QQmlApplicationEngine()
    try:
        engine.addImportPath(str(qml_root))
        engine.setInitialProperties({"moduleViewModel": module_view_model, "appShellViewModel": app_shell})
        engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml")))
        _flush_qt_events(passes=5)

        assert engine.rootObjects(), "CircuitoWorkflowPage.qml no pudo cargar con detalle de circuito"
        action_button_states = []
        for root in engine.rootObjects():
            for item in root.findChildren(QObject):
                try:
                    if item.property("text") == "Agregar viaje de vuelta":
                        action_button_states.append(bool(item.property("visible")))
                except RuntimeError:
                    continue
        assert action_button_states
        assert any(action_button_states)
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()
        _flush_qt_events()


def test_circuito_detail_reuses_readonly_summary_form_and_edits_header_inline():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    trips_source = (qml_root / "workflows" / "circuito" / "detail" / "TripReadOnlyBlock.qml").read_text(
        encoding="utf-8"
    )
    viaje_summary_source = (qml_root / "workflows" / "viaje" / "detail" / "ViajeDetailSummaryPanel.qml").read_text(
        encoding="utf-8"
    )
    header_source = (qml_root / "workflows" / "circuito" / "detail" / "CircuitoHeaderPanel.qml").read_text(
        encoding="utf-8"
    )
    workflow_source = (qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml").read_text(
        encoding="utf-8"
    )

    assert "ReadOnlySummaryFields {" in trips_source
    assert "ReadOnlySummaryFields {" in viaje_summary_source
    assert "FormFieldRenderer {" in header_source
    assert "formViewModel: root.formViewModel" in header_source
    assert "readOnly: !root.editable" in header_source
    assert "root.formViewModel.submit_form()" in header_source
    assert "page.moduleViewModel.open_detalle(recordId)" in workflow_source


def test_circuito_movimientos_section_hides_edit_actions_in_read_only_mode():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (
        qml_root
        / "workflows"
        / "circuito"
        / "detail"
        / "CircuitoMovimientosSection.qml"
    ).read_text(encoding="utf-8")

    assert "readonly property bool readOnly: root.formViewModel ? root.formViewModel.is_read_only : true" in source
    assert "enabled: !!root.formViewModel && !root.readOnly" in source
    assert "visible: !root.readOnly" in source


@WINDOWS_LIVE_QML_SKIP
def test_viaje_workflow_page_detail_loads_without_undefined_binding_warnings(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()

    with session_factory() as session:
        deps = seed_viaje_dependencies(session)

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(
            deps,
            detalle_operacion={
                "descarga": {
                    "fecha_descarga": datetime(2026, 1, 16, 10, 0, 0),
                },
                "gasto_real_thermo": {
                    "combustible_base_thermo": 40,
                },
                "ordenes_combustible": [
                    {
                        "gasolinera": "NEDICSA",
                        "numero_orden": "ORD-QML-REOPEN-001",
                        "galones_autorizados": 70,
                        "tipo": "CAMION",
                    }
                ],
            },
        )
    )
    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    module_view_model = app_shell._workflow_modules["viaje"]
    assert isinstance(module_view_model, ViajeWorkflowViewModel)
    run_action_and_wait_for_applied_load(module_view_model.list_screen, lambda: app_shell.select_module("viaje"))
    module_view_model.open_detalle(created["id"])
    module_view_model.detail_view_model.set_active_tab("ordenes_combustible")

    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    warnings: list[str] = []

    def capture_qml_warning(_mode, _context, message):
        if "undefined" in message or "Cannot read property" in message or "Binding loop" in message:
            warnings.append(str(message))

    previous_handler = qInstallMessageHandler(capture_qml_warning)
    engine = QQmlApplicationEngine()
    try:
        engine.addImportPath(str(qml_root))
        engine.setInitialProperties({"moduleViewModel": module_view_model})
        engine.load(QUrl.fromLocalFile(str(qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml")))
        _flush_qt_events(passes=5)

        assert engine.rootObjects(), "ViajeWorkflowPage.qml no pudo cargar con detalle de viaje"
        assert warnings == []
    finally:
        _dispose_qml_engine(engine)
        qInstallMessageHandler(previous_handler)
        app_shell.dispose()
        _flush_qt_events()


def test_viaje_detail_operations_panel_resolves_sections_from_registry():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (
        qml_root
        / "workflows"
        / "viaje"
        / "detail"
        / "ViajeDetailOperationsPanel.qml"
    ).read_text(encoding="utf-8")

    assert "sectionRegistry" in source
    assert "sourceComponent: root.componentForSection(root.activeSectionKey())" in source
    assert "return descargaSectionComponent" not in source
    assert 'active_tab === "combustible_thermo"' not in source
    assert 'active_tab === "ordenes_combustible"' not in source


def test_viaje_detail_operations_panel_hides_actions_when_closed_and_confirms_reopen():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (
        qml_root
        / "workflows"
        / "viaje"
        / "detail"
        / "ViajeDetailOperationsPanel.qml"
    ).read_text(encoding="utf-8")

    assert "visible: !root.detailClosed" in source
    assert "root.detailViewModel.close_detail()" in source
    assert "visible: root.detailClosed" in source
    assert "Reabrir este viaje solo es recomendable" in source
    assert "root.detailViewModel.reopen_detail()" in source


def test_viaje_detail_section_actions_are_hidden_in_read_only_mode():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    section_source = (qml_root / "workflows" / "viaje" / "OperationalDetailSectionForm.qml").read_text(
        encoding="utf-8"
    )
    orders_source = (qml_root / "workflows" / "viaje" / "OperationalFuelOrdersSection.qml").read_text(
        encoding="utf-8"
    )

    assert "visible: !root.readOnly" in section_source
    assert "visible: !root.readOnly" in orders_source


def test_viaje_detail_save_actions_show_success_confirmation_after_save():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    base_dialog = qml_root / "catalog" / "BaseConfirmDialog.qml"
    panel_source = (qml_root / "workflows" / "viaje" / "detail" / "ViajeDetailOperationsPanel.qml").read_text(
        encoding="utf-8"
    )
    delete_dialog_source = (qml_root / "catalog" / "CatalogScreenConfirmDialog.qml").read_text(encoding="utf-8")
    section_source = (qml_root / "workflows" / "viaje" / "OperationalDetailSectionForm.qml").read_text(
        encoding="utf-8"
    )
    orders_source = (qml_root / "workflows" / "viaje" / "OperationalFuelOrdersSection.qml").read_text(
        encoding="utf-8"
    )

    assert base_dialog.exists()
    base_source = base_dialog.read_text(encoding="utf-8")
    assert "property var buttons" in base_source
    assert "signal actionRequested(string role)" in base_source
    assert "model: root.buttons" in base_source
    assert "variant: buttonDelegate.modelData.variant" in base_source
    assert "BaseConfirmDialog {" in delete_dialog_source
    assert 'role: "cancel"' in delete_dialog_source
    assert 'role: "confirm"' in delete_dialog_source
    assert "saveConfirmationOpen" in panel_source
    assert "BaseConfirmDialog {" in panel_source
    assert 'role: "accept"' in panel_source
    assert 'role: "cancel"' not in panel_source.split('title: qsTr("Cambios guardados")', 1)[1].split("Component {", 1)[0]
    assert "Se guardaron los cambios correctamente." in panel_source
    assert "if (root.detailViewModel.save_all())" in panel_source
    assert "signal saveSucceeded()" in section_source
    assert "if (root.formViewModel.save_section())" in section_source
    assert "root.saveSucceeded()" in section_source
    assert "signal saveSucceeded()" in orders_source
    assert "if (root.formViewModel.save_section())" in orders_source
    assert "root.saveSucceeded()" in orders_source


@WINDOWS_LIVE_QML_SKIP
def test_viaje_workflow_form_loads_with_header_layout_metadata(qapp, modelo_workflow, reference_lookup_service):
    del qapp
    qml_registry.register_qml_types()
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    form = ViajeFormViewModel(
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    component = QQmlComponent(engine)
    component.loadUrl(QUrl.fromLocalFile(str(qml_root / "workflows" / "viaje" / "ViajeWorkflowForm.qml")))
    context = QQmlContext(engine.rootContext())
    root = component.createWithInitialProperties({"formViewModel": form}, context)

    try:
        assert root is not None, "\n".join(error.toString() for error in component.errors())
        _flush_qt_events(passes=5)
        assert root.property("renderedHeaderLayoutItemCount") == 13
    finally:
        if root is not None:
            root.deleteLater()
        form.deleteLater()
        engine.clearComponentCache()
        engine.deleteLater()
        _flush_qt_events(passes=5)


def test_recibo_workflow_form_renders_factura_candidates_with_table_view(staging_database_url):
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    script = textwrap.dedent(
        f"""
        import os
        from pathlib import Path
        from uuid import uuid4

        from PySide6.QtCore import QUrl, QObject
        from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlContext
        from PySide6.QtWidgets import QApplication
        from sqlalchemy.orm import sessionmaker

        from openlogistic_erp.application.modelo.factories import build_modelo_module
        from openlogistic_erp.infrastructure.persistence.database import build_postgres_connect_args, create_engine_and_factory, with_session_auth_context
        from openlogistic_erp.infrastructure.persistence.modelo.repositories import SqlAlchemyModeloRepository
        from openlogistic_erp.presentation.qml_registry import register_qml_types
        from openlogistic_erp.presentation.workflows.recibo import ReciboFormViewModel
        from tests.builders.modelo_seed import build_factura_payload, create_cliente

        app = QApplication.instance() or QApplication([])
        engine_db, _ = create_engine_and_factory(
            os.environ["OPENLOGISTIC_DATABASE_URL"],
            connect_args=build_postgres_connect_args(os.environ.get("OPENLOGISTIC_ENV", "development")),
        )
        connection = engine_db.connect()
        transaction = connection.begin()
        try:
            base_factory = sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            session_factory = with_session_auth_context(base_factory, apply_authenticated_role=True)
            workflow_service = build_modelo_module(repository=SqlAlchemyModeloRepository(session_factory), session_factory=session_factory)
            token = uuid4().hex[:8].upper()
            with session_factory() as session:
                cliente = create_cliente(session, nombre=f"Cliente Recibo TableView {{token}}", ruc=f"REC-TBL-{{token}}")
                session.commit()
                cliente_id = cliente.id
            factura_payload = build_factura_payload(cliente_id, [])
            factura_payload["factura"]["numero_factura"] = f"FAC-TBL-{{token}}"
            factura = workflow_service.factura.create(factura_payload)

            form = ReciboFormViewModel(catalog_service=workflow_service.catalog, workflow_service=workflow_service)
            form.load(None)
            form.set_field_value("cliente_id", cliente_id)
            form.open_factura_selector()

            register_qml_types()
            qml_root = Path({str(qml_root)!r})
            engine = QQmlApplicationEngine()
            engine.addImportPath(str(qml_root))
            component = QQmlComponent(engine)
            component.loadUrl(QUrl.fromLocalFile(str(qml_root / "workflows" / "recibo" / "ReciboWorkflowForm.qml")))
            context = QQmlContext(engine.rootContext())
            root = component.createWithInitialProperties({{"formViewModel": form, "width": 1200, "height": 720}}, context)
            if root is None:
                raise SystemExit("\\n".join(error.toString() for error in component.errors()))
            for _ in range(20):
                app.processEvents()
            table = root.findChild(QObject, "facturaCandidateTable")
            if table is None:
                raise SystemExit("facturaCandidateTable no fue creado")
            if table.property("rows") != 1:
                raise SystemExit(f"rows={{table.property('rows')}} candidates={{len(form.factura_candidates)}}")
            if form.factura_candidate_model.row_data(0)["value"] != factura["id"]:
                raise SystemExit("La tabla no esta leyendo el modelo de candidatos correcto")
        finally:
            transaction.rollback()
            connection.close()
            engine_db.dispose()
        os._exit(0)
        """
    )
    env = {
        **os.environ,
        "OPENLOGISTIC_DATABASE_URL": staging_database_url,
        "PYTHONPATH": "src",
        "QT_QPA_PLATFORM": "offscreen",
        "QT_QUICK_CONTROLS_STYLE": "Material",
    }
    result = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_viaje_workflow_form_header_delegate_uses_field_metadata():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "workflows" / "viaje" / "ViajeWorkflowForm.qml").read_text(encoding="utf-8")

    assert "id: fieldContainer" in source
    assert "FormFieldRenderer {" in source
    assert "field: fieldContainer.modelData" in source
    assert "optionsOverride: root.headerFieldOptions(fieldContainer.modelData)" in source
    assert "editableOverride: root.headerFieldEnabled(fieldContainer.modelData.name)" in source
    assert "const lockedFields = root.formViewModel.locked_fields || []" in source
    assert "lockedFields.indexOf(fieldName) !== -1" in source
    assert "useReferenceSetter: false" in source
    assert "property var field: sectionContainer.modelData" not in source
    assert "sectionContainer.modelData.label" not in source
    assert "sectionContainer.modelData.kind" not in source


@WINDOWS_LIVE_QML_SKIP
def test_catalog_screen_page_handles_search_selection_and_edit_with_loaded_qml(session_factory, modelo_workflow):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    screen = app_shell.current_catalog_screen
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    assert screen is not None

    run_action_and_wait_for_request(screen, screen.load)
    rows = screen.table_model.rows()
    assert rows

    term = str(rows[0][screen.search_field])[:4]

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"screenViewModel": screen})
    engine.load(QUrl.fromLocalFile(str(qml_root / "catalog" / "CatalogScreenPage.qml")))

    try:
        assert engine.rootObjects(), "CatalogScreenPage.qml no pudo cargar con CatalogScreenViewModel"
        run_action_and_wait_for_request(screen, lambda: screen.apply_search(term))
        record_id = screen.record_id_at_row(0)
        assert isinstance(record_id, int)
        screen.select_record_by_id(record_id)
        assert screen.selected_record_id == record_id
        assert screen.open_record_form(record_id) is True
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()


@WINDOWS_LIVE_QML_SKIP
def test_catalog_screen_page_opens_factura_form_with_loaded_qml(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    screen = app_shell._catalog_screens["factura"]
    run_action_and_wait_for_applied_load(screen, lambda: app_shell.select_module("factura"))
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    assert screen is not None

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"screenViewModel": screen})
    engine.load(QUrl.fromLocalFile(str(qml_root / "catalog" / "CatalogScreenPage.qml")))

    try:
        assert engine.rootObjects(), "CatalogScreenPage.qml no pudo cargar con factura"
        assert screen.open_create_form() is True
        _flush_qt_events(passes=5)
        assert screen.form_host.is_open is True
        assert isinstance(screen.form_host.active_form, qml_registry.FacturaFormViewModel)
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()


@WINDOWS_LIVE_QML_SKIP
def test_catalog_screen_page_does_not_mount_page_forms_in_hidden_overlay(
    session_factory,
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(
        query_service,
        modelo_workflow.catalog,
        reference_lookup_service=reference_lookup_service,
        workflow_service=modelo_workflow,
    )
    screen = app_shell._catalog_screens["recibo"]
    run_action_and_wait_for_applied_load(screen, lambda: app_shell.select_module("recibo"))
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    assert screen is not None

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"screenViewModel": screen})
    engine.load(QUrl.fromLocalFile(str(qml_root / "catalog" / "CatalogScreenPage.qml")))

    try:
        assert engine.rootObjects(), "CatalogScreenPage.qml no pudo cargar con recibo"
        assert screen.open_create_form() is True
        _flush_qt_events(passes=10)

        root = engine.rootObjects()[0]
        form_instances = [
            item
            for item in root.findChildren(QObject)
            if "ReciboWorkflowForm" in item.metaObject().className()
        ]
        assert len(form_instances) == 1
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()


@WINDOWS_LIVE_QML_SKIP
def test_factura_workflow_form_loads_with_concrete_view_model(
    modelo_workflow,
    reference_lookup_service,
):
    qml_registry.register_qml_types()
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    form = qml_registry.FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    component = QQmlComponent(engine)
    component.loadUrl(QUrl.fromLocalFile(str(qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml")))
    context = QQmlContext(engine.rootContext())
    root = component.createWithInitialProperties({"formViewModel": form}, context)

    try:
        assert root is not None, "\n".join(error.toString() for error in component.errors())
        _flush_qt_events(passes=5)
    finally:
        if root is not None:
            root.deleteLater()
        form.deleteLater()
        engine.clearComponentCache()
        engine.deleteLater()
        _flush_qt_events(passes=5)


@WINDOWS_LIVE_QML_SKIP
def test_factura_workflow_form_opens_viaje_selector_table_with_live_qml(
    modelo_workflow,
    session_factory,
    reference_lookup_service,
    install_reference_lookup_schema,
):
    del install_reference_lookup_schema
    from uuid import uuid4

    from openlogistic_erp.infrastructure.persistence.modelo.workflow_orm import EstadoFacturacion, EstadoViaje, Viaje

    token = uuid4().hex[:8].upper()
    with session_factory() as session:
        deps = seed_viaje_dependencies(session)
        cliente_id = deps["cliente_id"]

    created = modelo_workflow.viaje.create(
        build_viaje_export_payload(deps, viaje={"descripcion": f"selector qml {token}"})
    )
    with session_factory() as session:
        viaje = session.get(Viaje, created["id"])
        assert viaje is not None
        viaje.estado = EstadoViaje.FINALIZADO
        viaje._estado_facturacion = EstadoFacturacion.REGISTRADO
        session.commit()

    qml_registry.register_qml_types()
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    form = qml_registry.FacturaFormViewModel(
        catalog_service=modelo_workflow.catalog,
        workflow_service=modelo_workflow,
        reference_lookup_service=reference_lookup_service,
    )
    form.load(None)
    form.set_lookup_field_value("cliente_id", cliente_id, "Cliente Demo")
    form.search_lookup_options("viaje_id", token)
    form.open_viaje_selector()

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    component = QQmlComponent(engine)
    component.loadUrl(QUrl.fromLocalFile(str(qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml")))
    context = QQmlContext(engine.rootContext())
    root = component.createWithInitialProperties({"formViewModel": form, "width": 1200, "height": 720}, context)

    try:
        assert root is not None, "\n".join(error.toString() for error in component.errors())
        _flush_qt_events(passes=20)
        table = root.findChild(QObject, "viajeCandidateTable")
        assert table is not None
        assert table.property("rows") == 1
        assert form.viaje_candidate_model.row_data(0)["value"] == created["id"]
    finally:
        if root is not None:
            root.deleteLater()
        form.deleteLater()
        engine.clearComponentCache()
        engine.deleteLater()
        _flush_qt_events(passes=5)


@WINDOWS_LIVE_QML_SKIP
def test_catalog_screen_page_mounts_pagination_controls(session_factory, modelo_workflow):
    qml_registry.register_qml_types()

    query_service = ModeloCatalogQueryService(SqlAlchemyCatalogQueryRepository(session_factory))
    app_shell = build_default_app_shell(query_service, modelo_workflow.catalog)
    screen = app_shell.current_catalog_screen
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    assert screen is not None

    run_action_and_wait_for_request(screen, screen.load)

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.setInitialProperties({"screenViewModel": screen})
    engine.load(QUrl.fromLocalFile(str(qml_root / "catalog" / "CatalogScreenPage.qml")))

    try:
        assert engine.rootObjects(), "CatalogScreenPage.qml no pudo cargar con CatalogScreenViewModel"
        root = engine.rootObjects()[0]

        for object_name in (
            "paginationFirstButton",
            "paginationPrevButton",
            "paginationPageField",
            "paginationGoButton",
            "paginationNextButton",
            "paginationLastButton",
        ):
            assert root.findChild(QObject, object_name) is not None, f"Falta el control {object_name}"

        page_field = root.findChild(QObject, "paginationPageField")
        assert page_field is not None
        assert page_field.property("text") == "1"
    finally:
        _dispose_qml_engine(engine)
        app_shell.dispose()


@WINDOWS_LIVE_QML_SKIP
def test_generic_catalog_form_qml_loads_custom_layout_metadata(qapp):
    del qapp
    qml_registry.register_qml_types()
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    form = GenericCatalogFormViewModel(
        catalog_name="cliente",
        fields=(
            GenericFormFieldDefinition(name="nombre", required=True),
            GenericFormFieldDefinition(name="ruc", required=True),
            GenericFormFieldDefinition(name="direccion"),
        ),
        form_layout=FormLayoutDefinition(
            items=(
                FormLayoutSectionItem(title="Encabezado"),
                FormLayoutFieldItem(field_name="nombre"),
                FormLayoutFieldItem(field_name="ruc"),
                FormLayoutFieldItem(field_name="direccion", full_width=True),
            )
        ),
        catalog_service=object(),
    )

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    component = QQmlComponent(engine)
    component.loadUrl(QUrl.fromLocalFile(str(qml_root / "shared" / "forms" / "GenericCatalogForm.qml")))
    context = QQmlContext(engine.rootContext())
    context.setContextProperty("testFormViewModel", form)
    root = component.createWithInitialProperties({"formViewModel": form}, context)

    try:
        assert root is not None, "\n".join(error.toString() for error in component.errors())
        _flush_qt_events(passes=5)
        assert root.property("renderedLayoutItemCount") == 3
    finally:
        if root is not None:
            root.deleteLater()
        engine.clearComponentCache()
        engine.deleteLater()
        _flush_qt_events(passes=5)


def test_workflow_repeatable_cards_use_field_layout_metadata():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    viaje_source = (qml_root / "workflows" / "viaje" / "ViajeWorkflowForm.qml").read_text(encoding="utf-8")
    factura_source = (qml_root / "workflows" / "factura" / "FacturaWorkflowForm.qml").read_text(encoding="utf-8")
    recibo_source = (qml_root / "workflows" / "recibo" / "ReciboWorkflowForm.qml").read_text(encoding="utf-8")

    assert "fuel_order_fields" in viaje_source
    assert "Layout.columnSpan" in viaje_source
    assert "detail_fields" in factura_source
    assert "facturaDetailCollapseButton" in factura_source
    assert "Layout.columnSpan" in factura_source
    assert "selected_factura_fields" in recibo_source
    assert "Layout.columnSpan" in recibo_source


def test_grouped_client_cards_start_collapsed_and_toggle_from_headers():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"

    viaje_source = (qml_root / "workflows" / "viaje" / "ViajeWorkflowPage.qml").read_text(encoding="utf-8")
    debt_source = (qml_root / "catalog" / "ClientDebtPage.qml").read_text(encoding="utf-8")

    assert "property bool expanded: false" in viaje_source
    assert "onClicked: clientCard.expanded = !clientCard.expanded" in viaje_source
    assert "visible: clientCard.expanded" in viaje_source

    assert "property bool expanded: false" in debt_source
    assert "onClicked: debtCard.expanded = !debtCard.expanded" in debt_source
    assert "visible: debtCard.expanded" in debt_source


def test_detail_editable_table_component_uses_real_table_primitives():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    source = (qml_root / "shared" / "tables" / "DetailEditableTable.qml").read_text(encoding="utf-8")

    assert "HorizontalHeaderView" in source
    assert "TableView" in source
    assert "syncView: bodyTable" in source
    assert "OpacityMask" in source
    assert "clip: true" in source


def test_detail_sections_use_shared_real_table_component():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    circuito_source = (
        qml_root / "workflows" / "circuito" / "detail" / "CircuitoMovimientosSection.qml"
    ).read_text(encoding="utf-8")
    fuel_source = (
        qml_root / "workflows" / "viaje" / "OperationalFuelOrdersSection.qml"
    ).read_text(encoding="utf-8")

    assert "DetailEditableTable" in circuito_source
    assert "DetailEditableTable" in fuel_source


def test_generated_qmltypes_capture_concrete_view_model_graph(tmp_path):
    module_dir = generate_qmltypes(tmp_path / "OpenLogistic" / "Models")
    contract = (module_dir / "OpenLogisticModels.qmltypes").read_text(encoding="utf-8")

    assert 'name: "AppShellViewModel"' in contract
    assert 'name: "RuntimeSessionViewModel"' in contract
    assert 'name: "SecurityAdminViewModel"' in contract
    assert 'name: "WorkflowModuleViewModel"' in contract
    assert 'name: "ViajeWorkflowViewModel"' in contract
    assert 'name: "CircuitoWorkflowViewModel"' in contract
    assert 'name: "CircuitoDetailViewModel"' in contract
    assert 'name: "CircuitoBasicFormViewModel"' in contract
    assert 'name: "DetalleOperacionViewModel"' in contract
    assert 'name: "DetailSectionFormViewModel"' in contract
    assert 'name: "FuelOrdersSectionFormViewModel"' in contract
    assert 'name: "CatalogScreenViewModel"' in contract
    assert 'name: "CatalogWorkbenchViewModel"' in contract
    assert 'name: "FormHostViewModel"' in contract
    assert 'name: "CatalogTableModel"' in contract
    assert 'name: "BaseFormViewModel"' in contract
    assert 'name: "WorkflowFormViewModelBase"' in contract
    assert 'name: "FacturaFormViewModel"' in contract
    assert 'name: "ReciboFormViewModel"' in contract
    assert 'name: "ViajeFormViewModel"' in contract
    assert 'name: "current_catalog_screen"' in contract and 'type: "CatalogScreenViewModel"' in contract
    assert 'name: "current_workflow_module"' in contract and 'type: "WorkflowModuleViewModel"' in contract
    assert 'name: "current_workflow_component"' in contract and 'type: "QString"' in contract
    assert 'name: "form_host"' in contract and 'type: "FormHostViewModel"' in contract
    assert 'name: "table_model"' in contract and 'type: "CatalogTableModel"' in contract
    assert 'name: "selected_row_data"' in contract
    assert 'name: "active_form"' in contract and 'type: "BaseFormViewModel"' in contract
    assert 'name: "detail_view_model"' in contract and 'type: "DetalleOperacionViewModel"' in contract
    assert 'name: "viaje_summary"' in contract and 'type: "QVariantMap"' in contract
    assert 'name: "visible_sections"' in contract and 'type: "QVariantList"' in contract
    assert 'name: "select_record_by_id"' in contract
    assert 'name: "record_id_at_row"' in contract and 'type: "int"' in contract


def test_qmllint_accepts_generated_qml_module(tmp_path):
    module_dir = generate_qmltypes(tmp_path / "OpenLogistic" / "Models")
    result = run_qmllint(module_dir)

    assert result.returncode == 0, result.stdout + result.stderr


def test_qml_typegen_cli_generates_and_lints(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path / "OpenLogistic" / "Models"), "--lint", "--quiet"])

    assert exit_code == 0


def test_trip_read_only_block_exposes_existing_trip_action():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    summary_text = (qml_root / "shared" / "forms" / "ReadOnlySummaryFields.qml").read_text(encoding="utf-8")
    text = (qml_root / "workflows" / "circuito" / "detail" / "TripReadOnlyBlock.qml").read_text(encoding="utf-8")
    assert "property bool secondaryActionVisible" in summary_text
    assert "property string secondaryActionText" in summary_text
    assert "signal secondaryActionRequested()" in summary_text
    assert "property bool existingActionVisible" in text
    assert 'property string existingActionText: qsTr("Ver detalle operativo")' in text
    assert "signal existingActionRequested()" in text


def test_circuito_trip_panels_propagate_existing_trip_navigation():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    panel_text = (qml_root / "workflows" / "circuito" / "detail" / "CircuitoTripsPanel.qml").read_text(encoding="utf-8")
    detail_text = (qml_root / "workflows" / "circuito" / "detail" / "CircuitoDetailPage.qml").read_text(encoding="utf-8")
    assert "signal openTripDetailRequested(var viajeId)" in panel_text
    assert "onExistingActionRequested: root.openTripDetailRequested(root.viajeIda.id)" in panel_text
    assert "onExistingActionRequested: root.openTripDetailRequested(root.viajeVuelta.id)" in panel_text
    assert "signal openTripDetailRequested(var viajeId)" in detail_text


def test_circuito_workflow_page_forwards_trip_detail_navigation_to_app_shell():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    text = (qml_root / "workflows" / "circuito" / "CircuitoWorkflowPage.qml").read_text(encoding="utf-8")
    assert "onOpenTripDetailRequested: viajeId =>" in text
    assert "required property AppShellViewModel appShellViewModel" in text
    assert "page.appShellViewModel.navigate_to({" in text
    assert '"module_id": "viaje"' in text
    assert '"target": "detail"' in text
    assert '"record_id": viajeId' in text


def test_main_passes_app_shell_to_circuito_workflow_page():
    qml_root = Path(__file__).resolve().parents[2] / "src" / "openlogistic_erp" / "ui" / "qml"
    text = (qml_root / "Main.qml").read_text(encoding="utf-8")
    assert '|| workflowModuleId === "circuito"' in text
    assert 'initialProperties.appShellViewModel = window.appShellViewModel' in text
