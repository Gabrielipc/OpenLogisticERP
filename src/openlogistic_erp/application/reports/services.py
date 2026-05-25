from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from openlogistic_erp.domain.reports import ReportFilterOption, ReportFormat, ReportPayload, ReportRequest

from .definitions import ReportDefinition
from .errors import ReportExportError, ReportNotFoundError, ReportValidationError


class ReportReader(Protocol):
    def generate(self, params: dict[str, Any]) -> ReportPayload:
        ...


class ReportExporter(Protocol):
    def export(self, payload: ReportPayload, target_path: str | Path, currency_key: str = "") -> None:
        ...


class ReportCatalogService:
    def __init__(
        self,
        definitions: Mapping[str, ReportDefinition],
        option_provider: Any = None,
    ) -> None:
        self._definitions = dict(definitions)
        self._option_provider = option_provider

    def list_definitions(self) -> list[dict[str, Any]]:
        return [definition.to_map() for definition in self._definitions.values()]

    def get_definition(self, key: str) -> ReportDefinition:
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise ReportNotFoundError(f"Report definition not found: {key}") from exc

    def options_for(self, source: str) -> list[dict[str, Any]]:
        options = self._resolve_options(source)
        return [_option_to_map(option) for option in options]

    def _resolve_options(self, source: str) -> list[ReportFilterOption]:
        provider = self._option_provider
        if provider is None:
            return []

        value: Any
        if isinstance(provider, Mapping):
            value = provider.get(source, [])
        else:
            value = getattr(provider, source, [])

        if callable(value):
            value = value()

        return list(value)


class ReportGenerationService:
    def __init__(
        self,
        definitions: Mapping[str, ReportDefinition],
        readers: Mapping[str, ReportReader],
    ) -> None:
        self._definitions = dict(definitions)
        self._readers = dict(readers)

    def generate(self, request: ReportRequest) -> ReportPayload:
        definition = self._definition_for(request.report_key)
        reader = self._reader_for(request.report_key)
        params = dict(request.params)
        self._validate_params(definition, params)
        return reader.generate(params)

    def _definition_for(self, key: str) -> ReportDefinition:
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise ReportNotFoundError(f"Report definition not found: {key}") from exc

    def _reader_for(self, key: str) -> ReportReader:
        try:
            return self._readers[key]
        except KeyError as exc:
            raise ReportNotFoundError(f"Report reader not found: {key}") from exc

    def _validate_params(self, definition: ReportDefinition, params: Mapping[str, Any]) -> None:
        for filter_definition in definition.filters:
            key = str(filter_definition["key"])
            value = params.get(key)
            if filter_definition.get("required") and _is_empty(value):
                raise ReportValidationError(f"Missing required report parameter: {key}")
            if key in params and filter_definition.get("type") == "date_range":
                if not isinstance(value, (list, tuple)) or len(value) != 2 or any(_is_empty(endpoint) for endpoint in value):
                    raise ReportValidationError(f"Report parameter must be a two-item date range: {key}")


class ReportExportService:
    def __init__(self, exporters: Mapping[ReportFormat, ReportExporter]) -> None:
        self._exporters = {self._coerce_format(key): exporter for key, exporter in exporters.items()}

    def export(
        self,
        payload: ReportPayload,
        target_path: str | Path,
        export_format: ReportFormat | str,
        currency_key: str = "",
    ) -> str:
        path = self._coerce_target_path(target_path)
        report_format = self._coerce_format(export_format)

        try:
            exporter = self._exporters[report_format]
        except KeyError as exc:
            raise ReportExportError(f"Unsupported report export format: {report_format.value}") from exc

        try:
            exporter.export(payload, path, currency_key=currency_key)
        except ReportExportError:
            raise
        except Exception as exc:
            raise ReportExportError(f"Could not export report as {report_format.value}: {exc}") from exc

        return str(path)

    def _coerce_target_path(self, target_path: str | Path) -> Path:
        if isinstance(target_path, str) and not target_path.strip():
            raise ReportExportError("Report export target path cannot be empty")

        path = Path(target_path)
        if not str(path).strip():
            raise ReportExportError("Report export target path cannot be empty")
        return path

    def _coerce_format(self, export_format: ReportFormat | str) -> ReportFormat:
        if isinstance(export_format, ReportFormat):
            return export_format
        try:
            return ReportFormat(str(export_format).strip().lower())
        except ValueError as exc:
            raise ReportExportError(f"Unsupported report export format: {export_format}") from exc


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == () or value == [] or value == {}


def _option_to_map(option: ReportFilterOption | Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(option, "to_map"):
        return option.to_map()
    return dict(option)
