"""QML module registration for Python-backed view models."""

from __future__ import annotations

from .app_shell import AppShellViewModel, WorkflowPlaceholderViewModel
from .catalog import (
    BaseFormViewModel,
    CatalogScreenViewModel,
    CatalogTableModel,
    CatalogWorkbenchViewModel,
    FormHostViewModel,
    GenericCatalogFormViewModel,
)
from .dashboard import DashboardViewModel
from .qml_module import QML_IMPORT_MAJOR_VERSION, QML_IMPORT_MINOR_VERSION, QML_IMPORT_NAME
from .reports import ReportsModuleViewModel, ReportTableModel
from .viewmodels import BaseViewModel, RuntimeSessionViewModel
from .workflows.circuito import (
    CircuitoBasicFormViewModel,
    CircuitoDetailViewModel,
    CircuitoMovimientosAdicionalesFormViewModel,
    CircuitoMovimientosTableModel,
    CircuitoWorkflowViewModel,
)
from .workflows.common import WorkflowModuleViewModel
from .workflows.factura import FacturaFormViewModel
from .workflows.recibo import ReciboFormViewModel
from .workflows.viaje import (
    DetailSectionFormViewModel,
    DetalleOperacionViewModel,
    FuelOrdersSectionFormViewModel,
    FuelOrdersTableModel,
    ViajeFormViewModel,
    ViajeWorkflowViewModel,
)
from .workflows.seguridad import SecurityAdminViewModel

QML_MODULE_URI = QML_IMPORT_NAME
QML_MODULE_MAJOR_VERSION = QML_IMPORT_MAJOR_VERSION
QML_MODULE_MINOR_VERSION = QML_IMPORT_MINOR_VERSION

QML_NAMED_TYPES: tuple[tuple[type[object], str], ...] = (
    (BaseViewModel, "BaseViewModel"),
    (BaseFormViewModel, "BaseFormViewModel"),
    (GenericCatalogFormViewModel, "GenericCatalogFormViewModel"),
    (FormHostViewModel, "FormHostViewModel"),
    (CatalogTableModel, "CatalogTableModel"),
    (CatalogScreenViewModel, "CatalogScreenViewModel"),
    (CatalogWorkbenchViewModel, "CatalogWorkbenchViewModel"),
    (DashboardViewModel, "DashboardViewModel"),
    (WorkflowModuleViewModel, "WorkflowModuleViewModel"),
    (WorkflowPlaceholderViewModel, "WorkflowPlaceholderViewModel"),
    (ReportsModuleViewModel, "ReportsModuleViewModel"),
    (ReportTableModel, "ReportTableModel"),
    (FacturaFormViewModel, "FacturaFormViewModel"),
    (ReciboFormViewModel, "ReciboFormViewModel"),
    (ViajeFormViewModel, "ViajeFormViewModel"),
    (DetailSectionFormViewModel, "DetailSectionFormViewModel"),
    (FuelOrdersSectionFormViewModel, "FuelOrdersSectionFormViewModel"),
    (FuelOrdersTableModel, "FuelOrdersTableModel"),
    (DetalleOperacionViewModel, "DetalleOperacionViewModel"),
    (ViajeWorkflowViewModel, "ViajeWorkflowViewModel"),
    (CircuitoBasicFormViewModel, "CircuitoBasicFormViewModel"),
    (CircuitoDetailViewModel, "CircuitoDetailViewModel"),
    (CircuitoMovimientosAdicionalesFormViewModel, "CircuitoMovimientosAdicionalesFormViewModel"),
    (CircuitoMovimientosTableModel, "CircuitoMovimientosTableModel"),
    (CircuitoWorkflowViewModel, "CircuitoWorkflowViewModel"),
    (SecurityAdminViewModel, "SecurityAdminViewModel"),
    (AppShellViewModel, "AppShellViewModel"),
    (RuntimeSessionViewModel, "RuntimeSessionViewModel"),
)

_REGISTERED = False


def register_qml_types() -> None:
    """Import PySide6-decorated presentation types so QML registration side effects run."""

    global _REGISTERED

    if _REGISTERED:
        return

    # Importing the decorated classes is enough for PySide6 to register them.
    _ = QML_NAMED_TYPES
    _REGISTERED = True
