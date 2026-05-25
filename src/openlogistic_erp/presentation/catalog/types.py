"""Shared catalog presentation types."""

from __future__ import annotations

from enum import StrEnum


class FormMode(StrEnum):
    CREATE = "create"
    EDIT = "edit"
    VIEW = "view"
