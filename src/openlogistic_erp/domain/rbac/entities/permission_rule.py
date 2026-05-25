"""Permission action-level model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionRule:
    resource: str
    action: str
