"""Shared domain/presentation error types for migration readiness."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class MigrationError(Exception):
    """Raised when the bootstrap or migration setup is not valid."""


class NotReadyError(MigrationError):
    """Raised when a module fails READY_TO_MIGRATE criteria."""


class PersistenceConstraintError(ValueError):
    """User-facing representation of persistence constraint failures."""

    def __init__(
        self,
        summary_message: str,
        *,
        field_errors: Mapping[str, str] | None = None,
        error_code: str = "integrity",
        fields: Sequence[str] | None = None,
    ) -> None:
        normalized_summary = str(summary_message or "No se pudo guardar el registro por una restriccion de datos.")
        normalized_field_errors = {
            str(field_name): str(message)
            for field_name, message in dict(field_errors or {}).items()
            if str(field_name or "").strip()
        }
        normalized_fields = tuple(
            dict.fromkeys(
                [
                    str(field_name)
                    for field_name in (fields or ())
                    if str(field_name or "").strip()
                ]
                + list(normalized_field_errors.keys())
            )
        )

        super().__init__(normalized_summary)
        self.summary_message = normalized_summary
        self.field_errors = normalized_field_errors
        self.error_code = str(error_code or "integrity")
        self.fields = normalized_fields

    def __str__(self) -> str:
        return self.summary_message
