from __future__ import annotations


class ReportError(Exception):
    """Base exception for application report failures."""


class ReportNotFoundError(ReportError):
    """Raised when a report definition or reader cannot be found."""


class ReportValidationError(ReportError):
    """Raised when a report request does not satisfy its definition."""


class ReportExportError(ReportError):
    """Raised when a report export fails."""
