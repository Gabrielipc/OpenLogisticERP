"""Permission grant/deny cell."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionCell:
    resource: str
    action: str
    granted: bool
