"""Persistence helpers for per-catalog table presentation preferences."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..qt import QSettings


class CatalogTablePreferencesStore(ABC):
    """Abstracts persistence for user-adjustable table preferences."""

    @abstractmethod
    def load_column_widths(self, catalog_name: str) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def save_column_width(self, catalog_name: str, field_name: str, width: int) -> None:
        raise NotImplementedError


class InMemoryCatalogTablePreferencesStore(CatalogTablePreferencesStore):
    def __init__(self) -> None:
        self._storage: dict[str, dict[str, int]] = {}

    def load_column_widths(self, catalog_name: str) -> dict[str, int]:
        return dict(self._storage.get(str(catalog_name).lower(), {}))

    def save_column_width(self, catalog_name: str, field_name: str, width: int) -> None:
        normalized_catalog = str(catalog_name).lower()
        bucket = self._storage.setdefault(normalized_catalog, {})
        bucket[str(field_name)] = int(width)


class QSettingsCatalogTablePreferencesStore(CatalogTablePreferencesStore):
    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    def load_column_widths(self, catalog_name: str) -> dict[str, int]:
        normalized_catalog = str(catalog_name).lower()
        base_key = self._base_key(normalized_catalog)
        self._settings.beginGroup(base_key)
        try:
            result: dict[str, int] = {}
            for field_name in self._settings.childKeys():
                value = self._settings.value(field_name, 0)
                coerced = self._coerce_int(value)
                if coerced is None:
                    continue
                result[str(field_name)] = coerced
            return result
        finally:
            self._settings.endGroup()

    def save_column_width(self, catalog_name: str, field_name: str, width: int) -> None:
        normalized_catalog = str(catalog_name).lower()
        self._settings.setValue(f"{self._base_key(normalized_catalog)}/{field_name}", int(width))

    @staticmethod
    def _base_key(catalog_name: str) -> str:
        return f"catalog_table/{catalog_name}/column_widths"

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None
