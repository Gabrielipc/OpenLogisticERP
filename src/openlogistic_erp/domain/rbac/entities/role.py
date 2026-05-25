"""Role entity."""

from dataclasses import dataclass, field

from .permission_cell import PermissionCell


@dataclass(frozen=True)
class Role:
    name: str
    permissions: list[PermissionCell] = field(default_factory=list)
