"""Permission snapshot DTO used by presentation/admin flows."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionSnapshot:
    resources: dict[str, list[str]]
