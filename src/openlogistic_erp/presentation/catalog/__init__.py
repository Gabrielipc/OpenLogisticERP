"""Catalog presentation primitives for list + form composition."""

from .definitions import (
    CatalogColumnDefinition,
    CatalogViewDefinition,
    FormDefinition,
    FormFieldOption,
    GenericFormFieldDefinition,
)
from .column_overrides import CatalogColumnOverride, apply_catalog_column_overrides
from .form_layout import FormLayoutDefinition, FormLayoutFieldItem, FormLayoutSectionItem
from .form_host_view_model import FormHostViewModel
from .forms import BaseFormViewModel, FormViewModelContract, GenericCatalogFormViewModel
from .registry import FormRegistry
from .screen_view_model import CatalogScreenViewModel
from .table_model import CatalogTableModel
from .table_preferences import (
    CatalogTablePreferencesStore,
    InMemoryCatalogTablePreferencesStore,
    QSettingsCatalogTablePreferencesStore,
)
from .types import FormMode
from .workbench_view_model import CatalogWorkbenchViewModel, build_default_catalog_workbench

__all__ = [
    "BaseFormViewModel",
    "CatalogColumnDefinition",
    "CatalogColumnOverride",
    "CatalogScreenViewModel",
    "CatalogTableModel",
    "CatalogTablePreferencesStore",
    "CatalogWorkbenchViewModel",
    "CatalogViewDefinition",
    "FormDefinition",
    "FormFieldOption",
    "FormLayoutDefinition",
    "FormLayoutFieldItem",
    "FormLayoutSectionItem",
    "FormHostViewModel",
    "FormMode",
    "FormRegistry",
    "FormViewModelContract",
    "GenericCatalogFormViewModel",
    "GenericFormFieldDefinition",
    "InMemoryCatalogTablePreferencesStore",
    "QSettingsCatalogTablePreferencesStore",
    "apply_catalog_column_overrides",
    "build_default_catalog_workbench",
]
