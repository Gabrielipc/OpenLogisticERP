"""Viaje workflow presentation types."""

from ..common import WorkflowDescriptor, WorkflowModuleViewModel
from .detail import DetalleOperacionViewModel, DetailSectionFormViewModel, FuelOrdersSectionFormViewModel, FuelOrdersTableModel
from .forms import ViajeFormViewModel
from .viewmodels import ViajeWorkflowViewModel

__all__ = [
    "DetalleOperacionViewModel",
    "DetailSectionFormViewModel",
    "FuelOrdersSectionFormViewModel",
    "FuelOrdersTableModel",
    "ViajeFormViewModel",
    "ViajeWorkflowViewModel",
    "WorkflowDescriptor",
    "WorkflowModuleViewModel",
]
