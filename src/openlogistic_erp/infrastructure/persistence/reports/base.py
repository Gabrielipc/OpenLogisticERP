"""Shared helpers for persistence-backed report readers."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func


class ReportReaderBase:
    """Base helper namespace for SQL-backed report readers."""

    _DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")

    @staticmethod
    def parse_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_date(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.min)
        if not isinstance(value, str):
            return None

        raw = value.strip()
        if not raw:
            return None
        for date_format in ReportReaderBase._DATE_FORMATS:
            try:
                return datetime.strptime(raw, date_format)
            except ValueError:
                continue
        return None

    @staticmethod
    def parse_date_range(raw: Any) -> tuple[datetime | None, datetime | None]:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return None, None

        start = ReportReaderBase.parse_date(raw[0])
        end = ReportReaderBase.parse_date(raw[1])
        if end is not None:
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        if start is not None and end is not None and start > end:
            start, end = end.replace(hour=0, minute=0, second=0, microsecond=0), start.replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )
        return start, end

    @staticmethod
    def format_date(value: Any) -> str:
        parsed = ReportReaderBase.parse_date(value)
        if parsed is None:
            return ""
        return parsed.strftime("%d-%m-%Y")

    @staticmethod
    def nombre_completo(nombre: Any, apellido: Any) -> str:
        parts = [str(part).strip() for part in (nombre, apellido) if part not in (None, "")]
        full_name = " ".join(part for part in parts if part)
        return full_name or "(Sin nombre)"

    @staticmethod
    def to_local_expr(value: Any):
        return func.timezone("America/Managua", value)
